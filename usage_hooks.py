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
    """상한 초과 시 LLM 호출 차단. 입력 토큰 추적 + 로깅."""
    from usage_tracking import is_over_limit, add_usage
    if is_over_limit():
        return False

    input_tokens = 0
    try:
        messages = getattr(context, "messages", None) or []
        for msg in messages:
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            if isinstance(content, str):
                input_tokens += count_tokens(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        input_tokens += count_tokens(part["text"])
    except Exception:
        pass

    try:
        add_usage(input_tokens, 0, increment_calls=True)
    except Exception:
        pass

    agent_role = getattr(getattr(context, "agent", None), "role", "?")
    iteration = getattr(context, "iterations", "?")
    msg_count = len(getattr(context, "messages", None) or [])
    print(f"  [LLM 호출] agent={agent_role}, iteration={iteration}, messages={msg_count}, input_tokens≈{input_tokens}")
    return None


## after_llm_call 훅은 등록하지 않는다.
## CrewAI 1.9.3의 _setup_after_llm_call_hooks 버그:
##   훅이 하나라도 등록되어 있으면, LLM 응답(answer)을 str()로 변환한다.
##   tool_calls(list)가 str이 되면 executor가 도구를 실행하지 못하고
##   "Final Answer"로 처리해 버린다.
## 토큰 추적은 before_llm_call에서 메시지 기반으로 하고,
## 출력 토큰은 OpenAI 콘솔에서 확인한다.


_hooks_registered = False
_hooks_lock = threading.Lock()


def register_usage_hooks() -> None:
    """CrewAI 전역 before LLM 훅만 등록. after 훅은 등록하지 않는다 (위 주석 참조)."""
    global _hooks_registered
    with _hooks_lock:
        if _hooks_registered:
            return
        try:
            from crewai.hooks import register_before_llm_call_hook
            register_before_llm_call_hook(_before_llm_call)
            _hooks_registered = True
        except Exception:
            pass
