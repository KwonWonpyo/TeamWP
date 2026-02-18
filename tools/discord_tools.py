"""
tools/discord_tools.py

Discord Bot API를 사용하는 툴. 채널에 메시지 전송 등.
DISCORD_BOT_TOKEN(및 필요 시 DISCORD_CHANNEL_ID)이 설정된 경우에만 사용 가능.
"""

import os
from typing import Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

try:
    import requests
except ImportError:
    requests = None

DISCORD_API_BASE = "https://discord.com/api/v10"


def _discord_headers() -> dict:
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        return {}
    return {"Authorization": f"Bot {token}", "Content-Type": "application/json"}


# ─────────────────────────────────────────────
# 채널에 메시지 전송
# ─────────────────────────────────────────────
class SendDiscordMessageInput(BaseModel):
    content: str = Field(description="전송할 메시지 내용 (최대 2000자)")
    channel_id: Optional[str] = Field(
        default=None,
        description="채널 ID. 비우면 .env의 DISCORD_CHANNEL_ID 사용",
    )


class SendDiscordMessageTool(BaseTool):
    name: str = "send_discord_message"
    description: str = "Discord 채널에 메시지를 전송합니다. 작업 완료 알림·요약 공유 등에 사용."
    args_schema: type[BaseModel] = SendDiscordMessageInput

    def _run(self, content: str, channel_id: Optional[str] = None) -> str:
        if not requests:
            return "requests 패키지가 필요합니다: pip install requests"
        headers = _discord_headers()
        if not headers:
            return "DISCORD_BOT_TOKEN이 설정되지 않았습니다. .env에 넣으세요."
        cid = channel_id or os.getenv("DISCORD_CHANNEL_ID")
        if not cid:
            return "channel_id를 인자로 넘기거나 .env에 DISCORD_CHANNEL_ID를 설정하세요."
        if len(content) > 2000:
            content = content[:1997] + "..."
        try:
            r = requests.post(
                f"{DISCORD_API_BASE}/channels/{cid}/messages",
                headers=headers,
                json={"content": content},
                timeout=10,
            )
            r.raise_for_status()
            return f"메시지 전송 완료 (채널 {cid})"
        except Exception as e:
            return f"Discord API 오류: {e}"
