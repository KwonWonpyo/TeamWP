"""
test_main.py

TeamWP 기능 개발/테스트용 진입점.
- 소스코드에 테스트할 에이전트, 툴, 태스크, 프로세스를 배열로 정의해 두고
- CLI로 프로세스를 선택해 원할 때 실행합니다.

사용법:
    python test_main.py                    # 대화형 메뉴에서 프로세스 선택 후 실행
    python test_main.py --list             # 등록된 프로세스 목록 출력
    python test_main.py --run <id|이름>     # 지정한 프로세스만 실행 (id는 1부터)
"""

import argparse
import os
import sys
from pathlib import Path

# 프로젝트 루트의 .env 로드
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

# ─────────────────────────────────────────────────────────────────────────────
# 테스트용 정의: 소스코드에 배열로 관리 (필요 시 항목 추가/수정)
# ─────────────────────────────────────────────────────────────────────────────

# 테스트에서 선택할 수 있는 에이전트 식별자 (agents.agents와 매핑)
TEST_AGENTS = [
    {"id": "manager", "name": "바이스(PM)", "description": "매니저 에이전트"},
    {"id": "dev", "name": "플뢰르(Dev)", "description": "개발 에이전트"},
    {"id": "qa", "name": "베델(QA)", "description": "QA 에이전트"},
    {"id": "ui_designer", "name": "아주르(UI Designer)", "description": "UI 디자이너 에이전트"},
    {"id": "ui_publisher", "name": "엘시(UI Publisher)", "description": "UI 퍼블리셔 에이전트"},
]

# 테스트에서 선택할 수 있는 툴 이름 (실제 툴은 tools/ 모듈에서 로드)
TEST_TOOLS = [
    "get_github_issue",
    "comment_github_issue",
    "list_github_issues",
    "read_github_file",
    "write_github_file",
    "create_github_branch",
    "create_github_pr",
    "create_github_issue",
]

# 테스트에서 선택할 수 있는 태스크 유형
TEST_TASKS = [
    {"id": "issue_analysis", "name": "이슈 분석·스펙 작성", "description": "매니저 태스크"},
    {"id": "dev_impl", "name": "구현·커밋·PR", "description": "개발 태스크"},
    {"id": "qa_review", "name": "코드 리뷰·QA", "description": "QA 태스크"},
    {"id": "ui_designer", "name": "디자인 스펙·스타일", "description": "UI Designer 태스크"},
    {"id": "ui_publisher", "name": "웹 퍼블리싱·PR", "description": "UI Publisher 태스크"},
]


def _run_process_meta_only():
    """프로세스: 메타 정보만 출력 (에이전트/툴/태스크 배열 확인)."""
    print("\n[테스트] 메타 정보 출력")
    print("-" * 40)
    print("TEST_AGENTS:", [a["id"] for a in TEST_AGENTS])
    print("TEST_TOOLS:", TEST_TOOLS)
    print("TEST_TASKS:", [t["id"] for t in TEST_TASKS])
    print("-" * 40)
    return None


def _run_process_agents_list():
    """프로세스: 실제 에이전트 객체 로드 후 툴 목록 출력."""
    from agents.agents import manager_agent, dev_agent, qa_agent, ui_designer_agent, ui_publisher_agent
    agents_map = {
        "manager": manager_agent,
        "dev": dev_agent,
        "qa": qa_agent,
        "ui_designer": ui_designer_agent,
        "ui_publisher": ui_publisher_agent,
    }
    print("\n[테스트] 에이전트별 툴 목록")
    print("-" * 40)
    for aid, agent in agents_map.items():
        names = [getattr(t, "name", type(t).__name__) for t in agent.tools]
        print(f"  {aid}: {names}")
    print("-" * 40)
    return None


def _run_process_single_tool_dry():
    """프로세스: 단일 툴 존재 여부 확인 (실제 API 호출 없음)."""
    from tools.github_tools import (
        GetIssueTool,
        CommentIssueTool,
        ListIssuesTool,
        ReadFileTool,
        WriteFileTool,
        CreateBranchTool,
        CreatePRTool,
        CreateIssueTool,
    )
    name_to_cls = {
        "get_github_issue": GetIssueTool,
        "comment_github_issue": CommentIssueTool,
        "list_github_issues": ListIssuesTool,
        "read_github_file": ReadFileTool,
        "write_github_file": WriteFileTool,
        "create_github_branch": CreateBranchTool,
        "create_github_pr": CreatePRTool,
        "create_github_issue": CreateIssueTool,
    }
    print("\n[테스트] 툴 클래스 로드 확인 (실행 없음)")
    print("-" * 40)
    for name in TEST_TOOLS:
        cls = name_to_cls.get(name)
        status = "OK" if cls else "NOT FOUND"
        print(f"  {name}: {status}")
    print("-" * 40)
    return None


