import { NextResponse } from "next/server";
import { readJson, readJsonOrNull } from "@/lib/repo";
import type { CaseFile, CaseSummaryRow, SummaryPayload } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  const report = readJson<{
    status: string;
    cases_passed: number;
    total_errors: number;
    per_case: CaseSummaryRow[];
  }>("cases/validation_report.json");

  const build = readJson<{
    verdicts: { fraud: number; legitimate: number; uncertain: number };
    sar_filed: number;
    tool_calls: { live: number; retrieval: number };
  }>("cases/_build_summary.json");

  const metrics = readJson<SummaryPayload["metrics"]>("models/metrics.json");

  // graph write state is the same object in every case file — read one case.
  const first = readJson<CaseFile>("cases/HHG-001.json");

  const gsql = readJson<Record<string, number | string>>(
    "docs/PHASE3_QUERY_CATALOG.json",
  );
  const mcp = readJsonOrNull<Record<string, unknown>>(
    "mcp/validation/phase3_mcp_live.json",
  );

  const payload: SummaryPayload = {
    cases: report.per_case,
    counts: build.verdicts,
    sar_filed: build.sar_filed,
    tool_calls: build.tool_calls,
    validation_status: report.status,
    cases_passed: report.cases_passed,
    total_errors: report.total_errors,
    metrics,
    graph_write: first.graph_write,
    gsql,
    mcp: mcp ?? {},
  };

  return NextResponse.json(payload, {
    headers: { "cache-control": "no-store" },
  });
}
