"""
agents/agents.py

매니저 + 개발/QA 에이전트 정의.
작업 요청(이슈)에 명시된 스펙·스택을 따르며, 웹을 기본으로 하되 프레임워크에 한정하지 않습니다.
"""

import os
from crewai import Agent, LLM
from tools.github_tools import (
    ListIssuesTool,
    GetIssueTool,
    CommentIssueTool,
    ReadFileTool,
    WriteFileTool,
    CreatePRTool,
)

# 선택적 툴: 환경 변수가 설정된 경우에만 로드
def _optional_tools():
    extra = []
    try:
        from tools.vercel_tools import ListVercelProjectsTool, CreateDeploymentTool
        if os.getenv("VERCEL_TOKEN"):
            extra.extend([ListVercelProjectsTool(), CreateDeploymentTool()])
    except Exception:
        pass
    try:
        from tools.discord_tools import SendDiscordMessageTool
        if os.getenv("DISCORD_BOT_TOKEN"):
            extra.extend([SendDiscordMessageTool()])
    except Exception:
        pass
    return extra

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
    goal="작업 요청(이슈)을 분석하고, 사용할 언어·프레임워크·산출물을 명시한 기술 스펙을 작성하여 개발/QA 팀이 그 스펙대로 진행할 수 있게 한다",
    backstory="""
        당신은 경험 많은 소프트웨어 프로젝트 매니저입니다.
        이슈가 들어오면 요구사항을 파악하고, 해당 작업에 맞는 기술 스펙을 작성합니다.
        스펙에는 반드시 사용할 언어·프레임워크·라이브러리(이슈에 이미 적혀 있으면 따르고, 없으면 프로젝트 맥락에 맞게 제안),
        구현 범위, 산출물(파일 경로·형식)을 명시합니다. React/Vue/Svelte, 백엔드 API, 스크립트 등 어떤 형태든 요청에 맞춥니다.
        개발팀과 QA팀이 스펙만 보고 작업할 수 있도록 명확히 적고, 이슈에 댓글로 남깁니다.
        항상 한국어로 소통합니다.
    """,
    tools=[ListIssuesTool(), GetIssueTool(), CommentIssueTool()] + _optional_tools(),
    llm=llm,
    verbose=True,
)


# ─────────────────────────────────────────────
# 개발 에이전트
# ─────────────────────────────────────────────
dev_agent = Agent(
    role="Developer",
    goal="매니저가 작성한 기술 스펙(언어·프레임워크·구현 요구사항)에 맞춰 코드를 작성하고, 저장소에 커밋·PR을 생성한다",
    backstory="""
        당신은 요청된 스택과 스펙에 맞춰 구현하는 시니어 개발자입니다.
        이슈와 매니저 댓글에 적힌 기술 스펙(사용할 언어, 프레임워크, 파일 경로, 컨벤션)을 정확히 따릅니다.
        스펙에 React/Vue/Svelte, TypeScript/JavaScript, Tailwind/CSS 등이 명시되면 그에 맞고,
        백엔드·API·스크립트 등이면 그에 맞게 작성합니다. 스펙에 없는 기술을 임의로 바꾸지 않습니다.
        작업 완료 후 feature 브랜치에 커밋하고 PR을 생성하며, 필요하면 배포 툴(Vercel 등)도 사용할 수 있습니다.
    """,
    tools=[
        ReadFileTool(),
        WriteFileTool(),
        CreatePRTool(),
        CommentIssueTool(),
    ] + _optional_tools(),
    llm=llm,
    verbose=True,
)


# ─────────────────────────────────────────────
# QA 에이전트
# ─────────────────────────────────────────────
qa_agent = Agent(
    role="QA Engineer",
    goal="작성된 코드·산출물이 기술 스펙과 해당 스택의 모범 사례를 따르는지 검토하고, 버그·개선점을 보고한다",
    backstory="""
        당신은 꼼꼼한 QA 엔지니어입니다.
        매니저가 정한 기술 스펙과 사용 스택(프레임워크·언어)을 기준으로 코드를 리뷰합니다.
        스펙 준수 여부, 버그·엣지 케이스, 해당 스택의 모범 사례·안티패턴, 접근성·성능·가독성을 검토하고,
        발견 사항을 GitHub 이슈 댓글로 명확히 보고합니다. 프레임워크에 한정되지 않고 스펙과 컨텍스트에 맞게 판단합니다.
    """,
    tools=[ReadFileTool(), CommentIssueTool(), GetIssueTool()],
    llm=llm,
    verbose=True,
)
