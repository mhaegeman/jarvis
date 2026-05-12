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
  kind: "+" | "-" | " ";
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
  const res = await fetcher(`${baseUrl}${STATUS_URL}`);
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

/** Fetch a unified diff for one file. Returns an empty list on 404. */
export async function fetchGitDiff(
  path: string,
  baseUrl = "",
  fetcher: typeof fetch = fetch,
): Promise<ServerGitDiffLine[]> {
  const res = await fetcher(`${baseUrl}${DIFF_URL}?path=${encodeURIComponent(path)}`);
  if (res.status === 404) return [];
  if (!res.ok) {
    throw new Error(`git diff: HTTP ${res.status}`);
  }
  const body = (await res.json()) as ServerGitDiffResponse;
  return body.lines;
}
