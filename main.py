"""
main.py

에이전트 팀 진입점
- 직접 실행: 특정 이슈 번호를 처리
- 폴링 모드: GitHub 이슈를 주기적으로 감시 (--watch 옵션)
- 대시보드 모드: localhost:3000 웹 대시보드 + 선택적 감시

사용법:
    python main.py --issue 42                        # 이슈 #42 처리 (.env의 GITHUB_REPO)
    python main.py --watch --interval 300            # 5분마다 새 이슈 감시
    python main.py --dashboard [--watch] [--interval N]  # 대시보드 + 선택적 감시
    python main.py --watch --repo owner/other-repo   # 다른 저장소 감시 (여러 프로젝트 시)
"""

import argparse
import time
import os
import threading
import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone

from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트의 .env 로드 (실행 경로가 달라도 동일한 .env 사용)
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)

# OpenAI API 키가 없으면 LLM 호출이 실패하고, OpenAI 콘솔 사용량도 0으로 남음
def _check_llm_api_key():
    key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not key or not str(key).strip():
        print(
            "[경고] OPENAI_API_KEY(또는 ANTHROPIC_API_KEY)가 설정되지 않았습니다. "
            "LLM 호출이 실패하며 OpenAI 콘솔 사용량도 0으로 나올 수 있습니다. .env 파일과 실행 경로를 확인하세요."
        )
    else:
        print("[LLM] API 키가 설정됨 (OpenAI 또는 Anthropic). 정상 호출 시 OpenAI 콘솔에 사용량이 집계됩니다.")

_check_llm_api_key()

from usage_hooks import register_usage_hooks
register_usage_hooks()

from crewai import Crew, Process
from github import Auth, Github

from agents.agents import manager_agent, dev_agent, qa_agent, ui_designer_agent, ui_publisher_agent
from tasks.tasks import (
    create_issue_analysis_task,
    create_dev_task,
    create_qa_task,
    create_ui_design_task,
    create_devils_advocate_task,
    TASK_FACTORY,
    AGENT_HEADER_MAP,
)

# 이미 처리된 이슈 번호를 메모리에 저장 (재시작 시 초기화됨)
# 실제 운영에서는 DB나 파일로 관리하는 걸 권장
processed_issues = set()


def _format_crew_result(result) -> str:
    """크루 실행 결과를 사람이 읽기 쉬운 문자열로 변환. Final Answer가 도구 호출 객체면 요약만 반환."""
    if result is None:
        return "(결과 없음)"
    if isinstance(result, str):
        return result.strip() or "(빈 문자열)"
    # CrewAI가 도구 호출 객체를 그대로 반환한 경우 (실제 도구 실행이 안 된 경우)
    if isinstance(result, (list, tuple)):
        tool_names = []
        for item in result:
            name = getattr(getattr(item, "function", None), "name", None) or getattr(item, "name", None)
            if name:
                tool_names.append(name)
        if tool_names:
            return (
                "[도구 호출만 반환됨] 에이전트가 도구를 실행하지 않고 호출 목록만 반환했습니다. "
                f"요청된 도구: {', '.join(tool_names)}. "
                "CrewAI 버전 또는 LLM 응답 형식 이슈일 수 있습니다."
            )
    s = str(result)
    if "ChatCompletionMessageToolCall" in s or "Function(arguments=" in s:
        return (
            "[도구 호출 객체가 반환됨] 최종 답변이 텍스트가 아니라 도구 호출 객체입니다. "
            "실제로 get_github_issue, comment_github_issue 등이 실행되었는지 이슈/댓글에서 확인하세요."
        )
    return s


def _get_repo():
    """PyGithub repo 객체 반환 (댓글 검증용)."""
    token = os.getenv("GITHUB_TOKEN")
    repo_name = os.getenv("GITHUB_REPO")
    g = Github(auth=Auth.Token(token)) if token else Github()
    return g.get_repo(repo_name.strip())


def _count_comments(repo, issue_number: int) -> int:
    """이슈의 현재 댓글 수."""
    try:
        return repo.get_issue(issue_number).get_comments().totalCount
    except Exception:
        return -1


# 폴백: 매니저 플래닝 실패 시 기본 에이전트 세트
_DEFAULT_AGENT_IDS = ["dev", "qa"]

