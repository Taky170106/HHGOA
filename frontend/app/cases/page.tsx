"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  Button,
  ErrorNote,
  Loading,
  PageHeader,
  Segmented,
  StatTile,
  Tag,
} from "@/components/kit";
import { verdictColor, verdictShort } from "@/lib/classify";
import { useSummary } from "@/lib/useJson";
import type { CaseSummaryRow, Verdict } from "@/lib/types";

type FilterKey = "all" | Verdict | "sar";

export default function CasesPage() {
  const { data, error, loading } = useSummary();
  const [filter, setFilter] = useState<FilterKey>("all");
  const [q, setQ] = useState("");

  const rows = data?.cases ?? [];

  const counts = useMemo(() => {
    const c: Record<string, number> = {
      all: rows.length,
      fraud: 0,
      uncertain: 0,
      legitimate: 0,
      sar: 0,
    };
    for (const r of rows) {
      c[r.verdict] = (c[r.verdict] ?? 0) + 1;
      if (r.sar_file) c.sar += 1;
    }
    return c;
  }, [rows]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows.filter((r) => {
      if (filter !== "all") {
        if (filter === "sar") {
          if (!r.sar_file) return false;
        } else if (r.verdict !== filter) return false;
      }
      if (!needle) return true;
      return (
        r.case_id.toLowerCase().includes(needle) ||
        r.pattern.toLowerCase().includes(needle) ||
        r.next_best_action.toLowerCase().includes(needle)
      );
    });
  }, [rows, filter, q]);

  if (error) return <ErrorNote what="/api/summary" message={error} />;
  if (loading || !data) return <Loading what="cases/validation_report.json" />;

  return (
    <div className="fade-up pb-16">
      <PageHeader
        eyebrow="MODULE 01 · CASE SECTION"
        title="All 20 benchmark cases"
        lede="Every answer file produced by the agent, exactly as validated by scripts/validate_cases.py. Half the queue is legitimate by design — the agent scores badly if it blocks everything, so verdict, probability and evidence count are shown side by side."
        actions={
          <>
            <Button href="/investigation" variant="primary">
              ▶ RUN INVESTIGATION
            </Button>
            <Button href="/">← OVERVIEW</Button>
          </>
        }
        meta={
          <span className="font-mono text-[10px] text-dim">
            cases/HHG-001.json … HHG-020.json
          </span>
        }
      />

      <div className="border-b border-line bg-ink-950 py-6">
        <div className="mx-auto w-full max-w-[1520px] px-8">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <StatTile label="Cases" value={counts.all} sub={`${data.cases_passed} validated`} />
            <StatTile label="Fraud" value={counts.fraud} tone="var(--color-bad)" />
            <StatTile label="Uncertain" value={counts.uncertain} tone="var(--color-warn)" />
            <StatTile label="Legitimate" value={counts.legitimate} tone="var(--color-ok)" />
            <StatTile label="SAR filed" value={counts.sar} tone="var(--color-bad)" sub="approval L1/L2" />
            <StatTile
              label="Evidence"
              value={rows.reduce((s, r) => s + r.evidence_items, 0)}
              sub="items cited"
            />
          </div>
        </div>
      </div>

      <div className="mx-auto w-full max-w-[1520px] px-8 pt-7">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Segmented
            value={filter}
            onChange={(k) => setFilter(k as FilterKey)}
            options={[
              { key: "all", label: "All", count: counts.all },
              { key: "fraud", label: "Fraud", count: counts.fraud },
              { key: "uncertain", label: "Uncertain", count: counts.uncertain },
              { key: "legitimate", label: "Legitimate", count: counts.legitimate },
              { key: "sar", label: "SAR", count: counts.sar },
            ]}
          />

          <label className="flex items-center gap-2">
            <span className="text-[10px] tracking-[0.16em] text-dim uppercase">
              Search
            </span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="case id, pattern, action…"
              className="h-9 w-[300px] rounded-sm border border-line bg-ink-900 px-3 font-mono text-[12px] text-fg outline-none placeholder:text-dim focus:border-accent/60"
            />
          </label>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {shown.map((r) => (
            <CaseCard key={r.case_id} row={r} />
          ))}
        </div>

        {!shown.length && (
          <div className="mt-6 border border-dashed border-line px-4 py-10 text-center text-[12px] text-dim">
            No case matches this filter.
          </div>
        )}
      </div>
    </div>
  );
}

function CaseCard({ row }: { row: CaseSummaryRow }) {
  const color = verdictColor(row.verdict);
  const p = row.fraud_probability;

  return (
    <Link
      href={`/cases/${row.case_id}`}
      className="group flex flex-col border border-line bg-ink-900 p-4 transition hover:border-accent/50 hover:bg-ink-850"
      style={{ boxShadow: `inset 3px 0 0 ${color}` }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[15px] font-bold text-fg group-hover:text-accent">
          {row.case_id}
        </span>
        <span
          className="border px-1.5 py-[1px] font-mono text-[9.5px] font-bold tracking-[0.1em]"
          style={{ color, borderColor: `${color}80` }}
        >
          {verdictShort(row.verdict)} · {row.verdict.toUpperCase()}
        </span>
      </div>

      <div className="mt-1.5 flex items-center gap-2 text-[10.5px] text-fg-2">
        <span className="truncate">
          {row.pattern === "none" ? "no fraud pattern" : row.pattern}
        </span>
        <span className="ml-auto shrink-0 font-mono text-dim">
          {row.evidence_items} ev
        </span>
      </div>

      <div className="mt-3">
        <div className="flex items-baseline justify-between">
          <span className="text-[9.5px] tracking-[0.14em] text-dim uppercase">
            fraud_probability
          </span>
          <span className="font-mono text-[13px] font-bold" style={{ color }}>
            {p.toFixed(4)}
          </span>
        </div>
        <div className="mt-1 h-[6px] w-full border border-line bg-ink-850">
          <div
            className="h-full"
            style={{ width: `${Math.min(100, p * 100)}%`, background: color, opacity: 0.9 }}
          />
        </div>
        <div className="mt-1 flex justify-between font-mono text-[9px] text-dim">
          <span>0</span>
          <span className="text-warn">0.7 review threshold</span>
          <span>1</span>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-line pt-2 text-[10px]">
        <span className="text-dim">exposure</span>
        <span className="text-right font-mono text-fg-2">
          ${row.exposure_usd.toFixed(2)}
        </span>
        <span className="text-dim">next action</span>
        <span className="truncate text-right font-mono text-fg-2">
          {row.next_best_action}
        </span>
        <span className="text-dim">approval</span>
        <span className="text-right font-mono text-fg-2">
          {row.approval_route.join(", ")}
        </span>
      </div>

      <div className="mt-2.5 flex items-center gap-1.5">
        {row.sar_file ? <Tag tone="bad">SAR</Tag> : <Tag>no SAR</Tag>}
        {row.additional_evidence_received ? (
          <Tag tone="ok">evidence received</Tag>
        ) : (
          <Tag tone="warn">no extra evidence</Tag>
        )}
        <span className="ml-auto font-mono text-[9.5px] text-dim">
          {row.tool_calls} calls
        </span>
      </div>
    </Link>
  );
}
