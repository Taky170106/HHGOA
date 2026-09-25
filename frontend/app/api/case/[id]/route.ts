import { NextResponse } from "next/server";
import { exists, readJson } from "@/lib/repo";
import type { CaseFile, CasePayload, E2eRun, ShapLocalEntry } from "@/lib/types";

export const dynamic = "force-dynamic";

const ID_RE = /^HHG-\d{3}$/;

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;

  if (!ID_RE.test(id)) {
    return NextResponse.json({ error: "bad case id" }, { status: 400 });
  }
  if (!exists(`cases/${id}.json`)) {
    return NextResponse.json({ error: "case not found" }, { status: 404 });
  }

  const caseFile = readJson<CaseFile>(`cases/${id}.json`);

  const shapAll = exists("xai/shap_local_benchmark_cases.json")
    ? readJson<Record<string, ShapLocalEntry>>(
        "xai/shap_local_benchmark_cases.json",
      )
    : null;

  const shapGlobal = exists("xai/shap_global.json")
    ? readJson<CasePayload["shapGlobal"]>("xai/shap_global.json")
    : null;

  // The live end-to-end demo was executed once, for HHG-001.
  const e2e =
    id === "HHG-001" && exists("validation/phase3_e2e.json")
      ? readJson<E2eRun>("validation/phase3_e2e.json")
      : null;

  const payload: CasePayload = {
    caseFile,
    shapLocal: shapAll ? (shapAll[id] ?? null) : null,
    shapGlobal,
    e2e,
  };

  return NextResponse.json(payload, {
    headers: { "cache-control": "no-store" },
  });
}
