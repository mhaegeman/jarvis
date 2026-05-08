"""Google Calendar client for the Calendar HUD panel.

Reads today's primary-calendar entries via the Google Calendar API and
projects them into a panel-friendly shape:

    {time: "HH:MM", title: str, durationMin: int}

OAuth desktop flow:
  - First run pops a browser; user grants `calendar.readonly`.
  - Refresh token persisted at `~/.config/jarvis/google-token.json`.
  - Credentials at `~/.config/jarvis/credentials.json` (Maxime downloads
    this file from Google Cloud Console once).

If credentials are missing, `fetch_today()` returns `[]` and logs once —
the frontend keeps showing the empty state and the rest of the system is
unaffected.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
_DEFAULT_CONFIG_DIR = Path.home() / ".config" / "jarvis"


def project_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map raw `events.list` items to panel entries; drop all-day events."""
    out: list[tuple[dt.datetime, dict[str, Any]]] = []
    for ev in items:
        start_obj = ev.get("start") or {}
        end_obj = ev.get("end") or {}
        start_dt = start_obj.get("dateTime")
        end_dt = end_obj.get("dateTime")
        if not start_dt or not end_dt:
            # All-day events use {"date": "YYYY-MM-DD"} — skip in v2.
            continue
        start = dt.datetime.fromisoformat(start_dt)
        end = dt.datetime.fromisoformat(end_dt)
        title = (ev.get("summary") or "").strip() or "(no title)"
        duration_min = max(0, int((end - start).total_seconds() // 60))
        out.append(
            (
                start,
                {
                    "time": start.strftime("%H:%M"),
                    "title": title,
                    "durationMin": duration_min,
                },
            )
        )
    out.sort(key=lambda x: x[0])
    return [entry for _, entry in out]


class CalendarClient:
    def __init__(
        self,
        *,
        credentials_path: Path = _DEFAULT_CONFIG_DIR / "credentials.json",
        token_path: Path = _DEFAULT_CONFIG_DIR / "google-token.json",
        service: Any | None = None,
    ) -> None:
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._service = service
        self._warned_missing = False

    def _ensure_service(self) -> Any | None:
        if self._service is not None:
            return self._service
        if not self.credentials_path.exists():
            if not self._warned_missing:
                log.warning(
                    "calendar credentials missing at %s — Calendar panel will stay empty",
                    self.credentials_path,
                )
                self._warned_missing = True
            return None
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
            from googleapiclient.discovery import build  # type: ignore[import-untyped]
        except ImportError:  # pragma: no cover
            log.warning("google api libs not installed; Calendar panel will stay empty")
            return None

        creds: Any = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
                str(self.token_path), _SCOPES
            )
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path), _SCOPES
            )
            creds = flow.run_local_server(port=0)
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json())
            self.token_path.chmod(0o600)
        self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return self._service

    async def fetch_today(self) -> list[dict[str, Any]]:
        service = self._ensure_service()
        if service is None:
            return []
        now = dt.datetime.now(dt.UTC)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + dt.timedelta(days=1)

        def _call() -> dict[str, Any]:
            result: dict[str, Any] = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=start_of_day.isoformat(),
                    timeMax=end_of_day.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            return result

        try:
            result = await asyncio.to_thread(_call)
        except Exception:  # noqa: BLE001
            log.exception("calendar fetch failed")
            return []
        items = result.get("items") or []
        return project_events(items)
