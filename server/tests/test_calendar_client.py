"""Tests for the Google Calendar client.

The client is exercised against a mocked Google API service so tests don't
require real credentials. We verify the projection from the raw API
response into the panel-ready entries list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from server.calendar_client import CalendarClient, project_events


def _evt(start: str, end: str, summary: str = "X") -> dict[str, Any]:
    return {
        "summary": summary,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }


def test_project_events_basic() -> None:
    raw = [
        _evt("2026-05-08T09:00:00+00:00", "2026-05-08T09:30:00+00:00", "Standup"),
        _evt("2026-05-08T11:30:00+00:00", "2026-05-08T12:30:00+00:00", "Lunch"),
    ]
    out = project_events(raw)
    assert out == [
        {"time": "09:00", "title": "Standup", "durationMin": 30, "attendees": [], "room": None},
        {"time": "11:30", "title": "Lunch", "durationMin": 60, "attendees": [], "room": None},
    ]


def test_project_events_filters_all_day_events() -> None:
    raw = [
        {"summary": "Holiday", "start": {"date": "2026-05-08"}, "end": {"date": "2026-05-09"}},
        _evt("2026-05-08T10:00:00+00:00", "2026-05-08T10:30:00+00:00", "Real"),
    ]
    out = project_events(raw)
    assert len(out) == 1
    assert out[0]["title"] == "Real"


def test_project_events_sorts_by_start_time() -> None:
    raw = [
        _evt("2026-05-08T15:00:00+00:00", "2026-05-08T15:30:00+00:00", "Late"),
        _evt("2026-05-08T09:00:00+00:00", "2026-05-08T09:30:00+00:00", "Early"),
    ]
    out = project_events(raw)
    assert [e["title"] for e in out] == ["Early", "Late"]


def test_project_events_handles_missing_summary() -> None:
    raw = [_evt("2026-05-08T09:00:00+00:00", "2026-05-08T09:30:00+00:00", "")]
    raw[0]["summary"] = ""
    out = project_events(raw)
    assert out[0]["title"] == "(no title)"


def test_project_events_empty_input() -> None:
    assert project_events([]) == []


@pytest.mark.asyncio
async def test_fetch_today_returns_empty_when_credentials_missing(tmp_path: Path) -> None:
    creds = tmp_path / "missing.json"
    token = tmp_path / "token.json"
    client = CalendarClient(credentials_path=creds, token_path=token)
    result = await client.fetch_today()
    assert result == []


@pytest.mark.asyncio
async def test_fetch_today_uses_injected_service(tmp_path: Path) -> None:
    """When a service is injected, fetch_today calls events.list and projects."""
    creds = tmp_path / "creds.json"
    token = tmp_path / "token.json"
    creds.write_text("{}")
    token.write_text("{}")

    fake_service = MagicMock()
    fake_service.events().list().execute.return_value = {
        "items": [
            _evt("2026-05-08T09:00:00+00:00", "2026-05-08T09:30:00+00:00", "Standup"),
        ]
    }

    client = CalendarClient(
        credentials_path=creds, token_path=token, service=fake_service
    )
    result = await client.fetch_today()
    assert len(result) == 1
    assert result[0]["title"] == "Standup"


@pytest.mark.asyncio
async def test_fetch_today_uses_local_timezone_bounds(tmp_path: Path) -> None:
    """Regression: PR#7 P2 — day bounds must use the local timezone, not UTC.

    Otherwise a Pacific-time user's 19:00 meeting falls outside the UTC "today"
    window. We assert the timeMin sent to the Google API carries a non-Z (i.e.
    offset-bearing) ISO timestamp on systems where local != UTC.
    """
    creds = tmp_path / "creds.json"
    token = tmp_path / "token.json"
    creds.write_text("{}")
    token.write_text("{}")

    fake_service = MagicMock()
    fake_service.events().list.return_value.execute.return_value = {"items": []}

    client = CalendarClient(
        credentials_path=creds, token_path=token, service=fake_service
    )
    await client.fetch_today()

    # Inspect the kwargs the implementation passed to events().list(...)
    list_calls = fake_service.events.return_value.list.call_args_list
    # The MagicMock chain returns the same mock for repeated `.events()` calls,
    # so the most recent call is the one we want.
    last = list_calls[-1]
    time_min: str = last.kwargs["timeMin"]
    time_max: str = last.kwargs["timeMax"]

    # timeMin/timeMax come from `.isoformat()` of an aware datetime; if they
    # were built in UTC they would carry "+00:00" only.
    import datetime as _dt

    expected_offset = _dt.datetime.now().astimezone().strftime("%z")
    # %z emits "+0200"; isoformat emits "+02:00". Reformat for comparison.
    expected_iso_offset = (
        f"{expected_offset[:3]}:{expected_offset[3:]}"
        if expected_offset
        else "+00:00"
    )
    assert time_min.endswith(expected_iso_offset), (
        f"timeMin {time_min!r} should carry local offset {expected_iso_offset!r}"
    )
    assert time_max.endswith(expected_iso_offset)
    # Sanity: both bounds start at the same local-midnight prefix
    assert "T00:00:00" in time_min


def test_project_events_includes_attendees_and_room() -> None:
    raw = [
        {
            "summary": "Design Review",
            "start": {"dateTime": "2026-05-08T14:00:00+00:00"},
            "end": {"dateTime": "2026-05-08T15:00:00+00:00"},
            "attendees": [
                {"displayName": "Alice", "email": "alice@example.com"},
                {"email": "bob@example.com"},
            ],
            "location": "Room 42",
        }
    ]
    out = project_events(raw)
    assert out[0]["attendees"] == ["Alice", "bob@example.com"]
    assert out[0]["room"] == "Room 42"


def test_project_events_attendees_defaults_to_empty() -> None:
    raw = [_evt("2026-05-08T09:00:00+00:00", "2026-05-08T09:30:00+00:00", "Solo")]
    out = project_events(raw)
    assert out[0]["attendees"] == []
    assert out[0]["room"] is None
