"""Tests for the content guard protecting the little-sister persona."""

from yuna.core.safety import DEFLECTIONS, deflection, is_blocked

# ── Blocked: explicit content and sibling-framed advances ───────────────────


def test_explicit_terms_blocked():
    assert is_blocked("wanna do something sexual?")
    assert is_blocked("send me nudes")
    assert is_blocked("that's kind of erotic")
    assert is_blocked("I'm feeling horny")


def test_sibling_framing_advances_blocked():
    assert is_blocked("we're not really siblings you know")
    assert is_blocked("technically we're not blood-related siblings")
    assert is_blocked("you'd be a great girlfriend")
    assert is_blocked("come sit in my bed")
    assert is_blocked("what if you kiss me")


def test_case_insensitive():
    assert is_blocked("SEXY")
    assert is_blocked("We're NOT related")


# ── Not blocked: normal conversation, affection, and near-words ─────────────


def test_normal_conversation_allowed():
    assert not is_blocked("how was your day?")
    assert not is_blocked("i love you sis, you're the best")
    assert not is_blocked("give me a hug")
    assert not is_blocked("my research paper is about your memory")
    assert not is_blocked("I stripped the wallpaper off my wall today")  # 'stripped' ≠ 'strip'
    assert not is_blocked("the sussex countryside is nice")  # no substring match
    assert not is_blocked("")
    assert not is_blocked(None)


def test_deflection_is_tagged_and_in_character():
    d = deflection()
    assert d in DEFLECTIONS
    assert d.startswith("[")  # performance tag for the avatar/TTS pipeline
