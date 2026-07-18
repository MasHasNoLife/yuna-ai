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
    assert p == "(Saturday night, July 18)"


def test_time_preamble_morning():
    p = time_preamble(datetime(2026, 7, 20, 9, 0))
    assert "Monday morning" in p


def test_time_preamble_late_night():
    p = time_preamble(datetime(2026, 7, 19, 2, 30))
    assert "late night" in p
