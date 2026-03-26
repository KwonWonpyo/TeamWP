"""역할별 LLM 설정.

환경변수로 역할별 LLM을 지정한다. 값이 없으면 AGENT_LLM_DEFAULT → openai/gpt-4o 순서로 폴백.

환경변수 패턴:
    AGENT_LLM_VICE=openai/gpt-4o          # 바이스 (PM)
    AGENT_LLM_AZURE=openai/gpt-4o         # 아주르 (UI)
    AGENT_LLM_FLEUR=openai/gpt-4o         # 플뢰르 (Dev)
    AGENT_LLM_ELSI=openai/gpt-4o          # 엘시 (Devil's Advocate)
    AGENT_LLM_BETHEL=openai/gpt-4o-mini   # 베델 (QA)
    AGENT_LLM_DEFAULT=openai/gpt-4o       # 폴백

Claude로 전환 시: AGENT_LLM_FLEUR=anthropic/claude-opus-4-6 등으로 변경.
"""

from __future__ import annotations

import os

from crewai import LLM

from core.models import AgentRole

_ROLE_ENV_MAP: dict[AgentRole, str] = {
    AgentRole.VICE: "AGENT_LLM_VICE",
    AgentRole.AZURE: "AGENT_LLM_AZURE",
    AgentRole.FLEUR: "AGENT_LLM_FLEUR",
    AgentRole.ELSI: "AGENT_LLM_ELSI",
    AgentRole.BETHEL: "AGENT_LLM_BETHEL",
    # 레거시 이름 지원
    AgentRole.PM: "AGENT_LLM_VICE",
    AgentRole.CTO: "AGENT_LLM_VICE",
    AgentRole.DEVELOPER: "AGENT_LLM_FLEUR",
    AgentRole.QA: "AGENT_LLM_BETHEL",
    AgentRole.MARKETING: "AGENT_LLM_BETHEL",
}

_DEFAULT_MODEL = "openai/gpt-4o"


def get_llm(role: AgentRole) -> LLM:
    """환경변수 기반으로 역할별 LLM을 반환한다."""
    env_key = _ROLE_ENV_MAP.get(role, "AGENT_LLM_DEFAULT")
    model = (
        os.getenv(env_key)
        or os.getenv("AGENT_LLM_DEFAULT")
        or _DEFAULT_MODEL
    )
    return LLM(model=model)
