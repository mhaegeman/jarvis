"""Tests for server.git_status helpers and the /git/* HTTP routes."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from server import git_status as gs
from server.main import app

# ── git_status unit tests ────────────────────────────────────────────────


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


def test_diff_caps_output_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gs, "DIFF_MAX_LINES", 10)
    _init_repo(tmp_path)
    (tmp_path / "big.txt").write_text("x\n")
    _commit(tmp_path)
    (tmp_path / "big.txt").write_text("\n".join(f"line {i}" for i in range(500)) + "\n")
    lines = gs.diff("big.txt", tmp_path)
    assert len(lines) == 10


def test_safe_resolve_rejects_absolute(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="relative"):
        gs.safe_resolve("/etc/passwd", tmp_path)


def test_safe_resolve_rejects_parent_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="traversal"):
        gs.safe_resolve("../../etc/passwd", tmp_path)


def test_safe_resolve_accepts_normal_relative_path(tmp_path: Path) -> None:
    resolved = gs.safe_resolve("sub/file.txt", tmp_path)
    assert resolved == (tmp_path / "sub" / "file.txt").resolve()


# ── HTTP route tests ─────────────────────────────────────────────────────


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
