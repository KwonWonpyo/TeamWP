"""
tasks/tasks.py

각 에이전트가 수행할 태스크 정의.
Process.hierarchical 구조에서는 PM(바이스)에게 단일 태스크를 주면
PM이 직접 적합한 팀원에게 위임하므로 태스크 분리가 불필요합니다.

태스크:
  create_issue_task — 바이스(PM)에게 전달하는 단일 진입점 태스크
                      PM이 스펙 작성 후 팀원(플뢰르/타이니/아주르/엘시/베델)에게 위임
"""

from crewai import Task
from agents.agents import manager_agent


def create_issue_task(issue_number: int) -> Task:
    """PM(바이스)에게 전달하는 단일 태스크. hierarchical Crew에서 PM이 팀을 직접 구성·위임한다."""
    return Task(
        description=f"""
            GitHub 이슈 #{issue_number}을 처리하세요.

            [저장소 docs/ 규칙] 저장소에 docs/plan, docs/skill, docs/issues 디렉터리가 있으면:
            - docs/skill/ 내 파일을 읽어 프로젝트 스택·가이드라인에 맞게 스펙을 제안한다.
            - docs/plan/ 이 있으면 참고해 맥락에 반영한다.
            - 분석·스펙 요약을 docs/issues/issue-{issue_number}.md 에 작성한다 (없는 경로면 무시).

            [PM이 수행할 작업]
            1. get_github_issue 툴로 이슈 #{issue_number} 상세 내용과 모든 댓글을 읽는다.
            2. 기존 댓글에 이미 있는 결정사항·제약사항·미해결 논점을 정리한 뒤 기술 스펙에 반영한다.
            3. (docs/skill, docs/plan 존재 시) read_github_file로 해당 경로 파일을 읽는다.
            4. 이슈 유형을 파악한다 (신규 기능 / 버그 수정 / 개선 / 기타).
            5. 이 작업에 맞는 기술 스펙을 작성한다. 반드시 다음을 명시한다:
               - 사용할 언어·프레임워크·라이브러리
               - 구현 범위와 산출물 (어떤 파일/경로를 만들거나 수정할지)
               - API·UI·스크립트 등 형태와 컨벤션
            6. 반드시 comment_github_issue 툴을 호출하여 이슈 #{issue_number}에 기술 스펙 댓글을 남긴다.
               댓글 본문 맨 앞에 "**[바이스(Vice) — PM]**" 헤더를 붙인다.
            7. (docs/issues 존재 시) 요약을 docs/issues/issue-{issue_number}.md 에 write_github_file로 남긴다.
            8. 스펙에 맞는 팀원에게 작업을 위임한다:
               - 복잡한 기능·백엔드·API → 플뢰르(Fleur) — Senior Developer
               - 단순 스크립트·설정·문서 → 타이니(Tiny) — Developer
               - UI 디자인·퍼블리싱 → 아주르(Azure) — UI Designer & Publisher
               - 기술 리스크 검토 → 엘시(Elcy) — Devil's Advocate
               - 코드 품질·UX 검증 → 베델(Bethel) — QA Engineer
               필요에 따라 여러 팀원에게 순차적으로 위임한다.
            9. 모든 작업이 완료되면 update_github_issue_labels 툴로
               이슈 #{issue_number}에서 agent-todo 라벨을 제거하고 agent-done 라벨을 추가한다.
        """,
        expected_output="""
            - 이슈 유형과 요약
            - 기술 스펙: 사용 스택(언어·프레임워크), 구현 범위, 산출물(파일·경로), 컨벤션
            - GitHub 이슈 #{issue_number}에 "[바이스(Vice) — PM]" 헤더가 포함된 PM 스펙 댓글 작성 완료
            - 팀원 위임 및 실행 결과 요약
            - 이슈 라벨: agent-todo 제거, agent-done 추가 완료
        """,
        agent=manager_agent,
    )
