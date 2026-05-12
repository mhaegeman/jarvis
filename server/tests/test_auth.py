"""Tests for the POST /auth/login endpoint."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from server.config import Settings
from server.main import app


def test_passphrase_hash_config_default_is_none() -> None:
    """JARVIS_PASSPHRASE_HASH is optional; defaults to None."""
    s = Settings()
    assert s.passphrase_hash is None


@pytest.mark.asyncio
async def test_login_returns_503_when_no_hash_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """503 when JARVIS_PASSPHRASE_HASH is not set."""
    monkeypatch.setattr("server.main.settings", Settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/auth/login", json={"passphrase": "anything"})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_login_returns_401_on_wrong_passphrase(monkeypatch: pytest.MonkeyPatch) -> None:
    """401 on wrong passphrase when hash is configured."""
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    correct_hash = ph.hash("correctphrase123")
    monkeypatch.setattr("server.main.settings", Settings(JARVIS_PASSPHRASE_HASH=correct_hash))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/auth/login", json={"passphrase": "wrongpassphrase"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid passphrase"


@pytest.mark.asyncio
async def test_login_returns_token_on_correct_passphrase(monkeypatch: pytest.MonkeyPatch) -> None:
    """200 + token when passphrase matches the hash."""
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    correct_hash = ph.hash("correctphrase123")
    monkeypatch.setattr("server.main.settings", Settings(JARVIS_PASSPHRASE_HASH=correct_hash))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/auth/login", json={"passphrase": "correctphrase123"})
    assert r.status_code == 200
    body = r.json()
    assert "token" in body
    assert len(body["token"]) == 64  # 32 bytes hex = 64 chars
