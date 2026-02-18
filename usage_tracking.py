"""
usage_tracking.py

LLM 사용량(토큰/호출 횟수) 추적, 상한 검사, 초과 시 Discord 알림.
대시보드에서 조회·리셋 가능. JSON 파일로 영속화.
"""

import os
import json
import threading
from pathlib import Path

# 기본 저장 경로: 프로젝트 루트의 .agent_usage.json
def _usage_file() -> Path:
    return Path(__file__).resolve().parent / ".agent_usage.json"

_lock = threading.Lock()
_limit_exceeded_notified = False  # 이번 기간 내 상한 초과 알림 1회만


def _load() -> dict:
    p = _usage_file()
    if not p.exists():
        return {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "input_tokens": int(data.get("input_tokens", 0)),
            "output_tokens": int(data.get("output_tokens", 0)),
            "calls": int(data.get("calls", 0)),
        }
    except Exception:
        return {"input_tokens": 0, "output_tokens": 0, "calls": 0}


def _save(data: dict) -> None:
    p = _usage_file()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_limits_from_env() -> tuple[int | None, int | None]:
    """(token_limit, call_limit). 없으면 None."""
    token_limit = os.getenv("USAGE_LIMIT_TOKENS")
    call_limit = os.getenv("USAGE_LIMIT_CALLS")
    t = int(token_limit) if token_limit and token_limit.isdigit() else None
    c = int(call_limit) if call_limit and call_limit.isdigit() else None
    return (t, c)


def add_usage(
    input_tokens: int = 0,
    output_tokens: int = 0,
    increment_calls: bool = True,
) -> None:
    """토큰 사용량 누적. increment_calls=True이면 calls +1 (기본값)."""
    global _limit_exceeded_notified
    with _lock:
        data = _load()
        data["input_tokens"] = data.get("input_tokens", 0) + input_tokens
        data["output_tokens"] = data.get("output_tokens", 0) + output_tokens
        if increment_calls:
            data["calls"] = data.get("calls", 0) + 1
        _save(data)

        token_limit, call_limit = get_limits_from_env()
        over = False
        if token_limit is not None and (data["input_tokens"] + data["output_tokens"]) >= token_limit:
            over = True
        if call_limit is not None and data["calls"] >= call_limit:
            over = True
        if over and not _limit_exceeded_notified:
            _limit_exceeded_notified = True
            _send_discord_alert(data, token_limit, call_limit)


def is_over_limit() -> bool:
    """현재 사용량이 상한을 초과했으면 True."""
    token_limit, call_limit = get_limits_from_env()
    if token_limit is None and call_limit is None:
        return False
    with _lock:
        data = _load()
    total = data.get("input_tokens", 0) + data.get("output_tokens", 0)
    if token_limit is not None and total >= token_limit:
        return True
    if call_limit is not None and data.get("calls", 0) >= call_limit:
        return True
    return False


def get_usage() -> dict:
    """대시보드/API용: 사용량·상한·초과 여부·비용 추정.
    calls = LLM 호출 시도 횟수 (before 훅에서 카운트. API 실패 시에도 1회로 집계됨).
    """
    with _lock:
        data = _load()
    token_limit, call_limit = get_limits_from_env()
    total_tokens = data.get("input_tokens", 0) + data.get("output_tokens", 0)
    calls = data.get("calls", 0)

    over = False
    if token_limit is not None and total_tokens >= token_limit:
        over = True
    if call_limit is not None and calls >= call_limit:
        over = True

    estimate_usd = _estimate_cost(data.get("input_tokens", 0), data.get("output_tokens", 0))

    return {
        "input_tokens": data.get("input_tokens", 0),
        "output_tokens": data.get("output_tokens", 0),
        "total_tokens": total_tokens,
        "calls": calls,
        "limit_tokens": token_limit,
        "limit_calls": call_limit,
        "limit_exceeded": over,
        "cost_estimate_usd": round(estimate_usd, 4),
    }


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """모델별 1K 토큰 단가로 대략적인 USD 추정. .env LLM_COST_MODEL 미설정 시 gpt-4o 기준."""
    # gpt-4o (2024): input $2.50/1M, output $10/1M
    # claude-3-5-sonnet: input $3/1M, output $15/1M
    model = (os.getenv("LLM_COST_MODEL") or "gpt-4o").lower()
    if "claude" in model or "anthropic" in model:
        return (input_tokens / 1_000_000) * 3.0 + (output_tokens / 1_000_000) * 15.0
    return (input_tokens / 1_000_000) * 2.5 + (output_tokens / 1_000_000) * 10.0


def send_discord_run_failed(issue_number: int, error_message: str) -> None:
    """이슈 처리 중 LLM/실행 실패 시 Discord 채널에 알림 전송. DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID 필요."""
    try:
        import requests
    except ImportError:
        return
    token = os.getenv("DISCORD_BOT_TOKEN")
    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    if not token or not channel_id:
        return
    body = f"❌ **이슈 #{issue_number} 처리 실패**\n{error_message[:1500]}"
    if len(error_message) > 1500:
        body += "..."
    try:
        requests.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            json={"content": body},
            timeout=10,
        )
    except Exception:
        pass


def _send_discord_alert(data: dict, token_limit: int | None, call_limit: int | None) -> None:
    """상한 초과 시 Discord 채널에 알림 1회 전송."""
    try:
        import requests
    except ImportError:
        return
    token = os.getenv("DISCORD_BOT_TOKEN")
    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    if not token or not channel_id:
        return
    total = data.get("input_tokens", 0) + data.get("output_tokens", 0)
    calls = data.get("calls", 0)
    parts = ["⚠️ **Agent Team 사용량 상한 초과**"]
    if token_limit is not None:
        parts.append(f"토큰: {total:,} / {token_limit:,}")
    if call_limit is not None:
        parts.append(f"호출: {calls} / {call_limit}")
    parts.append("새 LLM 호출은 차단됩니다. 사용량을 리셋하거나 상한을 올려주세요.")
    body = "\n".join(parts)
    if len(body) > 2000:
        body = body[:1997] + "..."
    try:
        requests.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            json={"content": body},
            timeout=10,
        )
    except Exception:
        pass


def reset_usage() -> None:
    """사용량을 0으로 초기화. 상한 초과 알림 플래그도 리셋."""
    global _limit_exceeded_notified
    with _lock:
        _save({"input_tokens": 0, "output_tokens": 0, "calls": 0})
        _limit_exceeded_notified = False