# 에이전트 ID → 실제 에이전트 객체 매핑
AGENT_OBJECT_MAP = {
    "manager": manager_agent,
    "azure":   ui_designer_agent,
    "dev":     dev_agent,
    "elcy":    ui_publisher_agent,
    "qa":      qa_agent,
}

CREW_TIMEOUT_SECONDS = 600  # 10분 초과 시 강제 종료


def _find_missing_agents(repo, issue_number: int, before_count: int, expected_headers: list[str]) -> list[str]:
    """crew 실행 후 새로 달린 댓글을 검사해, 헤더가 빠진 에이전트 목록을 반환한다."""
    try:
        comments = list(repo.get_issue(issue_number).get_comments())
        new_comments = comments[before_count:] if before_count >= 0 else comments
        new_bodies = "\n".join(c.body or "" for c in new_comments)
    except Exception:
        return list(expected_headers)
    return [h for h in expected_headers if h not in new_bodies]


def _force_comment(repo, issue_number: int, missing_headers: list[str], crew_result) -> None:
    """댓글을 남기지 않은 에이전트 대신 오케스트레이션 코드가 보정 댓글을 작성한다."""
    names = ", ".join(missing_headers)
    result_text = str(crew_result) if crew_result else ""

    body = (
        f"## [자동 보정] 누락 에이전트 댓글\n\n"
        f"> 다음 에이전트가 `comment_github_issue`를 실행하지 못해 오케스트레이션 코드가 대신 댓글을 남깁니다: **{names}**\n\n"
    )
    if "ChatCompletionMessageToolCall" in result_text or "Function(arguments=" in result_text:
        body += "에이전트가 도구 호출 목록만 반환하고 실제 실행에 실패했습니다.\n"
    elif result_text.strip():
        if len(result_text) > 3000:
            result_text = result_text[:3000] + "\n\n... (이하 생략)"
        body += result_text
    else:
        body += "에이전트 실행 결과가 비어 있습니다.\n"

    try:
        issue = repo.get_issue(issue_number)
        issue.create_comment(body)
        print(f"[보정] 이슈 #{issue_number}에 누락 에이전트({names}) 보정 댓글 작성 완료.")
    except Exception as e:
        print(f"[보정 실패] 이슈 #{issue_number} 강제 댓글 작성 실패: {e}")


def _write_system_error_comment(repo, issue_number: int, reason: str) -> None:
    """크루 실행 실패 또는 타임아웃 시 이슈에 시스템 에러 댓글을 작성한다."""
    body = (
        f"## [시스템] 에이전트 실행 실패\n\n"
        f"> **사유**: {reason}\n\n"
        f"담당자가 확인 후 재실행하거나 `agent-todo` 라벨을 다시 붙여 주세요."
    )
    try:
        repo.get_issue(issue_number).create_comment(body)
        print(f"[에러 댓글] 이슈 #{issue_number}에 시스템 에러 댓글 작성 완료.")
    except Exception as e:
        print(f"[에러 댓글 실패] {e}")


