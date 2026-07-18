from yuna.core.history import make_history, trim_history


def _msgs(n: int) -> list[dict]:
    """System prompt + n alternating user/assistant messages."""
    out = make_history("SYSTEM")
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        out.append({"role": role, "content": f"msg{i}"})
    return out


def test_make_history():
    h = make_history("hello")
    assert h == [{"role": "system", "content": "hello"}]


def test_short_history_untouched():
    messages = _msgs(4)
    assert trim_history(messages, max_messages=10) == messages


def test_trim_keeps_system_prompt():
    trimmed = trim_history(_msgs(50), max_messages=10)
    assert trimmed[0] == {"role": "system", "content": "SYSTEM"}
    assert len(trimmed) <= 11


def test_trim_never_starts_on_assistant():
    trimmed = trim_history(_msgs(51), max_messages=10)
    assert trimmed[1]["role"] == "user"


def test_trim_keeps_most_recent():
    messages = _msgs(50)
    trimmed = trim_history(messages, max_messages=10)
    assert trimmed[-1] == messages[-1]
