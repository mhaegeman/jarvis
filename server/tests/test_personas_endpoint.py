"""Tests for GET /personas endpoint.

Phase 5 Task 4: auth-gated endpoint returns persona profiles +
last-refresh ts + refresh-count. Returns 503 when personas not enabled.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_client() -> TestClient:
    """Import app fresh for each test."""
    from server.main import app

    return TestClient(app, raise_server_exceptions=False)


# ── Tests: personas disabled ──────────────────────────────────────────────────


def test_personas_endpoint_503_when_disabled() -> None:
    """Returns 503 when no persona registry is configured."""
    import server.main as main_mod

    with patch.object(main_mod, "_persona_registry", None):
        client = _make_client()
        # Auth is disabled in test (no JARVIS_PASSPHRASE_HASH set)
        resp = client.get("/personas")
        assert resp.status_code == 503


# ── Tests: auth-gating ────────────────────────────────────────────────────────


def test_personas_endpoint_401_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns 401 when auth is enabled and no token is provided."""
    import server.main as main_mod

    # Enable auth by patching the passphrase_hash on the settings object
    # that server.main._auth_enabled() actually reads (server.main.settings).
    # Patching cfg.settings is unreliable: test_phase2_dormant_when_flag_off
    # reloads server.config which rebinds cfg.settings to a new object while
    # main.settings still references the old one.
    monkeypatch.setattr(main_mod.settings, "passphrase_hash", "$argon2id$fake_hash")

    # Make personas unavailable so it would 503 if we get past auth, but we
    # should get 401 first.
    with patch.object(main_mod, "_persona_registry", None):
        client = _make_client()
        resp = client.get("/personas")
        # 401 from auth before 503 from missing registry
        assert resp.status_code == 401


def test_personas_endpoint_401_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns 401 with an invalid bearer token."""
    import server.main as main_mod

    monkeypatch.setattr(main_mod.settings, "passphrase_hash", "$argon2id$fake_hash")

    with patch.object(main_mod, "_persona_registry", None):
        client = _make_client()
        resp = client.get("/personas", headers={"Authorization": "Bearer bad_token"})
        assert resp.status_code == 401


# ── Tests: success path ───────────────────────────────────────────────────────


def _build_mock_registry() -> Any:
    """Build a minimal mock PersonaRegistry."""
    from server.personas.models import Persona

    jarvis = MagicMock(spec=Persona)
    jarvis.display_name = "Jarvis"
    jarvis.provider = "anthropic"
    jarvis.voice = "en-US-ChristopherNeural"
    jarvis.specialty_profile = "Jarvis speciality profile text."

    pepper = MagicMock(spec=Persona)
    pepper.display_name = "Pepper"
    pepper.provider = "openai"
    pepper.voice = "en-US-AriaNeural"
    pepper.specialty_profile = "Pepper specialty profile text."

    registry = MagicMock()
    registry.available_ids.return_value = ["jarvis", "pepper"]
    registry.get.side_effect = lambda pid: jarvis if pid == "jarvis" else pepper
    return registry


def test_personas_endpoint_200_with_registry() -> None:
    """Returns 200 with expected JSON shape when registry is present (auth disabled)."""
    import server.main as main_mod

    mock_registry = _build_mock_registry()

    with (
        patch.object(main_mod, "_persona_registry", mock_registry),
        patch.object(main_mod, "_profile_refresher", None),
    ):
        client = _make_client()
        resp = client.get("/personas")
        assert resp.status_code == 200
        data = resp.json()
        assert "jarvis" in data
        assert "pepper" in data

        # Check required fields
        for pid in ("jarvis", "pepper"):
            entry = data[pid]
            assert "displayName" in entry
            assert "provider" in entry
            assert "voice" in entry
            assert "specialtyProfile" in entry
            assert "lastRefreshTs" in entry
            assert "refreshCount" in entry


def test_personas_endpoint_includes_specialty_profile() -> None:
    """specialtyProfile field contains the registry's current profile text."""
    import server.main as main_mod

    mock_registry = _build_mock_registry()

    with (
        patch.object(main_mod, "_persona_registry", mock_registry),
        patch.object(main_mod, "_profile_refresher", None),
    ):
        client = _make_client()
        resp = client.get("/personas")
        data = resp.json()
        assert data["jarvis"]["specialtyProfile"] == "Jarvis speciality profile text."
        assert data["pepper"]["specialtyProfile"] == "Pepper specialty profile text."


def test_personas_endpoint_refresh_ts_none_when_no_refresher() -> None:
    """lastRefreshTs is None and refreshCount is 0 when no refresher is wired."""
    import server.main as main_mod

    mock_registry = _build_mock_registry()

    with (
        patch.object(main_mod, "_persona_registry", mock_registry),
        patch.object(main_mod, "_profile_refresher", None),
    ):
        client = _make_client()
        resp = client.get("/personas")
        data = resp.json()
        assert data["jarvis"]["lastRefreshTs"] is None
        assert data["jarvis"]["refreshCount"] == 0


def test_personas_endpoint_refresh_ts_from_persisted_storage() -> None:
    """lastRefreshTs + refreshCount come from the persisted personas table
    via ProfileRefresher.get_persisted_metadata — survives server restart.
    """
    import server.main as main_mod

    mock_registry = _build_mock_registry()

    mock_refresher = MagicMock()

    async def fake_metadata(pid: str) -> tuple[float | None, int]:
        return {
            "jarvis": (1234567890.0, 3),
            "pepper": (1234567891.0, 2),
        }[pid]

    mock_refresher.get_persisted_metadata = fake_metadata

    with (
        patch.object(main_mod, "_persona_registry", mock_registry),
        patch.object(main_mod, "_profile_refresher", mock_refresher),
    ):
        client = _make_client()
        resp = client.get("/personas")
        data = resp.json()
        assert data["jarvis"]["lastRefreshTs"] == pytest.approx(1234567890.0)
        assert data["jarvis"]["refreshCount"] == 3
        assert data["pepper"]["lastRefreshTs"] == pytest.approx(1234567891.0)
        assert data["pepper"]["refreshCount"] == 2
