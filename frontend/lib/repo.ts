/**
 * Repository access for the dashboard.
 *
 * The UI is a READ-ONLY view over artifacts that already exist in the repo:
 *   cases/*.json, validation/*.json, models/*.json, xai/*.json, docs/*.json
 *
 * Nothing here writes to the graph, the schema, the model or the case files.
 */

import fs from "node:fs";
import path from "node:path";

/** Repo root: either cwd (if it holds `cases/`) or its parent (frontend/). */
function repoRoot(): string {
  const cwd = process.cwd();
  if (fs.existsSync(path.join(cwd, "cases"))) return cwd;
  const up = path.resolve(cwd, "..");
  if (fs.existsSync(path.join(up, "cases"))) return up;
  return cwd;
}

export const REPO = repoRoot();

export function readJson<T>(rel: string): T {
  return JSON.parse(fs.readFileSync(path.join(REPO, rel), "utf8")) as T;
}

export function readJsonOrNull<T>(rel: string): T | null {
  try {
    return readJson<T>(rel);
  } catch {
    return null;
  }
}

export function exists(rel: string): boolean {
  return fs.existsSync(path.join(REPO, rel));
}
