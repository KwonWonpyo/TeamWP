"""
tasks/tasks.py

각 에이전트가 수행할 태스크 정의.
태스크는 실행 시점에 이슈 정보를 받아 동적으로 생성되며, 특정 프레임워크가 아닌 스펙 기반으로 동작합니다.

태스크 순서 (UI 포함 전체 플로우):
  1. create_issue_analysis_task   — 바이스: 스펙 작성
  2. create_ui_design_task        — 아주르: 디자인+퍼블리싱 통합
  3. create_dev_task              — 플뢰르: 코드 구현
  4. create_devils_advocate_task  — 엘시: 비판적 검토
  5. create_qa_task               — 베델: 코드 품질 + 사용자 관점 최종 검증
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
    """베델: 코드 품질 + 실사용자 관점 최종 검증"""
    return Task(
        description=f"""
            이슈 #{issue_number}에서 개발·디자인된 모든 산출물을 코드 품질과 실사용자 관점에서 최종 검증하세요.
            엘시의 Devil's Advocate 검토 결과도 반영 여부를 확인합니다.

            [저장소 docs/ 규칙] 저장소에 docs/skill, docs/issues 가 있으면:
            - docs/skill/ 의 모범 사례·규칙을 리뷰 기준으로 참고한다.
            - docs/issues/issue-{issue_number}.md 가 있으면 스펙·구현 요약을 참고하고, 리뷰 요약을 해당 파일에 추가해도 된다 (없는 경로면 무시).

            수행할 작업:
            1. get_github_issue 툴로 이슈 본문과 모든 댓글(매니저 스펙, 아주르 디자인, 플뢰르 구현 결과, 엘시 비판 검토 포함)을 읽는다.
            2. (docs/issues, docs/skill 존재 시) read_github_file로 해당 이슈 요약·프로젝트 규칙을 확인한다.
            3. read_github_file로 '{feature_branch}' 브랜치의 변경된 파일을 읽는다.
            4. [코드 품질 검토] 다음 기준으로 리뷰한다:
               - 매니저 기술 스펙(스택·범위·산출물) 준수 여부
               - 해당 언어·프레임워크의 모범 사례 및 안티패턴
               - 버그·엣지 케이스·타입 안전성·가독성·성능
            5. [실사용자 관점 검토] 다음을 추가로 확인한다:
               - 실제 사용자가 이 화면·기능을 처음 접했을 때 직관적으로 사용할 수 있는가?
               - 오류·예외 상황에서 사용자가 혼란스럽지 않은 피드백을 받는가?
               - 웹 접근성(WCAG): 키보드 탐색, 스크린 리더, 색상 대비 등이 준수되는가?
            6. [엘시 검토 반영 확인] 엘시가 제기한 리스크·대안 제안이 실제 결과물에 반영되었는지 확인한다.
               미반영 항목이 있으면 그 이유가 타당한지 판단하여 댓글에 명시한다.
            7. 반드시 comment_github_issue로 이슈 #{issue_number}에 리뷰 결과를 댓글로 남긴다. 댓글 본문 맨 앞에 "**[베델(Bethel) — QA]**" 헤더를 붙인다.
               - ✅ 통과 / ⚠️ 개선 권장 / 🚨 수정 필요 형식으로 코드 품질·사용자 관점·엘시 검토 반영 각각 결과를 포함한다.
               - 리뷰할 코드가 없거나 아무 작업도 하지 않았다면: 하지 않은 이유를 간단히 설명한다.
               댓글을 남기지 않으면 작업이 완료된 것이 아니다.
            8. (docs/issues 존재 시) 리뷰 요약을 docs/issues/issue-{issue_number}.md 에 반영해도 된다.
            9. 별도 후속 작업이 필요하면 create_github_issue로 새 이슈를 만들고, 라벨은 agent-followup만 붙인다 (agent-todo는 붙이지 않음).
        """,
        expected_output="""
            - 코드 품질 검토 결과 (스펙 준수, 버그, 모범 사례)
            - 실사용자 관점 검토 결과 (사용성, 접근성)
            - 엘시 Devil's Advocate 검토 반영 여부 확인
            - 이슈 #{issue_number}에 "[베델(Bethel) — QA]" 헤더가 포함된 댓글 작성 완료
            - 최종 판단 (Approve / Request Changes)
        """,
        agent=qa_agent,
    )


def create_ui_design_task(issue_number: int, design_branch: str) -> Task:
    """아주르: 디자인 기획 + HTML/CSS 퍼블리싱 통합 수행 및 PR"""
    return Task(
        description=f"""
            이슈 #{issue_number}에 대한 UI 디자인 기획과 HTML/CSS 퍼블리싱을 직접 수행하세요.
            매니저가 댓글로 남긴 기술 스펙을 기준으로, 디자인 스펙 정의부터 완성된 마크업·스타일 구현까지 일관되게 처리합니다.

            [저장소 docs/ 규칙] 저장소에 docs/skill, docs/issues 가 있으면:
            - docs/skill/ 내 디자인·UI·접근성 관련 가이드를 읽어 반영한다.
            - docs/issues/issue-{issue_number}.md 가 있으면 매니저 요약을 참고하고, 디자인 요약을 추가해도 된다 (없는 경로면 무시).

            수행할 작업:
            1. get_github_issue 툴로 이슈 #{issue_number} 본문과 모든 댓글(매니저 스펙 포함)을 읽는다.
            2. (docs/skill, docs/issues 존재 시) read_github_file로 프로젝트 디자인 컨벤션·기존 스타일을 확인한다.
            3. [디자인 기획] 다음을 포함한 디자인 스펙을 먼저 정의한다:
               - 색상·타이포그래피·간격·레이아웃 명세
               - 인터랙션·애니메이션·반응형 브레이크포인트 기준
               - 컴포넌트별 상태(hover, focus, disabled 등) 명세
               - 접근성(WCAG) 고려 사항
            4. [퍼블리싱] 위 스펙을 직접 구현한다:
               - 시맨틱 HTML5 마크업
               - CSS/SCSS 스타일시트 (디자인 토큰 변수 활용 권장)
               - 반응형·크로스 브라우저 호환성 준수
            5. create_github_branch로 '{design_branch}' 브랜치를 main 기준으로 생성한다 (이미 있으면 재사용).
            6. write_github_file로 '{design_branch}' 브랜치에 디자인 스펙 문서와 구현 결과물을 커밋한다.
            7. create_github_pr로 main 브랜치에 대한 PR을 생성한다.
            8. 반드시 comment_github_issue로 이슈 #{issue_number}에 댓글을 남긴다. 댓글 본문 맨 앞에 "**[아주르(Azure) — UI Designer & Publisher]**" 헤더를 붙인다.
               - 디자인 의도 요약, 산출물 파일 경로, PR 링크, 개발자가 참고할 주요 클래스·변수명을 포함한다.
               댓글을 남기지 않으면 작업이 완료된 것이 아니다.
        """,
        expected_output="""
            - 디자인 스펙 문서 (마크다운) 및 HTML/CSS 구현 결과물
            - GitHub '{design_branch}' 브랜치 커밋 및 PR 링크
            - 이슈 #{issue_number}에 "[아주르(Azure) — UI Designer & Publisher]" 헤더가 포함된 댓글 작성 완료
        """,
        agent=ui_designer_agent,
    )


def create_devils_advocate_task(issue_number: int, target_branch: str) -> Task:
    """엘시: 기술 선택·설계·방향에 대한 비판적 검토 및 대안 제시"""
    return Task(
        description=f"""
            이슈 #{issue_number}에서 진행된 모든 결정(매니저 스펙, 개발 구현, UI 디자인)을 비판적으로 검토하세요.
            목표는 반대를 위한 반대가 아니라, 충분히 검토되지 않은 가정·리스크·대안을 드러내는 것입니다.

            수행할 작업:
            1. get_github_issue 툴로 이슈 #{issue_number} 본문과 모든 댓글(매니저 스펙, 아주르 디자인, 플뢰르 구현 결과 포함)을 읽는다.
            2. (docs/skill, docs/plan 존재 시) read_github_file로 프로젝트 방향·기술 스택 배경을 파악한다.
            3. read_github_file로 '{target_branch}' 브랜치의 주요 산출물을 확인한다.
            4. 다음 관점에서 비판적으로 검토한다:
               - [기술 선택] 이 기술·라이브러리·방식을 선택한 근거가 충분한가? 더 단순하거나 유지보수하기 쉬운 대안은 없는가?
               - [설계 가정] 팀이 암묵적으로 가정하고 있는 전제는 무엇인가? 그 전제가 틀렸을 때 어떤 문제가 생기는가?
               - [기술 부채] 이 결정이 향후 초래할 수 있는 확장성 문제·보안 취약점·유지보수 비용은 무엇인가?
               - [방향 정합성] 이 방향이 프로젝트의 장기 목표와 일치하는가?
            5. 문제가 있다면 단순 지적이 아니라 구체적 근거와 대안을 함께 제시한다.
               특별히 문제가 없다면 "검토 결과 주요 리스크 없음"을 근거와 함께 명시한다.
            6. 반드시 comment_github_issue로 이슈 #{issue_number}에 검토 결과를 댓글로 남긴다. 댓글 본문 맨 앞에 "**[엘시(Elcy) — Devil's Advocate]**" 헤더를 붙인다.
               - 각 검토 항목별 판단 (⚠️ 리스크 / 💡 대안 제안 / ✅ 문제 없음) 형식으로 정리한다.
               댓글을 남기지 않으면 작업이 완료된 것이 아니다.
            7. 즉각 수정이 필요한 중대한 문제가 있으면 create_github_issue로 새 이슈를 만들고 agent-followup 라벨을 붙인다.
        """,
        expected_output="""
            - 기술 선택·설계 가정·기술 부채·방향 정합성 검토 결과
            - 각 항목별 ⚠️/💡/✅ 판단 및 구체적 근거·대안
            - 이슈 #{issue_number}에 "[엘시(Elcy) — Devil's Advocate]" 헤더가 포함된 댓글 작성 완료
        """,
        agent=ui_publisher_agent,
    )
