from yuna.realtime.tags import first_tag, normalize_for_tts, split_segments, strip_tags


def test_strip_tags_removes_all_tags():
    assert strip_tags("[happy] Hello [sad] world") == "Hello world"


def test_strip_tags_plain_text_unchanged():
    assert strip_tags("no tags here") == "no tags here"


def test_first_tag():
    assert first_tag("[smug] obviously") == "smug"
    assert first_tag("no tags") is None


def test_split_segments_basic():
    assert split_segments("[happy] Hi there [sad] bye") == [("happy", "Hi there"), ("sad", "bye")]


def test_split_segments_leading_untagged_text():
    assert split_segments("intro text [laugh] haha") == [(None, "intro text"), ("laugh", "haha")]


def test_split_segments_lowercases_tags():
    assert split_segments("[HAPPY] Hi") == [("happy", "Hi")]


def test_split_segments_drops_empty_segments():
    # Adjacent tags: the first has no text and is dropped
    assert split_segments("[happy][sad] oh no") == [("sad", "oh no")]


def test_split_segments_empty_input():
    assert split_segments("") == []


def test_normalize_replaces_expressive_sounds():
    assert "humph" in normalize_for_tts("Hmph, whatever")
    assert "tsk" in normalize_for_tts("Tch, fine")
    assert "puf" in normalize_for_tts("Pfft okay")


def test_normalize_asterisk_emphasis_to_quotes():
    assert normalize_for_tts("that was *amazing* right") == "that was 'amazing' right"
