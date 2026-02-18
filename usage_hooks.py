"""
usage_hooks.py

CrewAI LLM 호출 전/후 훅: 토큰 사용량 집계, 상한 초과 시 호출 차단.
main에서 한 번 등록하면 모든 크루 실행에 적용됨.
"""

import threading

# tiktoken은 선택 의존: 없으면 토큰 수 대신 글자 수 근사
try:
    import tiktoken
    _encoding = None

    def _get_encoding():
        global _encoding
        if _encoding is None:
            try:
                _encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                _encoding = False
        return _encoding if _encoding else None

    def count_tokens(text: str) -> int:
        enc = _get_encoding()
        if enc:
            return len(enc.encode(text or ""))
        return max(0, (len(text or "") * 4) // 3)  # 대략적 근사
except ImportError:
    def count_tokens(text: str) -> int:
        return max(0, (len(text or "") * 4) // 3)


def _before_llm_call(context):
    """상한 초과 시 LLM 호출 차단."""
    from usage_tracking import is_over_limit
    if is_over_limit():
        return False
    return None


def _after_llm_call(context):
    """호출 후 입력/출력 토큰 집계."""
    from usage_tracking import add_usage
    try:
        input_tokens = 0
        for msg in (getattr(context, "messages", None) or []):
            content = msg.get("content", "") if isinstance(msg, dict) else ""
            if isinstance(content, str):
                input_tokens += count_tokens(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        input_tokens += count_tokens(part["text"])
        output_tokens = count_tokens(getattr(context, "response", None) or "")
        add_usage(input_tokens=input_tokens, output_tokens=output_tokens)
    except Exception:
        add_usage(input_tokens=0, output_tokens=0)
    return None


_hooks_registered = False
_hooks_lock = threading.Lock()


def register_usage_hooks() -> None:
    """CrewAI 전역 before/after LLM 훅 등록. 한 번만 호출."""
    global _hooks_registered
    with _hooks_lock:
        if _hooks_registered:
            return
        try:
            from crewai.hooks import (
                register_before_llm_call_hook,
                register_after_llm_call_hook,
            )
            register_before_llm_call_hook(_before_llm_call)
            register_after_llm_call_hook(_after_llm_call)
            _hooks_registered = True
        except Exception:
            pass
