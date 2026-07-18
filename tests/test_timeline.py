from yuna.reactions.timeline import build_timeline, extract_dialogue_lines, numbered_output_path


def test_build_timeline_interleaves_by_timestamp():
    visuals = [(0.0, "[0s] A cat appears"), (10.0, "[10s] The cat falls")]
    audio = [(5.0, "watch this")]
    result = build_timeline(visuals, audio).splitlines()
    assert result == ["[0s] A cat appears", '[SPEECH] "watch this"', "[10s] The cat falls"]


def test_build_timeline_no_audio():
    visuals = [(3.0, "[3s] Something happens")]
    assert build_timeline(visuals, None) == "[3s] Something happens"


def test_build_timeline_empty():
    assert build_timeline([], None) == ""


def test_extract_dialogue_skips_markers_and_blanks():
    script = "\n".join(
        [
            "[TIMESTAMP 0:00]",
            "Oh wow, okay, we're doing this.",
            "",
            "[DESCRIPTOR cat falls]",
            "No way, did you see that?!",
        ]
    )
    assert extract_dialogue_lines(script) == [
        "Oh wow, okay, we're doing this.",
        "No way, did you see that?!",
    ]


def test_numbered_output_path_increments(tmp_path):
    first = numbered_output_path(tmp_path, "reaction")
    assert first.name == "reaction.txt"
    first.write_text("x")
    second = numbered_output_path(tmp_path, "reaction")
    assert second.name == "reaction1.txt"
    second.write_text("x")
    assert numbered_output_path(tmp_path, "reaction").name == "reaction2.txt"
