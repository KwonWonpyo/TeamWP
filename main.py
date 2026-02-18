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
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from usage_hooks import register_usage_hooks
register_usage_hooks()

from crewai import Crew, Process
from github import Auth, Github

from agents.agents import manager_agent, dev_agent, qa_agent
from tasks.tasks import (
    create_issue_analysis_task,
    create_dev_task,
    create_qa_task,
)

# 이미 처리된 이슈 번호를 메모리에 저장 (재시작 시 초기화됨)
# 실제 운영에서는 DB나 파일로 관리하는 걸 권장
processed_issues = set()


def process_issue(issue_number: int, dashboard_callback=None):
    """단일 이슈를 처리하는 크루 실행. dashboard_callback 있으면 태스크 완료 시 호출."""
    feature_branch = f"feature/issue-{issue_number}"

    print(f"\n{'='*50}")
    print(f"[Start] Issue #{issue_number}")
    print(f"   브랜치: {feature_branch}")
    print(f"{'='*50}\n")

    # 태스크 생성 (순서 중요: 매니저 → 개발 → QA)
    tasks = [
        create_issue_analysis_task(issue_number),
        create_dev_task(issue_number, feature_branch),
        create_qa_task(issue_number, feature_branch),
    ]

    crew = Crew(
        agents=[manager_agent, dev_agent, qa_agent],
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
        task_callback=dashboard_callback,
    )

    result = crew.kickoff()

    print(f"\n{'='*50}")
    print(f"[Done] Issue #{issue_number}")
    print(f"{'='*50}")
    print(result)

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
    repo = g.get_repo(repo_name.strip())

    print(f"Issue watch started (every {interval_seconds}s)")
    print(f"   저장소: {os.getenv('GITHUB_REPO')}")
    print(f"   라벨 'agent-todo' 달린 이슈만 처리합니다\n")

    while True:
        try:
            issues = repo.get_issues(state="open", labels=["agent-todo"])

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

            print(f"Waiting {interval_seconds}s... (done: {len(processed_issues)})")
            time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\nWatch stopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            print(f"   {interval_seconds}초 후 재시도...")
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

    # 에이전트 목록은 고정 (매니저/개발/QA). 나중에 agents 리스트 확장 시 여기서 동적으로 가져오면 됨.
    init_agents_from_crew([manager_agent, dev_agent, qa_agent])

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
        set_run_started(issue_number, started)
        try:
            result = process_issue(issue_number, dashboard_callback=make_task_callback())
            set_run_finished(str(result)[:500] if result else "완료")
        except Exception as e:
            set_run_finished(error=str(e)[:300])

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