def _parse_agent_ids_from_result(result) -> list[str] | None:
    """매니저 출력에서 JSON 에이전트 목록을 파싱한다. 실패 시 None 반환."""
    text = ""
    if isinstance(result, str):
        text = result
    elif hasattr(result, "raw_output"):
        text = getattr(result, "raw_output", "") or ""
    elif hasattr(result, "raw"):
        text = getattr(result, "raw", "") or ""
    else:
        text = str(result)

    # ```json ... ``` 블록 우선 탐색
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        # 중괄호 블록 전체 탐색 (마지막 JSON 우선)
        candidates = re.findall(r"\{[^{}]*\"agents\"\s*:[^{}]*\}", text, re.DOTALL)
        match_text = candidates[-1] if candidates else None
    else:
        match_text = match.group(1)

    if not match_text:
        return None

    try:
        data = json.loads(match_text)
        agents = data.get("agents", [])
        if isinstance(agents, list) and agents:
            valid = [a for a in agents if a in TASK_FACTORY]
            return valid if valid else None
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _run_manager_planning(issue_number: int, dashboard_callback=None) -> list[str]:
    """1단계: 매니저만 단독 실행해 팀 구성 JSON을 파싱한다. 실패 시 기본 세트 반환."""
    print(f"[1단계] 매니저 플래닝 시작 (이슈 #{issue_number})")
    task = create_issue_analysis_task(issue_number)
    crew = Crew(
        agents=[manager_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
        task_callback=dashboard_callback,
    )

    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(crew.kickoff)
        try:
            result = fut.result(timeout=CREW_TIMEOUT_SECONDS)
        except FuturesTimeoutError:
            print(f"[1단계] 매니저 플래닝 타임아웃 - 기본 에이전트 세트 사용: {_DEFAULT_AGENT_IDS}")
            return _DEFAULT_AGENT_IDS
        except Exception as e:
            print(f"[1단계] 매니저 플래닝 실패: {e} - 기본 에이전트 세트 사용: {_DEFAULT_AGENT_IDS}")
            return _DEFAULT_AGENT_IDS

    agent_ids = _parse_agent_ids_from_result(result)
    if agent_ids:
        print(f"[1단계] 매니저 선발 에이전트: {agent_ids}")
        return agent_ids
    else:
        print(f"[1단계] JSON 파싱 실패 - 기본 에이전트 세트 사용: {_DEFAULT_AGENT_IDS}")
        return _DEFAULT_AGENT_IDS


def _run_dynamic_crew(
    issue_number: int,
    selected_agent_ids: list[str],
    dashboard_callback=None,
):
    """2단계: 선발된 에이전트로 동적 크루를 구성하고 실행한다."""
    feature_branch = f"feature/issue-{issue_number}"
    design_branch = f"design/issue-{issue_number}"

    tasks = []
    agents = []
    for agent_id in selected_agent_ids:
        factory_fn = TASK_FACTORY.get(agent_id)
        agent_obj = AGENT_OBJECT_MAP.get(agent_id)
        if not factory_fn or not agent_obj:
            print(f"[경고] 알 수 없는 에이전트 ID '{agent_id}' - 건너뜀")
            continue
        if agent_id == "azure":
            tasks.append(factory_fn(issue_number, design_branch))
        elif agent_id in ("dev", "elcy", "qa"):
            tasks.append(factory_fn(issue_number, feature_branch))
        else:
            tasks.append(factory_fn(issue_number))
        agents.append(agent_obj)

    if not tasks:
        print("[2단계] 실행할 태스크 없음 - 건너뜀")
        return None

    id_list = ", ".join(selected_agent_ids)
    print(f"[2단계] 동적 크루 실행: [{id_list}]")

    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
        task_callback=dashboard_callback,
    )

    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(crew.kickoff)
        try:
            return fut.result(timeout=CREW_TIMEOUT_SECONDS)
        except FuturesTimeoutError:
            raise RuntimeError(f"크루 실행 시간 초과 ({CREW_TIMEOUT_SECONDS}초)")


def process_issue(issue_number: int, dashboard_callback=None):
    """단일 이슈를 처리하는 2단계 동적 크루 실행.
    1단계: 매니저 플래닝 → 팀 구성 JSON 파싱
    2단계: 선발 에이전트로 크루 실행
    완료 후 댓글 누락 검증, 누락 시 보정 댓글 작성.
    """
    print(f"\n{'='*50}")
    print(f"[Start] Issue #{issue_number}")
    print(f"{'='*50}\n")

    repo = _get_repo()
    before_count = _count_comments(repo, issue_number)
    print(f"[검증] 실행 전 댓글 수: {before_count}")

    # 1단계: 매니저 플래닝 (댓글 callback은 1단계부터 전달)
    try:
        selected_ids = _run_manager_planning(issue_number, dashboard_callback)
    except Exception as e:
        from usage_tracking import send_discord_run_failed
        send_discord_run_failed(issue_number, str(e))
        _write_system_error_comment(repo, issue_number, f"매니저 플래닝 오류: {e}")
        raise

    # 2단계: 매니저를 제외한 선발 에이전트 실행
    dynamic_ids = [aid for aid in selected_ids if aid != "manager"]

    result = None
    if dynamic_ids:
        try:
            result = _run_dynamic_crew(issue_number, dynamic_ids, dashboard_callback)
        except Exception as e:
            from usage_tracking import send_discord_run_failed
            send_discord_run_failed(issue_number, str(e))
            _write_system_error_comment(repo, issue_number, str(e))
            raise

    readable = _format_crew_result(result)
    print(f"\n[완료] Issue #{issue_number}")
    print(f"{'='*50}")
    if len(readable) > 2000:
        print(readable[:2000] + "\n... (이하 생략)")
    else:
        print(readable)
    print(f"{'='*50}")

    # 댓글 검증: 실행된 에이전트 헤더가 모두 달렸는지 확인
    all_executed_ids = ["manager"] + dynamic_ids
    expected_headers = [AGENT_HEADER_MAP[aid] for aid in all_executed_ids if aid in AGENT_HEADER_MAP]
    after_count = _count_comments(repo, issue_number)
    new_count = max(after_count - before_count, 0)
    print(f"[검증] 실행 후 댓글 수: {after_count} (신규 {new_count}개)")

    missing = _find_missing_agents(repo, issue_number, before_count, expected_headers)
    if missing:
        print(f"[검증] 댓글 누락 에이전트: {', '.join(missing)}. 보정 댓글을 작성합니다.")
        _force_comment(repo, issue_number, missing, result)
    else:
        print(f"[검증] 모든 에이전트({len(expected_headers)}명)가 정상적으로 댓글을 작성했습니다.")

    print()
    return result


