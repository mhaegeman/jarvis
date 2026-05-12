"""Tests for the POST /auth/login endpoint."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from server.config import Settings


def test_passphrase_hash_config_default_is_none() -> None:
    """JARVIS_PASSPHRASE_HASH is optional; defaults to None."""
    s = Settings()
    assert s.passphrase_hash is None
