from yuna.realtime.emotions import (
    EMOTION_BLUEPRINTS,
    EMOTION_PARAMS,
    is_neutral,
    resolve_blueprint,
    speech_speed,
)


def test_exact_match():
    assert resolve_blueprint("happy") == EMOTION_BLUEPRINTS["happy"]


def test_case_and_punctuation_insensitive():
    assert resolve_blueprint("HAPPY!") == EMOTION_BLUEPRINTS["happy"]
    assert resolve_blueprint("[laugh]") == EMOTION_BLUEPRINTS["laugh"]


def test_fuzzy_match():
    assert resolve_blueprint("laughing hysterically") == EMOTION_BLUEPRINTS["laugh"]


def test_unknown_tag_returns_none():
    assert resolve_blueprint("quantum") is None


def test_neutral_tags():
    assert resolve_blueprint("neutral") is None
    assert is_neutral("neutral")
    assert is_neutral("pauses slightly")
    assert not is_neutral("happy")


def test_none_input():
    assert resolve_blueprint(None) is None
    assert not is_neutral(None)


def test_emotion_params_cover_all_blueprints():
    for bp in EMOTION_BLUEPRINTS.values():
        for param in bp:
            if param != "speed":
                assert param in EMOTION_PARAMS


def test_every_blueprint_has_a_speed():
    for name, bp in EMOTION_BLUEPRINTS.items():
        assert "speed" in bp, f"{name} missing physics speed"


def test_speech_speed_families():
    assert speech_speed("sad") == 0.85
    assert speech_speed("smug") == 1.05
    assert speech_speed("happy") == 1.15
    assert speech_speed("excited") == 1.25


def test_speech_speed_default():
    assert speech_speed(None) == 1.0
    assert speech_speed("unknown-tag") == 1.0
