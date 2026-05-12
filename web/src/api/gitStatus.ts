/**
 * Thin client for the backend `/git/status` and `/git/diff` routes.
 *
 * The East Code zone polls `fetchGitStatus()` every ~10s; the CodeFocus
 * overlay calls `fetchGitDiff(path)` on demand when a file is selected.
 *
 * The server returns porcelain status codes — we collapse those to the
 * three groups the UI cares about (modified / added / deleted) and
 * compute a placeholder delta string. Real per-file delta numbers would
 * require parsing the diff payload server-side, which is out of scope
 * for this iteration.
 */

import type { CompassCodeFile } from "@/compass/types";

export type ServerStatusCode = "M" | "A" | "D" | "R" | "??";

export interface ServerGitStatusFile {
  path: string;
  status: ServerStatusCode;
}

export interface ServerGitStatusResponse {
  branch: string;
  files: ServerGitStatusFile[];
  buildStatus: "ok" | "fail" | "running" | null;
}

export interface ServerGitDiffLine {
  /**
   * ``+``/``-``/`` `` are added/removed/context lines. ``…`` is a
   * truncation sentinel emitted by the backend when the diff exceeds
   * its line cap; ``text`` carries a user-facing message.
   */
  kind: "+" | "-" | " " | "…";
  text: string;
}

export interface ServerGitDiffResponse {
  lines: ServerGitDiffLine[];
}

export interface GitStatus {
  branch: string;
  files: CompassCodeFile[];
  buildStatus: "ok" | "fail" | "running" | null;
}

const STATUS_URL = "/git/status";
const DIFF_URL = "/git/diff";
const TOKEN_KEY = "jarvis_token";

/** Build the Authorization header from the cached login token, if any. */
function authHeaders(): Record<string, string> {
  const token =
    typeof sessionStorage !== "undefined"
      ? sessionStorage.getItem(TOKEN_KEY)
      : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Drop the cached token + reload to re-prompt login. Used on 401. */
function reauth(): void {
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.removeItem(TOKEN_KEY);
  }
  if (typeof window !== "undefined") {
    window.location.reload();
  }
}

/** Map a porcelain status code to the UI's three-bucket grouping. */
export function mapStatusGroup(code: ServerStatusCode): CompassCodeFile["group"] {
  if (code === "A" || code === "??") return "added";
  if (code === "D") return "deleted";
  // Rename + modified both surface as "modified" in the UI.
  return "modified";
}

/** Convert a server status payload into the UI's CompassCodeFile shape. */
export function toCompassFiles(files: ServerGitStatusFile[]): CompassCodeFile[] {
  return files.map((f, i) => ({
    group: mapStatusGroup(f.status),
    name: f.path,
    // Per-file line counts require a diff fetch; show the status letter as
    // a stable placeholder so the UI still has something to render.
    delta: f.status === "??" ? "new" : f.status,
    active: i === 0,
  }));
}

/** Fetch the current git status from the backend. */
export async function fetchGitStatus(
  baseUrl = "",
  fetcher: typeof fetch = fetch,
): Promise<GitStatus> {
  const res = await fetcher(`${baseUrl}${STATUS_URL}`, {
    headers: authHeaders(),
  });
  if (res.status === 401) {
    reauth();
    throw new Error("git status: HTTP 401");
  }
  if (!res.ok) {
    throw new Error(`git status: HTTP ${res.status}`);
  }
  const body = (await res.json()) as ServerGitStatusResponse;
  return {
    branch: body.branch,
    files: toCompassFiles(body.files),
    buildStatus: body.buildStatus,
  };
}

/**
 * Wrap a poll function so it only runs when the tab is visible.
 *
 * Returns ``true`` when the wrapped poll ran, ``false`` when it was
 * skipped because ``document.visibilityState`` is hidden. Exported so
 * the CompassApp wiring is unit-testable without mounting the full
 * surface.
 */
export async function pollIfVisible(
  poll: () => Promise<void>,
  visibilityState?: DocumentVisibilityState,
): Promise<boolean> {
  const state =
    visibilityState ??
    (typeof document !== "undefined" ? document.visibilityState : "visible");
  if (state !== "visible") return false;
  await poll();
  return true;
}

/** Fetch a unified diff for one file. Returns an empty list on 404. */
export async function fetchGitDiff(
  path: string,
  baseUrl = "",
  fetcher: typeof fetch = fetch,
): Promise<ServerGitDiffLine[]> {
  const res = await fetcher(
    `${baseUrl}${DIFF_URL}?path=${encodeURIComponent(path)}`,
    { headers: authHeaders() },
  );
  if (res.status === 404) return [];
  if (res.status === 401) {
    reauth();
    throw new Error("git diff: HTTP 401");
  }
  if (!res.ok) {
    throw new Error(`git diff: HTTP ${res.status}`);
  }
  const body = (await res.json()) as ServerGitDiffResponse;
  return body.lines;
}
