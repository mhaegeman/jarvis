"""Tests for server.git_status helpers and the /git/* HTTP routes."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from server import git_status as gs
from server.config import Settings
from server.main import _active_tokens, app

# ── git_status unit tests ─────────────────────────────


def _init_repo(root: Path) -> None:
    """Create an empty git repo with a deterministic identity."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=root, check=True)


def _commit(root: Path, msg: str = "init") -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=root, check=True)


def test_current_branch_returns_main(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("hello\n")
    _commit(tmp_path)
    assert gs.current_branch(tmp_path) == "main"


def test_current_branch_falls_back_to_sha_when_detached(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("hello\n")
    _commit(tmp_path)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "checkout", "-q", sha], cwd=tmp_path, check=True)
    branch = gs.current_branch(tmp_path)
    # Detached: should be a short SHA (7 hex chars), not "HEAD".
    assert branch != "HEAD"
    assert sha.startswith(branch)


def test_changed_files_classifies_modified_added_untracked_deleted(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "tracked.txt").write_text("v1\n")
    (tmp_path / "to_delete.txt").write_text("bye\n")
    _commit(tmp_path)

    # Modify a tracked file.
    (tmp_path / "tracked.txt").write_text("v2\n")
    # Stage a brand-new file (status: A).
    (tmp_path / "staged_new.txt").write_text("staged\n")
    subprocess.run(["git", "add", "staged_new.txt"], cwd=tmp_path, check=True)
    # Delete a tracked file.
    (tmp_path / "to_delete.txt").unlink()
    # Untracked file.
    (tmp_path / "untracked.txt").write_text("u\n")

    files = {f.path: f.status for f in gs.changed_files(tmp_path)}
    assert files["tracked.txt"] == "M"
    assert files["staged_new.txt"] == "A"
    assert files["to_delete.txt"] == "D"
    assert files["untracked.txt"] == "??"


def test_changed_files_handles_renames(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "old.txt").write_text("content\n")
    _commit(tmp_path)
    subprocess.run(["git", "mv", "old.txt", "new.txt"], cwd=tmp_path, check=True)
    files = gs.changed_files(tmp_path)
    paths = [f.path for f in files]
    # The renamed path should be present (porcelain emits new path).
    assert "new.txt" in paths
    statuses = {f.path: f.status for f in files}
    assert statuses["new.txt"] == "R"


def test_diff_returns_lines_for_modified_file(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("one\ntwo\nthree\n")
    _commit(tmp_path)
    (tmp_path / "a.txt").write_text("one\nTWO\nthree\n")
    lines = gs.diff("a.txt", tmp_path)
    kinds = [line.kind for line in lines]
    assert "+" in kinds
    assert "-" in kinds
    # First non-header line is a hunk header preserved as context.
    assert lines[0].kind == " "
    assert lines[0].text.startswith("@@")


def test_diff_handles_untracked_file(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n")
    _commit(tmp_path)
    (tmp_path / "fresh.txt").write_text("a\nb\nc\n")
    lines = gs.diff("fresh.txt", tmp_path)
    assert any(line.kind == "+" for line in lines)


def test_diff_caps_output_lines_with_truncation_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gs, "DIFF_MAX_LINES", 10)
    _init_repo(tmp_path)
    (tmp_path / "big.txt").write_text("x\n")
    _commit(tmp_path)
    (tmp_path / "big.txt").write_text("\n".join(f"line {i}" for i in range(500)) + "\n")
    lines = gs.diff("big.txt", tmp_path)
    assert len(lines) == 10
    # Last line is the truncation sentinel so the UI can render a notice
    # instead of silently cutting the diff off.
    assert lines[-1].kind == "…"
    assert "truncated" in lines[-1].text


def test_diff_no_truncation_marker_when_under_cap(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "small.txt").write_text("a\nb\n")
    _commit(tmp_path)
    (tmp_path / "small.txt").write_text("a\nB\n")
    lines = gs.diff("small.txt", tmp_path)
    assert all(line.kind != "…" for line in lines)


def test_safe_resolve_rejects_absolute(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="relative"):
        gs.safe_resolve("/etc/passwd", tmp_path)


def test_safe_resolve_rejects_parent_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="traversal"):
        gs.safe_resolve("../../etc/passwd", tmp_path)


def test_safe_resolve_accepts_normal_relative_path(tmp_path: Path) -> None:
    resolved = gs.safe_resolve("sub/file.txt", tmp_path)
    assert resolved == (tmp_path / "sub" / "file.txt").resolve()


