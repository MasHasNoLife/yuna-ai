"""Pure-logic tests for the session memory helpers (no GPU/DB required)."""

import time
from datetime import datetime

from yuna.core.chat_session import build_recall_query, time_preamble
from yuna.core.memory import format_age

DAY = 86400


# ── format_age ───────────────────────────────────────────────────────────────


def test_format_age_unknown():
    assert format_age(None) == ""
    assert format_age(0) == ""


def test_format_age_today_and_yesterday():
    now = time.time()
    assert format_age(now - 3600, now) == "earlier today"
    assert format_age(now - DAY - 3600, now) == "yesterday"


def test_format_age_days_weeks_months():
    now = time.time()
    assert format_age(now - 3 * DAY - 60, now) == "3 days ago"
    assert format_age(now - 21 * DAY, now) == "3 weeks ago"
    assert format_age(now - 90 * DAY, now) == "3 months ago"


# ── build_recall_query ──────────────────────────────────────────────────────


def test_recall_query_includes_previous_message():
    q = build_recall_query(
        "no the personal project i told you about earlier",
        ["do you remember about some project"],
    )
    assert "do you remember about some project" in q
    assert "personal project" in q


def test_recall_query_first_turn():
    assert build_recall_query("hi yuna", []) == "hi yuna"


def test_recall_query_only_uses_last_previous():
    q = build_recall_query("current", ["oldest", "latest"])
    assert "oldest" not in q
    assert "latest" in q


def test_recall_query_capped():
    q = build_recall_query("x" * 1000, ["y" * 1000])
    assert len(q) <= 400


# ── time_preamble ───────────────────────────────────────────────────────────


def test_time_preamble_night():
    p = time_preamble(datetime(2026, 7, 18, 23, 54))
    assert p == "(Saturday night, July 18, 11:54 pm)"


def test_time_preamble_morning():
    p = time_preamble(datetime(2026, 7, 20, 9, 0))
    assert "Monday morning" in p


def test_time_preamble_late_night():
    p = time_preamble(datetime(2026, 7, 19, 2, 30))
    assert "late night" in p


# ── remember-question grounding ─────────────────────────────────────────────


def test_remember_questions_detected():
    from yuna.core.chat_session import REMEMBER_RE

    assert REMEMBER_RE.search("do you remember us playing a game earlier today")
    assert REMEMBER_RE.search("remember when we went to the lake?")
    assert REMEMBER_RE.search("didn't we talk about this yesterday")
    assert REMEMBER_RE.search("that time we stayed up all night")


def test_normal_messages_not_flagged_as_remember():
    from yuna.core.chat_session import REMEMBER_RE

    assert not REMEMBER_RE.search("what are we gonna be doing later?")
    assert not REMEMBER_RE.search("i had a rough day at work")
    assert not REMEMBER_RE.search("can you remember this for later: i hate mondays")


# ── age annotation must not contradict an in-text date ───────────────────────


def test_no_age_prefix_when_text_has_absolute_date():
    from yuna.core.memory import _HAS_ABS_DATE

    # events carrying their own date should be detected (age prefix suppressed)
    assert _HAS_ABS_DATE.search("Mas and Yuna last spoke (on 19 July 2026).")
    assert _HAS_ABS_DATE.search("ran a charity race (on 20 May 2023)")
    # plain facts / undated summaries are not
    assert not _HAS_ABS_DATE.search("Yuna has a sketchbook")
    assert not _HAS_ABS_DATE.search("they talked about the project")


# ── per-user memory isolation ────────────────────────────────────────────────


def test_partition_mapping():
    from yuna.core.chat_session import ChatSession

    assert ChatSession._partition("Mas") == "global"
    assert ChatSession._partition("mas") == "global"
    assert ChatSession._partition("") == "global"
    assert ChatSession._partition("Alex") == "u:alex"
    assert ChatSession._partition("  Bob  ") == "u:bob"


def test_set_user_switches_partition_and_resets():
    from yuna.core.chat_session import ChatSession

    s = ChatSession(username="Mas")
    assert s.mem_partition == "global"
    s.exchanges.append(("hi", "hey"))
    s.set_user("Alex")
    assert s.username == "Alex"
    assert s.mem_partition == "u:alex"
    assert s.exchanges == []  # fresh history for the new person
    assert s._continuity_loaded is False
