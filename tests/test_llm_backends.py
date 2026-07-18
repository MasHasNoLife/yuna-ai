from yuna.core.llm_backends import google_generation_config, to_google_contents


def test_roles_mapped():
    contents = to_google_contents(
        [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello!"},
            {"role": "user", "content": "how are you"},
        ]
    )
    assert [c["role"] for c in contents] == ["user", "model", "user"]
    assert contents[1]["parts"][0]["text"] == "hello!"


def test_system_folded_into_first_user_turn():
    contents = to_google_contents(
        [
            {"role": "system", "content": "You are Yuna."},
            {"role": "user", "content": "hi"},
            {"role": "user", "content": "second"},
        ]
    )
    assert len(contents) == 2
    first = contents[0]["parts"][0]["text"]
    assert "You are Yuna." in first and "hi" in first
    # Only the first user turn carries the system text
    assert "You are Yuna." not in contents[1]["parts"][0]["text"]


def test_system_only_history_still_produces_user_turn():
    contents = to_google_contents([{"role": "system", "content": "sys"}])
    assert len(contents) == 1
    assert contents[0]["role"] == "user"
    assert "sys" in contents[0]["parts"][0]["text"]


def test_no_system_passthrough():
    contents = to_google_contents([{"role": "user", "content": "plain"}])
    assert contents == [{"role": "user", "parts": [{"text": "plain"}]}]


def test_generation_config_mapping():
    cfg = google_generation_config({"temperature": 0.8, "top_p": 0.9, "repeat_penalty": 1.15})
    assert cfg == {"temperature": 0.8, "topP": 0.9}


def test_generation_config_empty():
    assert google_generation_config({}) == {}
