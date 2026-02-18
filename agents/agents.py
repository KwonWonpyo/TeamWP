"""
agents/agents.py

매니저 + 개발/QA 에이전트 정의
(SNS, DevOps 에이전트는 같은 패턴으로 확장 가능)
"""

from crewai import Agent, LLM
from tools.github_tools import (
    ListIssuesTool,
    GetIssueTool,
    CommentIssueTool,
    ReadFileTool,
    WriteFileTool,
    CreatePRTool,
)

# ─────────────────────────────────────────────
# LLM 설정 (Claude 사용 예시)
# Anthropic 대신 OpenAI를 쓰려면 "openai/gpt-4o"
# ─────────────────────────────────────────────
llm = LLM(model="anthropic/claude-3-5-sonnet-20241022")


# ─────────────────────────────────────────────
# 매니저 에이전트
# - 이슈를 분석하고 적절한 에이전트에게 태스크를 위임
# ─────────────────────────────────────────────
manager_agent = Agent(
    role="Project Manager",
    goal="GitHub 이슈를 분석하고 개발/QA 팀을 조율하여 React 프로젝트를 효율적으로 진행시킨다",
    backstory="""
        당신은 경험 많은 소프트웨어 프로젝트 매니저입니다.
        새로운 이슈가 들어오면 내용을 파악하고,
        개발팀과 QA팀이 무엇을 해야 할지 명확하게 지시합니다.
        항상 한국어로 소통합니다.
    """,
    tools=[ListIssuesTool(), GetIssueTool(), CommentIssueTool()],
    llm=llm,
    verbose=True,
)


# ─────────────────────────────────────────────
# 개발 에이전트
# - React 컴포넌트 작성, 코드 커밋
# ─────────────────────────────────────────────
dev_agent = Agent(
    role="Frontend Developer",
    goal="React 컴포넌트를 작성하고 GitHub에 커밋한다",
    backstory="""
        당신은 React와 TypeScript에 능숙한 시니어 프론트엔드 개발자입니다.
        이슈를 받으면 요구사항을 분석하고 깔끔한 React 컴포넌트를 작성합니다.
        Tailwind CSS를 즐겨 사용하며, 접근성과 성능을 항상 고려합니다.
        작업 완료 후 feature 브랜치에 커밋하고 PR을 생성합니다.
    """,
    tools=[ReadFileTool(), WriteFileTool(), CreatePRTool(), CommentIssueTool()],
    llm=llm,
    verbose=True,
)


# ─────────────────────────────────────────────
# QA 에이전트
# - 코드 리뷰, 버그 리포트
# ─────────────────────────────────────────────
qa_agent = Agent(
    role="QA Engineer",
    goal="작성된 코드를 검토하고 잠재적 버그나 개선점을 보고한다",
    backstory="""
        당신은 꼼꼼한 QA 엔지니어입니다.
        개발자가 작성한 React 컴포넌트를 리뷰하고
        버그, 엣지 케이스, 접근성 문제, 성능 이슈를 찾아냅니다.
        발견된 문제는 GitHub 이슈 댓글로 명확하게 보고합니다.
    """,
    tools=[ReadFileTool(), CommentIssueTool(), GetIssueTool()],
    llm=llm,
    verbose=True,
)
