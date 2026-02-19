"""
tasks/tasks.py

각 에이전트가 수행할 태스크 정의.
태스크는 실행 시점에 이슈 정보를 받아 동적으로 생성되며, 특정 프레임워크가 아닌 스펙 기반으로 동작합니다.
"""

from crewai import Task
from agents.agents import manager_agent, dev_agent, qa_agent, ui_designer_agent, ui_publisher_agent


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
            6. 반드시 comment_github_issue 툴을 호출하여 이슈 #{issue_number}에 분석 결과와 기술 스펙 전체를 댓글로 남긴다.
               댓글 본문 맨 앞에 "**[바이스(Vice) — PM]**" 헤더를 붙인다. 댓글을 남기지 않으면 작업이 완료된 것이 아니다.
            7. (docs/issues 존재 시) 요약을 docs/issues/issue-{issue_number}.md 에 write_github_file로 남긴다.
        """,
        expected_output="""
            - 이슈 유형과 요약
            - 기술 스펙: 사용 스택(언어·프레임워크), 구현 범위, 산출물(파일·경로), 컨벤션
            - GitHub 이슈 #{issue_number}에 "[바이스(Vice) — PM]" 헤더가 포함된 댓글 작성 완료
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
            8. 반드시 comment_github_issue로 이슈 #{issue_number}에 댓글을 남긴다. 댓글 본문 맨 앞에 "**[플뢰르(Fleur) — Dev]**" 헤더를 붙인다.
               - 구현을 수행했다면: PR 링크 + QA가 확인할 변경 요약을 포함한다.
               - 아무 작업도 하지 않았다면: 하지 않은 이유를 간단히 설명한다.
               댓글을 남기지 않으면 작업이 완료된 것이 아니다.
            9. (선택) Vercel 등 배포 툴이 있으면 스펙이나 이슈에 배포 요청이 있을 때 사용한다.
            
            원칙: 기술 스펙을 정확히 따르고, 해당 스택의 일반적인 모범 사례(타입·에러 처리·접근성 등)를 적용한다.
        """,
        expected_output="""
            - 스펙에 맞게 작성된 코드·산출물 (또는 미작업 사유)
            - GitHub 커밋 및 PR 링크 (작업한 경우)
            - 이슈 #{issue_number}에 "[플뢰르(Fleur) — Dev]" 헤더가 포함된 댓글 작성 완료
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
            5. 반드시 comment_github_issue로 이슈 #{issue_number}에 리뷰 결과를 댓글로 남긴다. 댓글 본문 맨 앞에 "**[베델(Bethel) — QA]**" 헤더를 붙인다.
               - 리뷰를 수행했다면: ✅ 통과 / ⚠️ 개선 권장 / 🚨 수정 필요 형식으로 결과를 포함한다.
               - 리뷰할 코드가 없거나 아무 작업도 하지 않았다면: 하지 않은 이유를 간단히 설명한다.
               댓글을 남기지 않으면 작업이 완료된 것이 아니다.
            6. (docs/issues 존재 시) 리뷰 요약을 docs/issues/issue-{issue_number}.md 에 반영해도 된다.
            7. 별도 후속 작업이 필요하면 create_github_issue로 새 이슈를 만들고, 라벨은 agent-followup만 붙인다 (agent-todo는 붙이지 않음).
        """,
        expected_output="""
            - 스펙 준수 여부 (또는 리뷰 불가 사유)
            - 코드 리뷰 체크리스트 및 발견된 문제·개선 제안
            - 이슈 #{issue_number}에 "[베델(Bethel) — QA]" 헤더가 포함된 댓글 작성 완료
            - 최종 판단 (Approve / Request Changes)
        """,
        agent=qa_agent,
    )


def create_ui_designer_task(issue_number: int, design_branch: str) -> Task:
    """UI Designer: 디자인 스펙·스타일·가이드라인 작성 및 저장소 반영"""
    return Task(
        description=f"""
            이슈 #{issue_number}에 대한 UI/UX 디자인 산출물을 작성하세요.
            매니저가 댓글로 남긴 기술 스펙과 이슈 요구사항을 기준으로, UI Publisher 또는 Frontend Developer가 활용할 수 있는 형태로 만듭니다.
            
            [저장소 docs/ 규칙] 저장소에 docs/skill, docs/issues 가 있으면:
            - docs/skill/ 내 디자인·UI 관련 가이드를 읽어 반영한다.
            - docs/issues/issue-{issue_number}.md 가 있으면 매니저 요약을 참고하고, 디자인 요약을 추가해도 된다 (없는 경로면 무시).
            
            수행할 작업:
            1. get_github_issue 툴로 이슈 #{issue_number} 본문과 모든 댓글(매니저 스펙 포함)을 읽는다.
            2. (docs/skill, docs/issues 존재 시) read_github_file로 프로젝트 디자인 컨벤션·기존 스타일을 확인한다.
            3. 요구사항에 맞는 디자인 산출물을 만든다. 다음 중 적절한 형태를 선택·조합한다:
               - 디자인 스펙·가이드라인 (마크다운: docs/design/ 또는 이슈별 경로)
               - CSS/SCSS 스타일시트 또는 테마 변수 정의
               - 컴포넌트별 스타일·애니메이션·인터랙션 명세
               - Figma MCP 등 외부 디자인 툴이 있으면 해당 툴을 활용한 결과물 (연결 시)
            4. create_github_branch로 '{design_branch}' 브랜치를 main 기준으로 생성한다(이미 있으면 재사용).
            5. write_github_file로 '{design_branch}' 브랜치에 산출물을 커밋한다 (경로는 스펙·docs 규칙 따름).
            6. 필요 시 create_github_pr로 디자인 브랜치용 PR을 생성한다.
            7. 반드시 comment_github_issue로 이슈 #{issue_number}에 댓글을 남긴다. 댓글 본문 맨 앞에 "**[아주르(Azure) — UI Designer]**" 헤더를 붙인다.
               - 산출물 목록, 파일 경로, UI Publisher/개발자가 참고할 요점을 포함한다.
               댓글을 남기지 않으면 작업이 완료된 것이 아니다.
            
            원칙: CSS 애니메이션·인터랙션·UX·접근성·반응형을 고려하고, 퍼블리셔/개발자가 그대로 활용할 수 있도록 명확히 작성한다.
        """,
        expected_output="""
            - 디자인 스펙·스타일시트·가이드라인 등 산출물 (마크다운/CSS/명세)
            - GitHub 브랜치 커밋 및 필요 시 PR
            - 이슈 #{issue_number}에 "[아주르(Azure) — UI Designer]" 헤더가 포함된 댓글 작성 완료
        """,
        agent=ui_designer_agent,
    )


def create_ui_publisher_task(issue_number: int, feature_branch: str) -> Task:
    """UI Publisher: 웹 표준·접근성 준수 퍼블리싱 및 PR·이슈 댓글"""
    return Task(
        description=f"""
            이슈 #{issue_number}에 대한 웹 퍼블리싱을 수행하세요.
            매니저 스펙과 UI Designer가 제공한 디자인 산출물(마크다운·CSS·가이드라인 등)을 입력으로 활용합니다.
            
            [저장소 docs/ 규칙] 저장소에 docs/skill, docs/issues 가 있으면:
            - docs/skill/ 내 퍼블리싱·접근성 가이드를 읽어 준수한다.
            - docs/issues/issue-{issue_number}.md 및 디자인 관련 댓글을 참고한다.
            
            수행할 작업:
            1. get_github_issue 툴로 이슈 #{issue_number} 본문과 모든 댓글(매니저 스펙, UI Designer 산출물 요약 포함)을 읽는다.
            2. (docs/skill, docs/issues 존재 시) read_github_file로 프로젝트 규칙·디자인 스펙 파일을 확인한다.
            3. UI Designer가 올린 디자인 브랜치 또는 댓글에 안내된 산출물(마크다운, CSS, 이미지 경로 등)을 read_github_file로 읽고 반영한다.
            4. create_github_branch로 '{feature_branch}' 브랜치를 main 기준으로 생성한다(이미 있으면 재사용).
            5. 웹 표준(시맨틱 HTML5), 웹 접근성(WCAG), 크로스 브라우저·반응형을 준수하여 마크업·스타일을 작성한다.
            6. write_github_file로 '{feature_branch}' 브랜치에 커밋한다.
            7. create_github_pr로 main 브랜치에 대한 PR을 생성한다.
            8. 반드시 comment_github_issue로 이슈 #{issue_number}에 댓글을 남긴다. 댓글 본문 맨 앞에 "**[엘시(Elcy) — UI Publisher]**" 헤더를 붙인다.
               - PR 링크, 반영한 디자인·접근성 요약, 확인 포인트를 포함한다.
               댓글을 남기지 않으면 작업이 완료된 것이 아니다.
            
            원칙: 마크다운·소스코드 예시·이미지·Figma 등 입력을 이해하고, 웹 표준·접근성·호환성을 지키며 퍼블리싱한다.
        """,
        expected_output="""
            - 웹 표준·접근성 준수 퍼블리싱 산출물 (HTML/CSS 등)
            - GitHub 브랜치 '{feature_branch}' 커밋 및 PR 링크
            - 이슈 #{issue_number}에 "[엘시(Elcy) — UI Publisher]" 헤더가 포함된 댓글 작성 완료
        """,
        agent=ui_publisher_agent,
    )
