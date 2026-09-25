import { NextResponse } from "next/server";
import { readJsonOrNull, exists } from "@/lib/repo";

export const dynamic = "force-dynamic";

export interface AgentRunRow {
  case_id: string;
  status: string | null;
  uncertainty: string | null;
  verdict: string | null;
  p0: number | null;
  p1: number | null;
  next_best_action: string | null;
  tool_calls: number | null;
  tokens: number | null;
  llm_status: string | null;
  trace_len: number;
  errors: string[];
  latency_s: number | null;
}

interface RawRun {
  case_id?: string;
  status?: string;
  uncertainty?: string;
  tokens?: number;
  tool_calls?: number;
  latency_s?: number;
  errors?: string[];
  trace?: unknown[];
  decision?: { verdict?: string; p0?: number; p1?: number };
  policy?: { action?: string };
  summary?: { llm?: { status?: string } };
}

export interface AgentPayload {
  batch: Record<string, unknown> | null;
  runs: AgentRunRow[];
}

/**
 * LangGraph runs written by scripts/run_agent.py (agent/runs/*.json).
 * Read-only; absent artifacts come back as an empty list rather than an error.
 */
export async function GET() {
  const batch = readJsonOrNull<Record<string, unknown>>(
    "validation/phase4_agent_runs.json",
  );

  let runs: AgentRunRow[] = [];
  if (exists("agent/runs")) {
    const rows = (
      [
        "HHG-001", "HHG-002", "HHG-003", "HHG-004", "HHG-005",
        "HHG-006", "HHG-007", "HHG-008", "HHG-009", "HHG-010",
        "HHG-011", "HHG-012", "HHG-013", "HHG-014", "HHG-015",
        "HHG-016", "HHG-017", "HHG-018", "HHG-019", "HHG-020",
      ] as const
    )
      .map((id) => readJsonOrNull<RawRun>(`agent/runs/${id}.json`))
      .filter((r): r is RawRun => r !== null);

    runs = rows.map((r) => ({
      case_id: r.case_id ?? "unknown",
      status: r.status ?? null,
      uncertainty: r.uncertainty ?? null,
      verdict: r.decision?.verdict ?? null,
      p0: r.decision?.p0 ?? null,
      p1: r.decision?.p1 ?? null,
      next_best_action: r.policy?.action ?? null,
      tool_calls: r.tool_calls ?? null,
      tokens: r.tokens ?? null,
      llm_status: r.summary?.llm?.status ?? null,
      trace_len: Array.isArray(r.trace) ? r.trace.length : 0,
      errors: Array.isArray(r.errors) ? r.errors : [],
      latency_s: r.latency_s ?? null,
    }));
  }

  const payload: AgentPayload = { batch, runs };
  return NextResponse.json(payload, {
    headers: { "cache-control": "no-store" },
  });
}
