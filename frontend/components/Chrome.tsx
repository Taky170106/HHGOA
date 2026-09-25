"use client";

import { Chip } from "./ui";
import { verdictColor, verdictShort } from "@/lib/classify";
import type { CaseSummaryRow } from "@/lib/types";

export function TopBar({
  activeCase,
  caseStatus,
  tg,
  onRun,
  replaying,
  replayStage,
  onOpenArch,
  onOpenCase,
}: {
  activeCase: string;
  caseStatus: string;
  tg: {
    ok: boolean;
    http_status: number;
    latency_ms: number;
    endpoint?: string;
  } | null;
  onRun: () => void;
  replaying: boolean;
  replayStage: number;
  onOpenArch: () => void;
  onOpenCase: () => void;
}) {
  const complete = caseStatus.startsWith("closed");

  return (
    <header className="flex h-12 shrink-0 items-center gap-4 border-b border-line bg-ink-900 px-3">
      {/* identity */}
      <div className="flex items-center gap-2.5">
        <div className="flex h-7 w-7 items-center justify-center rounded-sm border border-accent/50 bg-accent/10 font-mono text-[13px] text-accent">
          ⬡
        </div>
        <div className="leading-none">
          <div className="text-[13.5px] font-bold tracking-[0.16em] text-fg">
            HHG FRAUD INTELLIGENCE
          </div>
          <div className="mt-[3px] text-[9px] tracking-[0.2em] text-dim">
            TIGERGRAPH AGENTIC INVESTIGATION · HHGOA 2026
          </div>
        </div>
      </div>

      <div className="h-7 w-px bg-line" />

      {/* agent status */}
      <div className="flex items-center gap-2">
        <span className="flex items-center gap-1.5 rounded border border-ok/40 bg-ok/10 px-2 py-1 text-[10px] font-bold tracking-[0.14em] text-ok">
          <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-ok" />
          AGENT ONLINE
        </span>
        <Chip
          tone={tg?.ok ? "ok" : tg ? "bad" : "neutral"}
          title={
            tg
              ? `RESTPP ${tg.endpoint ?? ""} ${tg.http_status} · ${tg.latency_ms}ms`
              : "probing TigerGraph RESTPP"
          }
        >
          TIGERGRAPH {tg ? `${tg.http_status}` : "…"}
        </Chip>
        <Chip tone="accent" title="scripts/validate_cases.py">
          VALIDATION 20/20
        </Chip>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <div className="flex items-center gap-1.5 border border-line bg-ink-850 px-2 py-1">
          <span className="label">CASE</span>
          <span className="font-mono text-[13px] font-bold text-accent">
            {activeCase}
          </span>
        </div>
        <div className="flex items-center gap-1.5 border border-line bg-ink-850 px-2 py-1">
          <span className="label">INVESTIGATION</span>
          <span
            className={`text-[11px] font-bold tracking-[0.1em] ${
              complete ? "text-ok" : replaying ? "text-accent" : "text-warn"
            }`}
          >
            {replaying
              ? `RUNNING ${replayStage + 1}/9`
              : complete
                ? "COMPLETE"
                : "ACTIVE"}
          </span>
        </div>

        <button
          type="button"
          onClick={onRun}
          disabled={replaying}
          className="h-8 rounded-sm border border-accent/60 bg-accent/15 px-3 text-[11px] font-bold tracking-[0.1em] text-accent transition hover:bg-accent/25 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {replaying ? "▶ RUNNING…" : "▶ RUN INVESTIGATION"}
        </button>

        <button
          type="button"
          onClick={onOpenCase}
          className="h-8 rounded-sm border border-line bg-ink-850 px-3 text-[11px] font-semibold tracking-[0.08em] text-fg-2 hover:border-ink-600 hover:text-fg"
        >
          CASE RECORD
        </button>
        <button
          type="button"
          onClick={onOpenArch}
          className="h-8 rounded-sm border border-line bg-ink-850 px-3 text-[11px] font-semibold tracking-[0.08em] text-fg-2 hover:border-ink-600 hover:text-fg"
        >
          SYSTEM ARCHITECTURE
        </button>
      </div>
    </header>
  );
}

export function CaseSidebar({
  rows,
  active,
  onSelect,
  counts,
  sar,
}: {
  rows: CaseSummaryRow[];
  active: string;
  onSelect: (id: string) => void;
  counts: { fraud: number; legitimate: number; uncertain: number };
  sar: number;
}) {
  return (
    <aside className="flex w-[236px] shrink-0 flex-col border-r border-line bg-ink-900">
      <div className="flex h-7 items-center justify-between border-b border-line bg-ink-850 px-2.5">
        <span className="label">CASE QUEUE</span>
        <span className="text-[9.5px] font-mono text-dim">
          {rows.filter((r) => r.ok).length}/{rows.length}
        </span>
      </div>

      <nav className="min-h-0 flex-1 overflow-auto">
        {rows.map((r) => {
          const isSel = r.case_id === active;
          const color = verdictColor(r.verdict);
          return (
            <button
              key={r.case_id}
              type="button"
              onClick={() => onSelect(r.case_id)}
              className={`group flex w-full items-center gap-2 border-b border-line/70 px-2 py-[7px] text-left transition ${
                isSel ? "bg-accent/10" : "hover:bg-ink-800"
              }`}
              style={
                isSel ? { boxShadow: "inset 2px 0 0 var(--color-accent)" } : undefined
              }
            >
              <span
                className="h-6 w-1 shrink-0 rounded-sm"
                style={{ background: color }}
              />
              <span className="min-w-0 flex-1">
                <span
                  className={`block font-mono text-[12px] leading-4 ${
                    isSel ? "font-bold text-accent" : "text-fg"
                  }`}
                >
                  {r.case_id}
                </span>
                <span className="block truncate text-[9.5px] leading-3 text-dim">
                  {r.pattern === "none" ? "no pattern" : r.pattern}
                </span>
              </span>
              <span className="flex flex-col items-end gap-[2px]">
                <span
                  className="font-mono text-[9px] font-bold tracking-wider"
                  style={{ color }}
                >
                  {verdictShort(r.verdict)}
                </span>
                <span className="font-mono text-[9px] text-dim">
                  {r.fraud_probability.toFixed(2)}
                </span>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="shrink-0 border-t border-line bg-ink-850 p-2.5">
        <div className="label mb-1.5">QUEUE SUMMARY</div>
        <div className="grid grid-cols-2 gap-1.5 text-[11px]">
          <Stat label="CASES" value={rows.length} />
          <Stat label="SAR" value={sar} tone="var(--color-bad)" />
          <Stat label="FRAUD" value={counts.fraud} tone="var(--color-bad)" />
          <Stat
            label="UNCERTAIN"
            value={counts.uncertain}
            tone="var(--color-warn)"
          />
          <Stat
            label="LEGITIMATE"
            value={counts.legitimate}
            tone="var(--color-ok)"
          />
          <Stat label="VALIDATION" value="PASS" tone="var(--color-ok)" />
        </div>
      </div>
    </aside>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  return (
    <div className="border border-line bg-ink-900 px-1.5 py-1">
      <div className="text-[8.5px] tracking-[0.12em] text-dim">{label}</div>
      <div
        className="font-mono text-[13px] leading-4 font-bold"
        style={tone ? { color: tone } : undefined}
      >
        {value}
      </div>
    </div>
  );
}
