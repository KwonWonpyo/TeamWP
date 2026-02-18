"""
tasks/tasks.py

각 에이전트가 수행할 태스크 정의.
태스크는 실행 시점에 이슈 정보를 받아 동적으로 생성되며, 특정 프레임워크가 아닌 스펙 기반으로 동작합니다.
"""

from crewai import Task
from agents.agents import manager_agent, dev_agent, qa_agent


def create_issue_analysis_task(issue_number: int) -> Task:
    """매니저: 이슈 분석 및 기술 스펙 작성 (스택·언어는 이슈/프로젝트에 맞게 결정)"""
    return Task(
        description=f"""
            GitHub 이슈 #{issue_number}을 분석하세요.
            
            [저장소 docs/ 규칙] 저장소에 docs/plan, docs/skill, docs/issues 디렉터리가 있으면:
            - docs/skill/ 내 파일을 읽어 프로젝트 스택·가이드라인에 맞게 스펙을 제안한다.
            - docs/plan/ 이 있으면 참고해 맥락에 반영한다.
            - 분석·스펙 요약을 docs/issues/issue-{issue_number}.md 에 작성한다 (없는 경로면 무시).
            
            수행할 작업:
            1. get_github_issue 툴로 이슈 #{issue_number} 상세 내용과 모든 댓글을 읽는다.
            2. 기존 댓글에 이미 있는 결정사항/제약사항/미해결 논점을 정리한 뒤 기술 스펙에 반영한다.
            3. (docs/skill, docs/plan 존재 시) read_github_file로 해당 경로 파일을 읽는다.
            4. 이슈 유형을 파악한다 (신규 기능 / 버그 수정 / 개선 / 기타).
            5. 이 작업에 맞는 기술 스펙을 작성한다. 반드시 다음을 명시한다:
               - 사용할 언어·프레임워크·라이브러리 (이슈에 이미 적혀 있으면 따르고, 없으면 docs/skill·웹/프로젝트 맥락에 맞게 제안)
               - 구현 범위와 산출물 (어떤 파일/경로를 만들거나 수정할지)
               - API·UI·스크립트 등 형태와 컨벤션
            6. 이슈에 분석 결과와 위 기술 스펙을 댓글로 남긴다.
            7. (docs/issues 존재 시) 요약을 docs/issues/issue-{issue_number}.md 에 write_github_file로 남긴다.
        """,
        expected_output="""
            - 이슈 유형과 요약
            - 기술 스펙: 사용 스택(언어·프레임워크), 구현 범위, 산출물(파일·경로), 컨벤션
            - GitHub 이슈에 남긴 댓글 확인
        """,
        agent=manager_agent,
    )


def create_dev_task(issue_number: int, feature_branch: str) -> Task:
    """개발 에이전트: 스펙에 맞는 구현 및 커밋·PR"""
    return Task(
        description=f"""
            이슈 #{issue_number}에 대한 구현을 하세요. 반드시 매니저가 댓글로 남긴 기술 스펙을 따릅니다.
            
            [저장소 docs/ 규칙] 저장소에 docs/skill, docs/issues 가 있으면:
            - docs/skill/ 내 파일을 읽어 스택·컨벤션을 준수한다.
            - docs/issues/issue-{issue_number}.md 가 있으면 매니저 요약을 참고한다.
            - 구현 요약을 docs/issues/issue-{issue_number}.md 에 추가해도 된다 (없는 경로면 무시).
            
            수행할 작업:
            1. get_github_issue 툴로 이슈 본문과 모든 댓글(매니저 스펙 포함)을 읽는다.
            2. create_github_branch로 '{feature_branch}' 브랜치를 main 기준으로 생성한다(이미 있으면 재사용).
            3. (docs/skill 존재 시) read_github_file로 프로젝트 규칙을 확인한다.
            4. 스펙에 명시된 언어·프레임워크·파일 경로에 맞춰 구현한다. 스펙에 없는 스택으로 바꾸지 않는다.
            5. 기존 관련 파일이 있다면 read_github_file로 확인한 뒤, 스펙에 맞게 작성·수정한다.
            6. write_github_file로 '{feature_branch}' 브랜치에 커밋한다 (경로·파일명은 스펙 또는 docs/skill·저장소 컨벤션 따름).
            7. create_github_pr로 main 브랜치에 대한 PR을 생성한다.
            8. 이슈에 개발 완료 댓글을 남긴다 (PR 링크 + QA가 확인할 변경 요약 포함).
            9. (선택) Vercel 등 배포 툴이 있으면 스펙이나 이슈에 배포 요청이 있을 때 사용한다.
            
            원칙: 기술 스펙을 정확히 따르고, 해당 스택의 일반적인 모범 사례(타입·에러 처리·접근성 등)를 적용한다.
        """,
        expected_output="""
            - 스펙에 맞게 작성된 코드·산출물
            - GitHub 커밋 및 PR 링크
            - 이슈에 남긴 완료 댓글
        """,
        agent=dev_agent,
    )


def create_qa_task(issue_number: int, feature_branch: str) -> Task:
    """QA 에이전트: 스펙·스택 기준 코드 리뷰"""
    return Task(
        description=f"""
            이슈 #{issue_number}에서 개발된 코드를 리뷰하세요.
            
            [저장소 docs/ 규칙] 저장소에 docs/skill, docs/issues 가 있으면:
            - docs/skill/ 의 모범 사례·규칙을 리뷰 기준으로 참고한다.
            - docs/issues/issue-{issue_number}.md 가 있으면 스펙·구현 요약을 참고하고, 리뷰 요약을 해당 파일에 추가해도 된다 (없는 경로면 무시).
            
            수행할 작업:
            1. get_github_issue 툴로 이슈 본문과 모든 댓글(매니저 스펙, 개발 구현 결과/PR 링크 포함)을 읽는다.
            2. (docs/issues, docs/skill 존재 시) read_github_file로 해당 이슈 요약·프로젝트 규칙을 확인한다.
            3. read_github_file로 '{feature_branch}' 브랜치의 변경된 파일을 읽는다 (경로는 이슈·댓글 또는 저장소 구조에서 확인).
            4. 다음 기준으로 리뷰한다:
               - 매니저 기술 스펙(스택·범위·산출물) 준수 여부
               - 해당 언어·프레임워크의 모범 사례 및 안티패턴
               - 버그·엣지 케이스·타입 안전성·접근성·가독성
            5. 리뷰 결과를 이슈에 댓글로 남긴다 (✅ 통과 / ⚠️ 개선 권장 / 🚨 수정 필요 형식).
            6. (docs/issues 존재 시) 리뷰 요약을 docs/issues/issue-{issue_number}.md 에 반영해도 된다.
            7. 별도 후속 작업이 필요하면 create_github_issue로 새 이슈를 만들고, 라벨은 agent-followup만 붙인다 (agent-todo는 붙이지 않음).
        """,
        expected_output="""
            - 스펙 준수 여부
            - 코드 리뷰 체크리스트 및 발견된 문제·개선 제안
            - 최종 판단 (Approve / Request Changes)
        """,
        agent=qa_agent,
    )