def test_safe_resolve_rejects_dot_git_dir(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=".git"):
        gs.safe_resolve(".git/config", tmp_path)


def test_safe_resolve_rejects_dot_git_case_insensitive(tmp_path: Path) -> None:
    # Defensive: case-insensitive check protects against case-folded
    # filesystems even though the test runs on Linux.
    with pytest.raises(ValueError, match=".git"):
        gs.safe_resolve(".GIT/config", tmp_path)


def test_diff_rejects_unchanged_tracked_file(tmp_path: Path) -> None:
    """Whitelist: only changed files are eligible for diff."""
    _init_repo(tmp_path)
    (tmp_path / "tracked.txt").write_text("content\n")
    _commit(tmp_path)
    # tracked.txt exists and is tracked, but it's NOT in changed_files()
    # because the working tree matches HEAD.
    with pytest.raises(gs.PathNotAllowedError):
        gs.diff("tracked.txt", tmp_path)


def test_diff_rejects_gitignored_untracked_file(tmp_path: Path) -> None:
    """Gitignored files (e.g. .env.local) are not in changed_files() → 404 surface."""
    _init_repo(tmp_path)
    (tmp_path / ".gitignore").write_text(".env.local\n")
    _commit(tmp_path)
    (tmp_path / ".env.local").write_text("SECRET=abc123\n")
    with pytest.raises(gs.PathNotAllowedError):
        gs.diff(".env.local", tmp_path)


