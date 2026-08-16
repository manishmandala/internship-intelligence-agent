"""Tests for the Workday collector's pure-logic helpers (no network calls)."""
from __future__ import annotations

from datetime import date, timedelta

from src.collectors.workday import _parse_relative_posted_date


def test_parses_today():
    assert _parse_relative_posted_date("Posted Today") == date.today().isoformat()


def test_parses_yesterday():
    expected = (date.today() - timedelta(days=1)).isoformat()
    assert _parse_relative_posted_date("Posted Yesterday") == expected


def test_parses_n_days_ago():
    expected = (date.today() - timedelta(days=7)).isoformat()
    assert _parse_relative_posted_date("Posted 7 Days Ago") == expected


def test_parses_n_plus_days_ago():
    expected = (date.today() - timedelta(days=30)).isoformat()
    assert _parse_relative_posted_date("Posted 30+ Days Ago") == expected


def test_returns_none_for_unrecognized_text():
    assert _parse_relative_posted_date("Some other text") is None


def test_returns_none_for_empty_input():
    assert _parse_relative_posted_date(None) is None
    assert _parse_relative_posted_date("") is None