def _run_process_manager_only(issue_number: int = 1):
    """프로세스: 매니저 에이전트만 실행 (이슈 분석 태스크). 실제 이슈 번호 사용 시 GitHub 호출 발생."""
    from crewai import Crew, Process
    from agents.agents import manager_agent
    from tasks.tasks import create_issue_analysis_task
    print(f"\n[테스트] 매니저만 실행 (이슈 #{issue_number})")
    print("-" * 40)
    task = create_issue_analysis_task(issue_number)
    crew = Crew(agents=[manager_agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    print("-" * 40)
    return result


def _run_process_full_crew(issue_number: int = 1):
    """프로세스: 풀 크루 실행 (매니저 → 개발 → QA). main.process_issue 호출."""
    from main import process_issue
    print(f"\n[테스트] 풀 크루 실행 (이슈 #{issue_number})")
    print("-" * 40)
    result = process_issue(issue_number)
    print("-" * 40)
    return result


# 등록된 테스트 프로세스: id, 이름, 설명, 실행 함수(인자 없음)
# 새 프로세스는 이 배열에 추가하면 CLI에서 선택 가능
TEST_PROCESSES = [
    {
        "id": 1,
        "name": "메타 정보 출력",
        "description": "TEST_AGENTS, TEST_TOOLS, TEST_TASKS 배열 내용만 출력",
        "run": _run_process_meta_only,
    },
    {
        "id": 2,
        "name": "에이전트 툴 목록",
        "description": "각 에이전트에 연결된 툴 이름 출력",
        "run": _run_process_agents_list,
    },
    {
        "id": 3,
        "name": "툴 로드 확인",
        "description": "GitHub 툴 클래스 로드 여부 확인 (API 호출 없음)",
        "run": _run_process_single_tool_dry,
    },
    {
        "id": 4,
        "name": "매니저만 실행",
        "description": "매니저 에이전트만 실행 (이슈 분석 태스크, 이슈 번호 필요)",
        "run": lambda: _run_process_manager_only(_get_test_issue_number()),
    },
    {
        "id": 5,
        "name": "풀 크루 실행",
        "description": "매니저→개발→QA 전체 실행 (main.process_issue, 이슈 번호 필요)",
        "run": lambda: _run_process_full_crew(_get_test_issue_number()),
    },
]


def _get_test_issue_number() -> int:
    """환경 변수 TEST_ISSUE_NUMBER 또는 기본값 1."""
    return int(os.getenv("TEST_ISSUE_NUMBER", "1"))


def list_processes():
    """등록된 프로세스 목록 출력."""
    print("\n등록된 테스트 프로세스:")
    print("-" * 50)
    for p in TEST_PROCESSES:
        print(f"  {p['id']}. {p['name']}")
        print(f"     {p['description']}")
    print("-" * 50)


def run_process_by_id(pid: int) -> bool:
    """id로 프로세스 실행. 성공 시 True."""
    for p in TEST_PROCESSES:
        if p["id"] == pid:
            p["run"]()
            return True
    return False


def run_process_by_name(name: str) -> bool:
    """이름(부분 일치)으로 프로세스 실행. 성공 시 True."""
    name_lower = name.strip().lower()
    for p in TEST_PROCESSES:
        if name_lower in p["name"].lower():
            p["run"]()
            return True
    return False


def interactive_menu():
    """대화형 메뉴: 번호 입력받아 해당 프로세스 실행."""
    list_processes()
    try:
        raw = input("\n실행할 프로세스 번호 (Enter=종료): ").strip()
        if not raw:
            print("종료합니다.")
            return
        pid = int(raw)
        if run_process_by_id(pid):
            print("\n실행 완료.")
        else:
            print(f"알 수 없는 번호: {pid}")
    except ValueError:
        print("숫자를 입력해 주세요.")
    except KeyboardInterrupt:
        print("\n종료합니다.")


def main():
    parser = argparse.ArgumentParser(
        description="TeamWP 기능/테스트: 등록된 프로세스 선택 실행",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python test_main.py                 # 메뉴에서 선택
  python test_main.py --list         # 프로세스 목록만 출력
  python test_main.py --run 1        # 1번 프로세스 실행
  python test_main.py --run "매니저만"
  TEST_ISSUE_NUMBER=42 python test_main.py --run 4   # 이슈 42로 매니저만 실행
        """,
    )
    parser.add_argument("--list", action="store_true", help="등록된 프로세스 목록 출력")
    parser.add_argument("--run", type=str, metavar="ID_OR_NAME", help="실행할 프로세스 (id 또는 이름)")

    args = parser.parse_args()

    if args.list:
        list_processes()
        return

    if args.run is not None:
        run_arg = args.run.strip()
        # 숫자면 id로 실행
        if run_arg.isdigit():
            if run_process_by_id(int(run_arg)):
                return
            print(f"프로세스 id를 찾을 수 없습니다: {run_arg}", file=sys.stderr)
        else:
            if run_process_by_name(run_arg):
                return
            print(f"프로세스 이름을 찾을 수 없습니다: {run_arg}", file=sys.stderr)
        sys.exit(1)

    interactive_menu()


if __name__ == "__main__":
    main()
