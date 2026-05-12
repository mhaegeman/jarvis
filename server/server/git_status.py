"""Git status + diff helpers for the East Code zone.

Shells out to the system `git` binary (already installed on the deploy
target) instead of pulling in `gitpython` — cheaper, smaller blast radius,
and keeps the dependency tree lean.

Public surface:

* :func:`current_branch` — name of the current branch (or detached HEAD ref).
* :func:`changed_files` — list of :class:`ChangedFile` against the working
  tree + index, including untracked files.
* :func:`diff` — unified diff for a single tracked or untracked path,
  bounded to keep the payload small.

All functions accept an optional ``root`` :class:`~pathlib.Path` so the
caller can pin the repo location (FastAPI route reads ``JARVIS_GIT_ROOT``
from the environment); otherwise the process CWD is used.

Path safety: :func:`safe_resolve` validates that a caller-supplied
relative path lives under ``root`` and rejects parent traversal. The
FastAPI route uses it before calling :func:`diff`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Public status codes surfaced to the frontend. Mirrors `git status --porcelain`:
#   M = modified, A = added (staged), D = deleted, R = renamed, ?? = untracked.
StatusCode = Literal["M", "A", "D", "R", "??"]

# Cap diff payloads so the route can't blow past a reasonable size.
DIFF_MAX_LINES = 200


@dataclass(frozen=True)
class ChangedFile:
    """A single entry in the changed-files list."""

    path: str
    status: StatusCode


@dataclass(frozen=True)
class DiffLine:
    """A single line of a unified diff.

    ``kind``:
      * ``"+"`` — added line
      * ``"-"`` — removed line
      * ``" "`` — context (incl. preserved hunk headers)
      * ``"…"`` — truncation sentinel; ``text`` carries the user-facing message.
        Emitted as the last line when the diff hits :data:`DIFF_MAX_LINES`,
        so the UI can render a "diff truncated" notice instead of silently
        cutting off.
    """

    kind: Literal["+", "-", " ", "…"]
    text: str


def _run_git(args: list[str], root: Path) -> str:
    """Run `git <args>` inside ``root`` and return stdout (text).

    Raises:
        subprocess.CalledProcessError: when git exits non-zero.
        FileNotFoundError: when the `git` binary is unavailable.
    """
    result = subprocess.run(  # noqa: S603 - args are constructed, not shell-parsed
        ["git", *args],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def current_branch(root: Path | None = None) -> str:
    """Return the current branch name, or the short SHA if HEAD is detached."""
    repo = root or Path.cwd()
    name = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo).strip()
    if name == "HEAD":
        # Detached — fall back to the short SHA so the UI shows something stable.
        return _run_git(["rev-parse", "--short", "HEAD"], repo).strip()
    return name


def changed_files(root: Path | None = None) -> list[ChangedFile]:
    """Return changed files relative to ``root`` (working tree + index).

    Parses ``git status --porcelain=v1 -z`` so paths with spaces are
    handled correctly. Untracked files are reported with status ``??``.
    """
    repo = root or Path.cwd()
    raw = _run_git(["status", "--porcelain=v1", "-z"], repo)
    return _parse_porcelain(raw)


def _parse_porcelain(raw: str) -> list[ChangedFile]:
    """Parse the output of ``git status --porcelain=v1 -z``.

    Each record is ``XY␣path[␣→␣renamed-path]\\0``. ``X`` is the index
    state, ``Y`` is the worktree state. We collapse to a single status
    for the UI: rename takes priority, then any modification, then
    untracked.
    """
    out: list[ChangedFile] = []
    # NUL-delimited; renames consume an extra NUL-terminated record (old path).
    records = raw.split("\x00")
    i = 0
    while i < len(records):
        rec = records[i]
        i += 1
        if not rec:
            continue
        if len(rec) < 3:
            continue
        x, y, path = rec[0], rec[1], rec[3:]
        status = _collapse_status(x, y)
        if status == "R":
            # Skip the paired old-path record that follows a rename.
            i += 1
        out.append(ChangedFile(path=path, status=status))
    return out


def _collapse_status(x: str, y: str) -> StatusCode:
    """Collapse a porcelain XY pair into a single user-facing status code."""
    if x == "?" and y == "?":
        return "??"
    if x == "R" or y == "R":
        return "R"
    if x == "A" or y == "A":
        return "A"
    if x == "D" or y == "D":
        return "D"
    return "M"


class PathNotAllowedError(ValueError):
    """Raised when ``path`` is outside the changed-files whitelist."""


def _is_git_internal(parts: tuple[str, ...]) -> bool:
    """True if the first path component is ``.git`` (case-insensitive).

    The whitelist enforced by :func:`diff` already rejects any path that
    isn't in ``changed_files()`` — porcelain never reports ``.git/...``.
    This is belt-and-braces in case a future caller bypasses the whitelist:
    even a permissive client cannot exfiltrate ``.git/config`` credentials.
    """
    if not parts:
        return False
    return parts[0].lower() == ".git"


def safe_resolve(path: str, root: Path) -> Path:
    """Resolve ``path`` (relative) against ``root``, rejecting traversal.

    Raises:
        ValueError: when ``path`` is absolute, contains ``..`` segments,
            resolves outside ``root``, or targets the ``.git/`` directory.
    """
    p = Path(path)
    if p.is_absolute():
        raise ValueError("path must be relative")
    if any(part == ".." for part in p.parts):
        raise ValueError("parent traversal is not allowed")
    if _is_git_internal(p.parts):
        raise ValueError(".git directory is not accessible")
    resolved = (root / p).resolve()
    root_resolved = root.resolve()
    if root_resolved not in resolved.parents and resolved != root_resolved:
        raise ValueError("path escapes git root")
    rel_parts = resolved.relative_to(root_resolved).parts
    if _is_git_internal(rel_parts):
        raise ValueError(".git directory is not accessible")
    return resolved


def diff(path: str, root: Path | None = None) -> list[DiffLine]:
    """Return a bounded unified diff for ``path``.

    Only paths reported by :func:`changed_files` are accepted: this caps
    the file-read surface to the working-tree delta the UI is allowed to
    show. Anything else (gitignored secrets, arbitrary tracked files
    outside the diff, ``.git/`` internals) raises :class:`PathNotAllowedError`,
    which the route maps to 404.

    For tracked changed files this shells out to ``git diff HEAD -- <path>``;
    for untracked files reported by porcelain it falls back to
    ``git diff --no-index /dev/null <path>``.

    The output is capped at :data:`DIFF_MAX_LINES` lines, with a
    truncation marker appended when the cap is hit.
    """
    repo = root or Path.cwd()
    resolved = safe_resolve(path, repo)
    # Use the relative form for git so it matches the index.
    rel = resolved.relative_to(repo.resolve()).as_posix()

    # Whitelist: only files in the porcelain-reported delta are eligible
    # for diff. Stops arbitrary file reads (gitignored .env*, secrets,
    # config files outside the change set).
    allowed = {f.path for f in changed_files(repo)}
    if rel not in allowed:
        raise PathNotAllowedError(f"path is not in the changed-files set: {rel}")

    # Decide between tracked and untracked rendering. Belt-and-braces:
    # `ls-files --error-unmatch` tells us whether the path is tracked,
    # which avoids assuming the porcelain status code.
    ls = subprocess.run(  # noqa: S603
        ["git", "ls-files", "--error-unmatch", "--", rel],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    if ls.returncode == 0:
        raw = _run_git(["diff", "--no-color", "HEAD", "--", rel], repo)
    else:
        # Untracked file — diff against /dev/null. `git diff --no-index`
        # exits 1 when files differ, which is the normal case.
        proc = subprocess.run(  # noqa: S603
            ["git", "diff", "--no-color", "--no-index", "--", "/dev/null", rel],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        # rc 0 = no diff (empty new file), rc 1 = differs (expected). Anything
        # else is a real error.
        if proc.returncode not in (0, 1):
            raise subprocess.CalledProcessError(
                proc.returncode, proc.args, proc.stdout, proc.stderr
            )
        raw = proc.stdout

    return _parse_unified_diff(raw, limit=DIFF_MAX_LINES)


def _parse_unified_diff(raw: str, limit: int) -> list[DiffLine]:
    """Parse a unified diff into :class:`DiffLine` rows, skipping headers.

    Skips ``diff --git``, ``index``, ``---``, ``+++`` header lines and
    ``\\ No newline at end of file`` markers. Hunk headers (``@@``) are
    preserved as context lines so the UI can show them. Output is
    truncated to ``limit`` lines; when truncation occurs, a final sentinel
    row of kind ``"…"`` is appended so the UI can render a "diff
    truncated" notice instead of just cutting off.
    """
    lines: list[DiffLine] = []
    truncated = False
    for line in raw.splitlines():
        if (
            line.startswith("diff --git")
            or line.startswith("index ")
            or line.startswith("--- ")
            or line.startswith("+++ ")
            or line.startswith("\\ ")
        ):
            continue
        if line.startswith("@@"):
            lines.append(DiffLine(kind=" ", text=line))
        elif line.startswith("+"):
            lines.append(DiffLine(kind="+", text=line[1:]))
        elif line.startswith("-"):
            lines.append(DiffLine(kind="-", text=line[1:]))
        elif line.startswith(" "):
            lines.append(DiffLine(kind=" ", text=line[1:]))
        else:
            # Defensive: treat unrecognised lines as context so we
            # don't silently drop them.
            lines.append(DiffLine(kind=" ", text=line))
        if len(lines) >= limit:
            truncated = True
            break
    if truncated:
        # Replace the last data row with the sentinel so total length stays
        # at exactly ``limit`` — keeps the existing test contract intact
        # while still signalling truncation to the UI.
        lines[-1] = DiffLine(
            kind="…",
            text=f"diff truncated at {limit} lines",
        )
    return lines
