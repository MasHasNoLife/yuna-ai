"""Tests for the benchmark harness: scoring, LoCoMo parsing, exchange pairing."""

import json

from yuna.bench.datasets import BenchSession, BenchTurn, load_locomo
from yuna.bench.runner import _pair_exchanges
from yuna.bench.scoring import exact_match, normalize_answer, token_f1

# ── Scoring ─────────────────────────────────────────────────────────────────


def test_normalize_answer():
    assert normalize_answer("The Cat!") == "cat"
    assert normalize_answer("  a  dog ") == "dog"
    assert normalize_answer("") == ""


def test_exact_match():
    assert exact_match("The cat", "cat") == 1.0
    assert exact_match("a dog", "cat") == 0.0


def test_token_f1_perfect_and_zero():
    assert token_f1("blue car", "blue car") == 1.0
    assert token_f1("red bike", "blue car") == 0.0


def test_token_f1_partial():
    # pred has 2 tokens, gold has 3, overlap 2 -> p=1.0, r=2/3, f1=0.8
    assert abs(token_f1("blue car", "big blue car") - 0.8) < 1e-9


def test_token_f1_empty():
    assert token_f1("", "cat") == 0.0
    assert token_f1("", "") == 1.0


# ── LoCoMo loader ───────────────────────────────────────────────────────────


def _fixture(tmp_path):
    data = [
        {
            "sample_id": "conv-1",
            "conversation": {
                "speaker_a": "Ana",
                "speaker_b": "Ben",
                "session_1_date_time": "1 pm on 5 May, 2023",
                "session_1": [
                    {"speaker": "Ana", "dia_id": "D1:1", "text": "I got a puppy called Rex!"},
                    {"speaker": "Ben", "dia_id": "D1:2", "text": "Congrats!"},
                ],
                "session_2_date_time": "2 pm on 9 May, 2023",
                "session_2": [
                    {"speaker": "Ana", "dia_id": "D2:1", "blip_caption": "a dog in a park"},
                    {"speaker": "Ben", "dia_id": "D2:2", "text": "Rex looks happy."},
                ],
            },
            "qa": [
                {"question": "What is Ana's dog called?", "answer": "Rex", "category": 4},
            ],
        }
    ]
    p = tmp_path / "locomo.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_load_locomo(tmp_path):
    convs = load_locomo(_fixture(tmp_path))
    assert len(convs) == 1
    conv = convs[0]
    assert conv.id == "conv-1"
    assert conv.speaker_a == "Ana" and conv.speaker_b == "Ben"
    assert [s.index for s in conv.sessions] == [1, 2]
    assert conv.sessions[0].date == "1 pm on 5 May, 2023"
    assert conv.n_turns == 4
    # image-only turn becomes a caption line
    assert "shares a photo: a dog in a park" in conv.sessions[1].turns[0].text
    assert conv.qa[0]["answer"] == "Rex"


# ── Exchange pairing ────────────────────────────────────────────────────────


def _session(turns):
    return BenchSession(index=1, date="", turns=[BenchTurn(s, t) for s, t in turns])


def test_pair_exchanges_alternating():
    s = _session([("A", "hi"), ("B", "hello"), ("A", "how are you"), ("B", "good")])
    assert _pair_exchanges(s, "A") == [("hi", "hello"), ("how are you", "good")]


def test_pair_exchanges_joins_consecutive_same_speaker():
    s = _session([("A", "hi"), ("A", "you there?"), ("B", "yes"), ("B", "what's up")])
    assert _pair_exchanges(s, "A") == [("hi you there?", "yes what's up")]


def test_pair_exchanges_trailing_user_turn():
    s = _session([("A", "hi"), ("B", "hello"), ("A", "bye")])
    assert _pair_exchanges(s, "A") == [("hi", "hello"), ("bye", "")]


# ── Evidence-based QA filtering ─────────────────────────────────────────────


def test_qa_within_sessions():
    from yuna.bench.runner import qa_within_sessions

    assert qa_within_sessions({"evidence": ["D1:5", "D2:3"]}, 2)
    assert not qa_within_sessions({"evidence": ["D1:5", "D3:1"]}, 2)
    assert qa_within_sessions({"evidence": []}, 1)  # adversarial: keep
    assert qa_within_sessions({}, 1)