def watch_new_issues(interval_seconds: int = 300, process_fn=None):
    """새로운 GitHub 이슈를 주기적으로 감시. process_fn이 있으면 그걸로 이슈 처리 (대시보드 연동용)."""
    run_issue = process_fn or process_issue
    token = os.getenv("GITHUB_TOKEN")
    repo_name = os.getenv("GITHUB_REPO")
    if not repo_name or not repo_name.strip():
        raise ValueError(
            "GITHUB_REPO가 .env에 없거나 비어 있습니다. "
            "예: GITHUB_REPO=owner/repo 형식으로 설정하세요."
        )
    g = Github(auth=Auth.Token(token)) if token else Github()
    try:
        repo = g.get_repo(repo_name.strip())
    except Exception as e:
        print(f"[오류] 레포지토리 접근 실패: {repo_name.strip()}")
        print(f"       {e}")
        raise

    print(f"Issue watch started (every {interval_seconds}s)")
    print(f"   저장소: {os.getenv('GITHUB_REPO')}")
    print(f"   라벨 'agent-todo' 달린 이슈만 처리합니다\n")

    while True:
        try:
            issues = list(repo.get_issues(state="open", labels=["agent-todo"]))
            new_count = sum(1 for i in issues if i.number not in processed_issues)

            for issue in issues:
                if issue.number not in processed_issues:
                    from usage_tracking import is_over_limit
                    if is_over_limit():
                        print("Usage limit exceeded. Skipping new issues until reset.")
                        break
                    print(f"New issue: #{issue.number} - {issue.title}")
                    run_issue(issue.number)
                    processed_issues.add(issue.number)

                    issue.remove_from_labels("agent-todo")
                    try:
                        issue.add_to_labels("agent-done")
                    except Exception:
                        pass

            print(f"이슈 조회: {len(issues)}건 (신규 {new_count}건) - {interval_seconds}초 후 재조회 (누적 처리: {len(processed_issues)})")
            time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\nWatch stopped.")
            break
        except Exception as e:
            print(f"[오류] 이슈 조회 실패 (레포 접근 등): {e}")
            print(f"       {interval_seconds}초 후 재시도...")
            time.sleep(interval_seconds)


