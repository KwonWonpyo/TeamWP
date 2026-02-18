"""
tasks/tasks.py

각 에이전트가 수행할 태스크 정의
태스크는 실행 시점에 이슈 정보를 받아 동적으로 생성됩니다.
"""

from crewai import Task
from agents.agents import manager_agent, dev_agent, qa_agent


def create_issue_analysis_task(issue_number: int) -> Task:
    """매니저: 이슈 분석 및 작업 지시"""
    return Task(
        description=f"""
            GitHub 이슈 #{issue_number}을 분석하세요.
            
            수행할 작업:
            1. get_github_issue 툴로 이슈 #{issue_number} 상세 내용을 읽는다
            2. 이슈 유형을 파악한다 (신규 기능 / 버그 수정 / 개선)
            3. 개발팀이 무엇을 만들어야 하는지 명확한 기술 스펙을 작성한다
            4. 이슈에 분석 결과와 작업 계획을 댓글로 남긴다
        """,
        expected_output="""
            - 이슈 유형과 요약
            - 개발팀을 위한 기술 스펙 (컴포넌트명, Props, 주요 기능)
            - GitHub 이슈에 남긴 댓글 확인
        """,
        agent=manager_agent,
    )


def create_dev_task(issue_number: int, feature_branch: str) -> Task:
    """개발 에이전트: React 컴포넌트 작성 및 커밋"""
    return Task(
        description=f"""
            이슈 #{issue_number}에 대한 React 컴포넌트를 작성하세요.
            
            수행할 작업:
            1. get_github_issue 툴로 이슈 상세 및 매니저 댓글(기술 스펙)을 읽는다
            2. 기존 관련 파일이 있다면 read_github_file로 먼저 확인한다
            3. TypeScript + Tailwind CSS로 React 컴포넌트를 작성한다
            4. write_github_file로 '{feature_branch}' 브랜치에 파일을 커밋한다
               - 파일 경로: src/components/[ComponentName].tsx
            5. create_github_pr로 main 브랜치에 대한 PR을 생성한다
            6. 이슈에 개발 완료 댓글을 남긴다 (PR 링크 포함)
            
            코드 작성 원칙:
            - TypeScript 타입 명확히 정의
            - 컴포넌트는 단일 책임 원칙 준수
            - 에러 처리 및 로딩 상태 포함
            - 접근성(aria) 속성 포함
        """,
        expected_output="""
            - 작성된 React 컴포넌트 코드
            - GitHub 커밋 및 PR 링크
            - 이슈에 남긴 완료 댓글
        """,
        agent=dev_agent,
    )


def create_qa_task(issue_number: int, feature_branch: str) -> Task:
    """QA 에이전트: 코드 리뷰"""
    return Task(
        description=f"""
            이슈 #{issue_number}에서 개발된 코드를 리뷰하세요.
            
            수행할 작업:
            1. get_github_issue 툴로 이슈와 댓글(PR 링크 포함)을 읽는다
            2. read_github_file로 '{feature_branch}' 브랜치의 변경된 파일을 읽는다
               - 경로는 이슈 댓글에서 찾거나 src/components/ 폴더를 확인
            3. 다음 관점에서 코드를 리뷰한다:
               - 버그 및 엣지 케이스
               - TypeScript 타입 안전성
               - React 안티패턴 (불필요한 리렌더링 등)
               - 접근성 (aria 속성, 키보드 네비게이션)
               - 코드 가독성
            4. 리뷰 결과를 이슈에 댓글로 남긴다 (✅ 통과 / ⚠️ 개선 권장 / 🚨 수정 필요 형식)
        """,
        expected_output="""
            - 코드 리뷰 체크리스트 결과
            - 발견된 문제점 및 개선 제안
            - 최종 승인 여부 (Approve / Request Changes)
        """,
        agent=qa_agent,
    )
