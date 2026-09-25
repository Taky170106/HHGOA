"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  Counterfactual,
  STAGES,
  Sufficiency,
  stageDetail,
  truncate,
} from "@/components/AgentPipeline";
import {
  Button,
  Card,
  Container,
  ErrorNote,
  Loading,
  PageHeader,
  Tag,
} from "@/components/kit";
import { verdictColor, verdictShort } from "@/lib/classify";
import { useJson, useSummary } from "@/lib/useJson";
import type { CasePayload, CaseSummaryRow } from "@/lib/types";

const RUN_MS = 6800; // 5–8s animation window
const STEP = RUN_MS / STAGES.length;

export default function InvestigationPage() {
  const { data: summary, error: sumErr, loading: sumLoad } = useSummary();
  const [caseId, setCaseId] = useState("HHG-001");
  const [q, setQ] = useState("");
  const [stage, setStage] = useState(STAGES.length);
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  const { data, error, loading } = useJson<CasePayload>(`/api/case/${caseId}`);

  const timeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ticker = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAt = useRef(0);

  /* honour /investigation?case=HHG-014 deep links */
  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get("case");
    if (wanted) setCaseId(wanted.toUpperCase());
  }, []);

  const stopTimers = () => {
    if (timeout.current) clearTimeout(timeout.current);
    if (ticker.current) clearInterval(ticker.current);
    timeout.current = null;
    ticker.current = null;
  };

  useEffect(() => () => stopTimers(), []);

  /* switching case resets the run */
  useEffect(() => {
    stopTimers();
    setRunning(false);
    setStage(STAGES.length);
    setElapsed(0);
  }, [caseId]);

  const run = () => {
    if (running) return;
    stopTimers();
    setRunning(true);
    setStage(0);
    setElapsed(0);
    startedAt.current = Date.now();

    ticker.current = setInterval(() => {
      setElapsed((Date.now() - startedAt.current) / 1000);
    }, 80);

    let i = 0;
    const tick = () => {
      i += 1;
      setStage(i);
      if (i >= STAGES.length) {
        if (ticker.current) clearInterval(ticker.current);
        ticker.current = null;
        setElapsed((Date.now() - startedAt.current) / 1000);
        setRunning(false);
        return;
      }
      timeout.current = setTimeout(tick, STEP);
    };
    timeout.current = setTimeout(tick, STEP);
  };

  const rows: CaseSummaryRow[] = summary?.cases ?? [];
  const visible = useMemo(() => {
    const n = q.trim().toLowerCase();
    if (!n) return rows;
    return rows.filter(
      (r) =>
        r.case_id.toLowerCase().includes(n) ||
        r.pattern.toLowerCase().includes(n) ||
        r.verdict.includes(n),
    );
  }, [rows, q]);

  const cf = data?.caseFile ?? null;

  if (sumErr) return <ErrorNote what="/api/summary" message={sumErr} />;
  if (sumLoad || !summary) return <Loading what="cases/validation_report.json" />;

  return (
    <div className="fade-up pb-14">
      <PageHeader
        eyebrow="MODULE 03 · RUN INVESTIGATION"
        title="Execute the nine-stage agent pipeline"
        lede={
          <>
            Pick a case and press run: the console walks{" "}
            <span className="font-mono text-fg">
              TRIGGER → TRIAGE → GRAPH INVESTIGATION → EVIDENCE → ML ANALYSIS →
              XAI → UNCERTAINTY → POLICY → NEXT BEST ACTION
            </span>{" "}
            and shows the recorded detail of each stage as it completes. Stage
            text is read from the case record — this is a{" "}
            <span className="text-accent">DEMO REPLAY</span> of a validated run,
            not a new model execution.
          </>
        }
        actions={
          <>
            <Button
              variant="primary"
              onClick={run}
              disabled={running || loading}
              title="Replay the validated record for the selected case"
            >
              {running ? `▶ RUNNING ${stage}/9` : "▶ RUN INVESTIGATION"}
            </Button>
            <Button href={`/cases/${caseId}`}>OPEN CASE RECORD</Button>
          </>
        }
        meta={
          <span className="font-mono text-[10px] text-dim">
            live run: python scripts/demo_hhg001.py
          </span>
        }
      />

      <Container className="pt-6">
        <div className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)_340px]">
          {/* ---------- case picker ---------- */}
          <Card title="SELECT CASE" right={<Tag>{rows.length}</Tag>} bodyClass="p-0">
            <div className="border-b border-line p-2.5">
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="id, pattern, verdict…"
                className="h-8 w-full rounded-sm border border-line bg-ink-950 px-2.5 font-mono text-[11.5px] text-fg outline-none placeholder:text-dim focus:border-accent/60"
              />
            </div>
            <div className="max-h-[560px] overflow-auto">
              {visible.map((r) => {
                const active = r.case_id === caseId;
                const c = verdictColor(r.verdict);
                return (
                  <button
                    key={r.case_id}
                    type="button"
                    onClick={() => setCaseId(r.case_id)}
                    className={`flex w-full items-center gap-2 border-b border-line/70 px-2.5 py-2 text-left transition ${
                      active ? "bg-accent/10" : "hover:bg-ink-850"
                    }`}
                    style={
                      active
                        ? { boxShadow: "inset 2px 0 0 var(--color-accent)" }
                        : undefined
                    }
                  >
                    <span
                      className="h-6 w-1 shrink-0 rounded-sm"
                      style={{ background: c }}
                    />
                    <span className="min-w-0 flex-1">
                      <span
                        className={`block font-mono text-[12px] ${
                          active ? "font-bold text-accent" : "text-fg"
                        }`}
                      >
                        {r.case_id}
                      </span>
                      <span className="block truncate text-[9.5px] text-dim">
                        {r.pattern === "none" ? "no pattern" : r.pattern}
                      </span>
                    </span>
                    <span className="flex flex-col items-end">
                      <span
                        className="font-mono text-[9px] font-bold"
                        style={{ color: c }}
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
              {!visible.length && (
                <div className="px-3 py-6 text-center text-[11px] text-dim">
                  No case matches.
                </div>
              )}
            </div>
          </Card>

          {/* ---------- run timeline ---------- */}
          <Card
            title={`PIPELINE · ${caseId}`}
            right={
              <span className="flex items-center gap-2 font-mono text-[10px]">
                <span className="text-dim">elapsed</span>
                <span className="text-accent">{elapsed.toFixed(2)}s</span>
                <span className="text-dim">/ recorded</span>
                <span className="text-fg-2">
                  {cf ? `${cf.latency_s.toFixed(2)}s` : "—"}
                </span>
              </span>
            }
            bodyClass="p-0"
          >
            <div className="flex items-center gap-3 border-b border-line bg-ink-950 px-3.5 py-2.5">
              <span
                className={`h-2 w-2 rounded-full ${
                  running ? "pulse-dot bg-accent" : "bg-ok"
                }`}
              />
              <span className="text-[10.5px] font-bold tracking-[0.16em] text-fg-2 uppercase">
                {running
                  ? `Running stage ${stage + 1} of 9`
                  : stage >= 9
                    ? "Run complete — result below"
                    : "Ready"}
              </span>
              <span className="ml-auto">
                <Tag tone="warn">DEMO REPLAY</Tag>
              </span>
            </div>

            <ol className="p-3">
              {STAGES.map((s, i) => {
                const done = i < stage;
                const active = running && i === stage - 1;
                return (
                  <li
                    key={s.key}
                    className={`flex gap-3 border-b border-line/60 py-2.5 last:border-0 ${
                      done ? "stage-in" : ""
                    } ${done ? "" : "opacity-45"}`}
                  >
                    <div className="flex w-5 shrink-0 flex-col items-center">
                      <span
                        className={`flex h-5 w-5 items-center justify-center rounded-full border font-mono text-[9.5px] ${
                          done
                            ? "border-ok/70 bg-ok/15 text-ok"
                            : active
                              ? "border-accent/70 bg-accent/15 text-accent"
                              : "border-line text-dim"
                        }`}
                      >
                        {done ? "✓" : i + 1}
                      </span>
                      {i < STAGES.length - 1 && (
                        <span
                          className={`mt-1 w-px flex-1 ${
                            done ? "bg-ok/40" : "bg-line"
                          }`}
                        />
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[11.5px] font-bold tracking-[0.1em] text-fg">
                          {s.key}
                        </span>
                        <span
                          className={`font-mono text-[9px] tracking-[0.1em] uppercase ${
                            done ? "text-ok" : "text-dim"
                          }`}
                        >
                          {done ? "complete" : active ? "running" : "pending"}
                        </span>
                      </div>
                      <p className="mt-0.5 text-[11.5px] leading-[17px] text-fg-2">
                        {done && cf && data
                          ? truncate(
                              stageDetail(cf, data.shapLocal, data.e2e, s),
                              220,
                            )
                          : "waiting for the previous stage…"}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ol>

            <div className="border-t border-line bg-ink-950 px-3.5 py-2.5 text-[10.5px] leading-[16px] text-dim">
              Playback only: the stage text is the recorded content of{" "}
              <span className="font-mono text-fg-2">cases/{caseId}.json</span>{" "}
              and <span className="font-mono text-fg-2">validation/phase3_e2e.json</span>.
              The model is not re-scored and nothing is written to TigerGraph.
            </div>
          </Card>

          {/* ---------- result ---------- */}
          <div className="space-y-4">
            <Card
              title="RESULT"
              right={
                cf ? (
                  <Tag
                    tone={
                      cf.case.verdict === "fraud"
                        ? "bad"
                        : cf.case.verdict === "legitimate"
                          ? "ok"
                          : "warn"
                    }
                  >
                    {cf.case.verdict.toUpperCase()}
                  </Tag>
                ) : null
              }
            >
              {error ? (
                <p className="text-[11.5px] text-bad">{error}</p>
              ) : loading || !cf ? (
                <Loading what={`cases/${caseId}.json`} />
              ) : (
                <>
                  <div className="font-mono text-[19px] font-bold text-fg">
                    {cf.case_id}
                  </div>
                  <div className="mt-0.5 text-[11.5px] text-fg-2">
                    {cf.case.pattern === "none"
                      ? "no fraud pattern"
                      : cf.case.pattern}
                    {" — "}
                    {cf.case.status}
                  </div>

                  <div className="mt-3 space-y-1.5 font-mono text-[11.5px]">
                    <Row k="fraud_probability" v={cf.case.fraud_probability.toFixed(4)} tone={verdictColor(cf.case.verdict)} />
                    <Row k="exposure" v={`$${cf.case.exposure_usd.toFixed(2)}`} />
                    <Row k="evidence" v={`${cf.case.evidence.length} items`} />
                    <Row k="sar" v={String(cf.sar.file)} tone={cf.sar.file ? "var(--color-bad)" : "var(--color-ok)"} />
                    <Row k="approval" v={cf.required_approval_route.join(", ")} />
                    <Row k="graph write" v={cf.graph_write.status} tone="var(--color-bad)" />
                  </div>

                  <div className="mt-3 border border-line bg-ink-850 p-2.5">
                    <div className="text-[9.5px] tracking-[0.16em] text-dim uppercase">
                      Next best action
                    </div>
                    <div className="mt-1 font-mono text-[12.5px] font-bold text-accent">
                      {cf.next_best_actions.final[0]?.action ?? "—"}
                    </div>
                    <p className="mt-1 text-[11px] leading-[16px] text-fg-2">
                      {cf.next_best_actions.what_changed}
                    </p>
                  </div>

                  <div className="mt-3 flex gap-2">
                    <Link
                      href={`/cases/${cf.case_id}`}
                      className="inline-flex h-8 flex-1 items-center justify-center border border-line bg-ink-900 text-[10.5px] font-bold tracking-[0.1em] text-fg-2 hover:border-accent/60 hover:text-accent"
                    >
                      OPEN FULL CASE
                    </Link>
                  </div>
                </>
              )}
            </Card>

            {cf ? (
              <>
                <Sufficiency cf={cf} />
                <Counterfactual cf={cf} />
              </>
            ) : null}
          </div>
        </div>
      </Container>
    </div>
  );
}

function Row({ k, v, tone }: { k: string; v: string; tone?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-line/60 pb-1 last:border-0">
      <span className="text-dim">{k}</span>
      <span className="font-semibold" style={tone ? { color: tone } : undefined}>
        {v}
      </span>
    </div>
  );
}