def test_diff_allows_file_in_changed_files(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("v1\n")
    _commit(tmp_path)
    (tmp_path / "a.txt").write_text("v2\n")
    # Sanity: appears in changed_files(), so diff() should succeed.
    assert "a.txt" in {f.path for f in gs.changed_files(tmp_path)}
    lines = gs.diff("a.txt", tmp_path)
    assert any(line.kind in ("+", "-") for line in lines)


# ── HTTP route tests ────────────────────────────────


@pytest.fixture
def repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a small repo and point JARVIS_GIT_ROOT at it."""
    _init_repo(tmp_path)
    (tmp_path / "hello.txt").write_text("alpha\nbeta\n")
    _commit(tmp_path)
    (tmp_path / "hello.txt").write_text("alpha\nBETA\n")
    (tmp_path / "untracked.md").write_text("hi\n")
    monkeypatch.setenv("JARVIS_GIT_ROOT", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_git_status_route_returns_branch_and_files(repo_root: Path) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/status")
    assert r.status_code == 200
    body = r.json()
    assert body["branch"] == "main"
    paths = {f["path"]: f["status"] for f in body["files"]}
    assert paths["hello.txt"] == "M"
    assert paths["untracked.md"] == "??"
    assert body["buildStatus"] is None


@pytest.mark.asyncio
async def test_git_diff_route_returns_lines(repo_root: Path) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/diff", params={"path": "hello.txt"})
    assert r.status_code == 200
    body = r.json()
    assert any(line["kind"] == "+" for line in body["lines"])
    assert any(line["kind"] == "-" for line in body["lines"])


@pytest.mark.asyncio
async def test_git_diff_route_404_on_missing_path(repo_root: Path) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/diff", params={"path": "nope.txt"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_git_diff_route_400_on_parent_traversal(repo_root: Path) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/diff", params={"path": "../etc/passwd"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_git_diff_route_400_on_absolute_path(repo_root: Path) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/diff", params={"path": "/etc/passwd"})
    assert r.status_code == 400


# ── Security: arbitrary file read + .git/ access ───────────────────


def _make_gitignored_secret(repo_root: Path) -> None:
    """Sync helper: drop a gitignored secrets file in ``repo_root``.

    Defined sync so ruff's ASYNC221 lint doesn't flag the blocking
    ``subprocess.run`` calls inside an ``async def`` test body.
    """
    (repo_root / ".gitignore").write_text(".env.local\n")
    subprocess.run(["git", "add", ".gitignore"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "ignore"], cwd=repo_root, check=True
    )
    (repo_root / ".env.local").write_text("ANTHROPIC_API_KEY=sk-leak\n")


@pytest.mark.asyncio
async def test_git_diff_route_404_on_gitignored_file(repo_root: Path) -> None:
    """Gitignored files shouldn't be readable via the diff endpoint."""
    _make_gitignored_secret(repo_root)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/diff", params={"path": ".env.local"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_git_diff_route_400_on_dot_git_config(repo_root: Path) -> None:
    """`.git/config` would expose stored credentials — must be 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/diff", params={"path": ".git/config"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_git_diff_route_400_on_dot_git_head(repo_root: Path) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/diff", params={"path": ".git/HEAD"})
    assert r.status_code == 400


def _commit_secret_file(repo_root: Path) -> None:
    """Sync helper: commit a plaintext secret file (tracked, unchanged)."""
    (repo_root / "secrets.txt").write_text("plaintext-secret\n")
    subprocess.run(["git", "add", "secrets.txt"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "secrets"], cwd=repo_root, check=True
    )


@pytest.mark.asyncio
async def test_git_diff_route_404_on_untracked_file_outside_changed_files(
    repo_root: Path,
) -> None:
    """A tracked-but-unchanged file isn't in changed_files() → 404."""
    _commit_secret_file(repo_root)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/diff", params={"path": "secrets.txt"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_git_diff_route_400_on_url_encoded_traversal(repo_root: Path) -> None:
    """URL-encoded traversal must be decoded before validation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/diff", params={"path": "../etc/passwd"})
    assert r.status_code == 400


# ── 503 when git routes are not available ─────────────────────


@pytest.mark.asyncio
async def test_git_status_503_when_no_git_repo_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If JARVIS_GIT_ROOT is unset and CWD has no .git, return 503."""
    monkeypatch.delenv("JARVIS_GIT_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)  # tmp_path has no .git dir
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/status")
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_git_diff_503_when_no_git_repo_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("JARVIS_GIT_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/diff", params={"path": "anything.txt"})
    assert r.status_code == 503


# ── Auth: bearer token gating + bypass when unconfigured ─────────────


@pytest.fixture
def auth_configured(monkeypatch: pytest.MonkeyPatch) -> str:
    """Configure a real argon2 hash and pre-mint a valid bearer token."""
    from argon2 import PasswordHasher

    ph = PasswordHasher()
    h = ph.hash("correctphrase123")
    monkeypatch.setattr(
        "server.main.settings", Settings(JARVIS_PASSPHRASE_HASH=h)
    )
    token = "deadbeef" * 8  # 64 hex chars, matches token_hex(32) shape
    _active_tokens.add(token)
    yield token
    _active_tokens.discard(token)


@pytest.mark.asyncio
async def test_git_status_401_without_token_when_auth_configured(
    repo_root: Path, auth_configured: str
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/status")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_git_status_200_with_valid_token(
    repo_root: Path, auth_configured: str
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(
            "/git/status",
            headers={"Authorization": f"Bearer {auth_configured}"},
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_git_status_200_without_token_when_auth_not_configured(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Local-dev parity: no hash → no auth gate, anywhere."""
    monkeypatch.setattr("server.main.settings", Settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/git/status")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_git_status_401_with_garbage_token(
    repo_root: Path, auth_configured: str
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(
            "/git/status", headers={"Authorization": "Bearer not-a-real-token"}
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_token_round_trip_grants_git_status_access(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: POST /auth/login → use token on /git/status."""
    from argon2 import PasswordHasher

    ph = PasswordHasher()
    monkeypatch.setattr(
        "server.main.settings",
        Settings(JARVIS_PASSPHRASE_HASH=ph.hash("correctphrase123")),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        login = await c.post("/auth/login", json={"passphrase": "correctphrase123"})
        assert login.status_code == 200
        token = login.json()["token"]
        r = await c.get(
            "/git/status", headers={"Authorization": f"Bearer {token}"}
        )
    assert r.status_code == 200


# ── WebSocket auth ───────────────────────────────


def test_ws_closed_with_1008_when_no_token_and_auth_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WS upgrade without ?token=… should be refused (close 1008).

    Uses ``TestClient`` without the ``with`` context — matches the style
    of ``tests/test_ws_integration.py`` and avoids triggering the
    module-level ``_memory_store`` open/close lifecycle, which would leak
    a closed store to subsequent tests run in the same process.
    """
    from argon2 import PasswordHasher
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect as _WSD

    ph = PasswordHasher()
    monkeypatch.setattr(
        "server.main.settings",
        Settings(JARVIS_PASSPHRASE_HASH=ph.hash("correctphrase123")),
    )
    client = TestClient(app)
    with pytest.raises(_WSD) as excinfo, client.websocket_connect("/ws") as ws:
        ws.receive_text()
    assert excinfo.value.code == 1008


# Note: a "WS accepts when auth not configured" test was intentionally
# omitted — the existing `tests/test_ws_integration.py` already exercises
# that path end-to-end (no token, no hash, full message flow). Adding a
# duplicate TestClient-based WS test here introduces lifespan ordering
# issues that corrupt the module-level `_memory_store`.
