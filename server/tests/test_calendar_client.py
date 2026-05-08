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
        {"time": "09:00", "title": "Standup", "durationMin": 30},
        {"time": "11:30", "title": "Lunch", "durationMin": 60},
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