def run_dashboard(port: int = 3000, watch: bool = False, interval: int = 300):
    """대시보드 서버 기동 + 선택적 감시 백그라운드. process_issue_with_dashboard 사용."""
    from dashboard_state import (
        init_agents_from_crew,
        set_run_started,
        on_task_complete,
        set_run_finished,
        set_idle,
    )
    from dashboard.server import app, register_runner

    # 대시보드 에이전트 초기화: 동적 팀 구성에서 사용될 수 있는 전체 에이전트 목록
    agents_for_crew = list(AGENT_OBJECT_MAP.values())
    init_agents_from_crew(agents_for_crew)

    task_index = [0]  # mutable for closure

    def make_task_callback():
        def _cb(output):
            idx = task_index[0]
            try:
                summary = getattr(output, "raw_output", "") or ""
                if isinstance(summary, str) and len(summary) > 200:
                    summary = summary[:200] + "..."
            except Exception:
                summary = ""
            on_task_complete(idx, summary)
            task_index[0] += 1
        return _cb

    def process_issue_with_dashboard(issue_number: int):
        task_index[0] = 0
        started = datetime.now(timezone.utc).isoformat()

        # 1단계: 매니저 플래닝으로 선발 에이전트 목록 먼저 확정
        # 대시보드 에이전트 목록을 실제 런 에이전트로 재초기화하기 위해 직접 호출
        repo = _get_repo()
        before_count = _count_comments(repo, issue_number)

        try:
            selected_ids = _run_manager_planning(issue_number)
        except Exception as e:
            set_run_started(issue_number, started)
            set_run_finished(error=f"매니저 플래닝 실패: {str(e)[:200]}")
            _write_system_error_comment(repo, issue_number, f"매니저 플래닝 오류: {e}")
            return

        # 선발 에이전트(매니저 포함) 객체 목록 구성
        dynamic_ids = [aid for aid in selected_ids if aid != "manager"]
        all_ids = ["manager"] + dynamic_ids
        run_agent_objects = [AGENT_OBJECT_MAP[aid] for aid in all_ids if aid in AGENT_OBJECT_MAP]

        # 대시보드를 실제 런 에이전트로 재초기화 후 시작 상태 설정
        set_run_started(issue_number, started, run_agents=run_agent_objects)

        try:
            result = None
            if dynamic_ids:
                result = _run_dynamic_crew(
                    issue_number, dynamic_ids, dashboard_callback=make_task_callback()
                )

            # 댓글 검증
            expected_headers = [AGENT_HEADER_MAP[aid] for aid in all_ids if aid in AGENT_HEADER_MAP]
            missing = _find_missing_agents(repo, issue_number, before_count, expected_headers)
            if missing:
                _force_comment(repo, issue_number, missing, result)

            summary = _format_crew_result(result)
            set_run_finished(summary[:500] if len(summary) > 500 else summary)
        except Exception as e:
            set_run_finished(error=str(e)[:300])
            _write_system_error_comment(repo, issue_number, str(e))

    def run_issue_background(issue_number: int):
        """API에서 호출 시 백그라운드 스레드로 실행."""
        t = threading.Thread(target=process_issue_with_dashboard, args=(issue_number,))
        t.start()

    register_runner(run_issue_background)

    def run_server():
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print(f"Dashboard: http://127.0.0.1:{port}")
    repo_env = os.getenv("GITHUB_REPO") or "(not set)"
    print(f"GITHUB_REPO: {repo_env}")

    if watch:
        watch_thread = threading.Thread(
            target=watch_new_issues,
            kwargs={"interval_seconds": interval, "process_fn": process_issue_with_dashboard},
            daemon=True,
        )
        watch_thread.start()
        print(f"Watch mode: {interval}s interval")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI 에이전트 팀 실행")
    parser.add_argument("--issue", type=int, help="처리할 이슈 번호")
    parser.add_argument("--watch", action="store_true", help="이슈 감시 모드 실행")
    parser.add_argument("--dashboard", action="store_true", help="웹 대시보드 기동 (localhost:3000)")
    parser.add_argument("--interval", type=int, default=300, help="감시 주기 (초, 기본 300)")
    parser.add_argument("--port", type=int, default=3000, help="대시보드 포트 (기본 3000)")
    parser.add_argument(
        "--repo",
        type=str,
        metavar="OWNER/REPO",
        help="대상 저장소 (예: owner/repo). 없으면 .env의 GITHUB_REPO 사용.",
    )

    args = parser.parse_args()

    if args.repo:
        os.environ["GITHUB_REPO"] = args.repo

    if args.dashboard:
        run_dashboard(port=args.port, watch=args.watch, interval=args.interval)
    elif args.issue:
        process_issue(args.issue)
    elif args.watch:
        watch_new_issues(args.interval)
    else:
        parser.print_help()
        print("\n예시:")
        print("  python main.py --issue 42")
        print("  python main.py --watch --interval 300")
        print("  python main.py --dashboard              # 대시보드만")
        print("  python main.py --dashboard --watch      # 대시보드 + 감시")
        print("  python main.py --watch --repo owner/repo-a")
