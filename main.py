"""
main.py

에이전트 팀 진입점
- 직접 실행: 특정 이슈 번호를 처리
- 폴링 모드: GitHub 이슈를 주기적으로 감시 (--watch 옵션)

사용법:
    python main.py --issue 42                  # 이슈 #42 처리
    python main.py --watch --interval 300      # 5분마다 새 이슈 감시
"""

import argparse
import time
import os
from dotenv import load_dotenv
from crewai import Crew, Process
from github import Github

from agents.agents import manager_agent, dev_agent, qa_agent
from tasks.tasks import (
    create_issue_analysis_task,
    create_dev_task,
    create_qa_task,
)

load_dotenv()

# 이미 처리된 이슈 번호를 메모리에 저장 (재시작 시 초기화됨)
# 실제 운영에서는 DB나 파일로 관리하는 걸 권장
processed_issues = set()


def process_issue(issue_number: int):
    """단일 이슈를 처리하는 크루 실행"""
    feature_branch = f"feature/issue-{issue_number}"

    print(f"\n{'='*50}")
    print(f"🚀 이슈 #{issue_number} 처리 시작")
    print(f"   브랜치: {feature_branch}")
    print(f"{'='*50}\n")

    # 태스크 생성 (순서 중요: 매니저 → 개발 → QA)
    tasks = [
        create_issue_analysis_task(issue_number),
        create_dev_task(issue_number, feature_branch),
        create_qa_task(issue_number, feature_branch),
    ]

    # 크루 구성
    # Process.sequential = 태스크를 순서대로 실행
    # Process.hierarchical = 매니저가 자동으로 태스크를 분배 (더 자율적)
    crew = Crew(
        agents=[manager_agent, dev_agent, qa_agent],
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()

    print(f"\n{'='*50}")
    print(f"✅ 이슈 #{issue_number} 처리 완료")
    print(f"{'='*50}")
    print(result)

    return result


def watch_new_issues(interval_seconds: int = 300):
    """새로운 GitHub 이슈를 주기적으로 감시"""
    g = Github(os.getenv("GITHUB_TOKEN"))
    repo = g.get_repo(os.getenv("GITHUB_REPO"))

    print(f"👀 이슈 감시 시작 (매 {interval_seconds}초마다 체크)")
    print(f"   저장소: {os.getenv('GITHUB_REPO')}")
    print(f"   라벨 'agent-todo' 달린 이슈만 처리합니다\n")

    while True:
        try:
            # 'agent-todo' 라벨이 달린 open 이슈만 처리
            # 라벨로 에이전트가 처리할 이슈를 명시적으로 제어할 수 있음
            issues = repo.get_issues(state="open", labels=["agent-todo"])

            for issue in issues:
                if issue.number not in processed_issues:
                    print(f"📌 새 이슈 발견: #{issue.number} - {issue.title}")
                    process_issue(issue.number)
                    processed_issues.add(issue.number)

                    # 처리 완료 라벨 교체 (agent-todo → agent-done)
                    issue.remove_from_labels("agent-todo")
                    try:
                        issue.add_to_labels("agent-done")
                    except Exception:
                        pass  # 라벨이 없으면 무시

            print(f"⏳ {interval_seconds}초 대기 중... (처리 완료: {len(processed_issues)}개)")
            time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\n🛑 감시 종료")
            break
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            print(f"   {interval_seconds}초 후 재시도...")
            time.sleep(interval_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI 에이전트 팀 실행")
    parser.add_argument("--issue", type=int, help="처리할 이슈 번호")
    parser.add_argument("--watch", action="store_true", help="이슈 감시 모드 실행")
    parser.add_argument("--interval", type=int, default=300, help="감시 주기 (초, 기본 300)")

    args = parser.parse_args()

    if args.issue:
        process_issue(args.issue)
    elif args.watch:
        watch_new_issues(args.interval)
    else:
        parser.print_help()
        print("\n예시:")
        print("  python main.py --issue 42")
        print("  python main.py --watch --interval 300")
