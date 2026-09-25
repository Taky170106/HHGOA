"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import GraphCanvas from "@/components/GraphCanvas";
import { AgentPipeline } from "@/components/AgentPipeline";
import { ActionPanel, EvidencePanel, MlPanel, XaiPanel } from "@/components/Panels";
import { CaseDrawer, NodeDetails } from "@/components/Overlays";
import {
  Button,
  Card,
  Container,
  ErrorNote,
  Fill,
  Loading,
  Tag,
} from "@/components/kit";
import { verdictColor, verdictShort } from "@/lib/classify";
import { buildGraph } from "@/lib/graph";
import { useJson, useSummary } from "@/lib/useJson";
import type { CasePayload, CaseSummaryRow, SummaryPayload } from "@/lib/types";

const TABS = [
  "GRAPH",
  "INVESTIGATION",
  "EVIDENCE",
  "MODEL & XAI",
  "NEXT BEST ACTION",
  "CASE RECORD",
];

export default function CasePage() {
  const params = useParams<{ id: string }>();
  const id = (
    typeof params?.id === "string" ? params.id : "HHG-001"
  ).toUpperCase();

  const [tab, setTab] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [recTab, setRecTab] = useState(0);

  const { data, error, loading } = useJson<CasePayload>(`/api/case/${id}`);
  const summary = useSummary();

  if (error) return <ErrorNote what={id} message={error} />;
  if (loading || !data) return <Loading what={`cases/${id}.json`} />;

  const cf = data.caseFile;
  const color = verdictColor(cf.case.verdict);

  const rows: CaseSummaryRow[] = summary.data?.cases ?? [];
  const idx = rows.findIndex((r) => r.case_id === id);
  const prev = idx > 0 ? rows[idx - 1] : null;
  const next = idx >= 0 && idx < rows.length - 1 ? rows[idx + 1] : null;

  return (
    <div className="fade-up pb-14">
      {/* ---------------- case header ---------------- */}
      <header className="border-b border-line bg-ink-950 pt-7 pb-0">
        <Container>
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/cases"
              className="text-[10.5px] font-bold tracking-[0.16em] text-dim uppercase hover:text-accent"
            >
              ← Case section
            </Link>
            <span className="h-3.5 w-px bg-line" />
            <span className="font-mono text-[26px] leading-7 font-bold text-fg">
              {cf.case_id}
            </span>
            <span
              className="border px-2 py-[3px] font-mono text-[11px] font-bold tracking-[0.1em]"
              style={{ color, borderColor: `${color}80` }}
            >
              {cf.case.verdict.toUpperCase()}
            </span>
            <Tag tone="neutral">{cf.case.status}</Tag>
            {cf.sar.file ? <Tag tone="bad">SAR FILED</Tag> : <Tag>no SAR</Tag>}
            <Tag tone="accent">{cf.case.pattern}</Tag>

            <div className="ml-auto flex items-center gap-2">
              {prev ? (
                <Link
                  href={`/cases/${prev.case_id}`}
                  className="h-8 border border-line px-2.5 text-[11px] text-fg-2 hover:border-ink-600 hover:text-fg"
                >
                  ← {prev.case_id}
                </Link>
              ) : null}
              {next ? (
                <Link
                  href={`/cases/${next.case_id}`}
                  className="h-8 border border-line px-2.5 text-[11px] text-fg-2 hover:border-ink-600 hover:text-fg"
                >
                  {next.case_id} →
                </Link>
              ) : null}
              <Link
                href={`/investigation?case=${cf.case_id}`}
                className="inline-flex h-8 items-center border border-accent/60 bg-accent/15 px-3 text-[11px] font-bold tracking-[0.1em] text-accent hover:bg-accent/25"
              >
                ▶ RUN THIS CASE
              </Link>
            </div>
          </div>

          {/* fact strip */}
          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 border-t border-line pt-3 pb-4 sm:grid-cols-3 lg:grid-cols-6">
            <Fact
              k="fraud_probability"
              v={cf.case.fraud_probability.toFixed(4)}
              tone={color}
            />
            <Fact
              k="exposure"
              v={`$${cf.case.exposure_usd.toFixed(2)}`}
            />
            <Fact k="evidence" v={`${cf.case.evidence.length} items`} />
            <Fact k="graph edges" v={`${cf.graph_evidence.edges.length}`} />
            <Fact
              k="tool calls / tokens"
              v={`${cf.tool_calls} / ${cf.tokens}`}
            />
            <Fact k="recorded latency" v={`${cf.latency_s.toFixed(2)}s`} />
          </dl>

          {/* tabs */}
          <nav className="flex gap-1 overflow-x-auto">
            {TABS.map((t, i) => (
              <button
                key={t}
                type="button"
                onClick={() => setTab(i)}
                className={`relative px-4 py-3 text-[11px] font-bold tracking-[0.12em] whitespace-nowrap transition ${
                  tab === i ? "text-accent" : "text-fg-2 hover:text-fg"
                }`}
              >
                {t}
                <span
                  className={`absolute inset-x-2 bottom-0 h-[2px] ${
                    tab === i ? "bg-accent" : "bg-transparent"
                  }`}
                />
              </button>
            ))}
          </nav>
        </Container>
      </header>

      <Container className="pt-6">
        {tab === 0 && <GraphTab cf={cf} selected={selected} setSelected={setSelected} />}
        {tab === 1 && (
          <InvestigationTab
            payload={data}
            metrics={summary.data?.metrics ?? null}
          />
        )}
        {tab === 2 && <EvidenceTab cf={cf} />}
        {tab === 3 && (
          <ModelTab payload={data} metrics={summary.data?.metrics ?? null} />
        )}
        {tab === 4 && <ActionsTab cf={cf} />}
        {tab === 5 && (
          <Fill className="h-[720px]">
            <CaseDrawer
              cf={cf}
              shapLocal={data.shapLocal}
              open
              tab={recTab}
              setTab={setRecTab}
              variant="inline"
            />
          </Fill>
        )}
      </Container>
    </div>
  );
}

function Fact({ k, v, tone }: { k: string; v: string; tone?: string }) {
  return (
    <div>
      <dt className="text-[9px] tracking-[0.16em] text-dim uppercase">{k}</dt>
      <dd
        className="font-mono text-[13px] font-semibold"
        style={tone ? { color: tone } : undefined}
      >
        {v}
      </dd>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* tab 1 — graph                                                       */
/* ------------------------------------------------------------------ */

function GraphTab({
  cf,
  selected,
  setSelected,
}: {
  cf: CasePayload["caseFile"];
  selected: string | null;
  setSelected: (v: string | null) => void;
}) {
  const graph = buildGraph(cf);
  const ge = cf.graph_evidence;

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card
        title="GRAPH INVESTIGATION"
        right={
          <span className="font-mono text-[10px] text-dim">
            {ge.edges.length} edges · zoom / pan / select
          </span>
        }
        bodyClass="p-0"
      >
        <div className="relative h-[620px]">
          <GraphCanvas
            nodes={graph.nodes}
            edges={graph.edges}
            selected={selected}
            onSelect={setSelected}
          />
          {selected ? (
            <NodeDetails
              cf={cf}
              nodeId={selected}
              onClose={() => setSelected(null)}
            />
          ) : null}
          <div className="pointer-events-none absolute bottom-2 left-2 border border-line bg-ink-900/90 px-2 py-1 font-mono text-[9.5px] text-dim">
            source: graph_evidence — LLM cannot invent these relationships
          </div>
        </div>
      </Card>

      <div className="space-y-4">
        <Card title="LIVE QUERIES" right={<Tag tone="ok">READ ONLY</Tag>}>
          <div className="space-y-1.5">
            {ge.queries.map((q) => (
              <div key={q.name} className="border border-line bg-ink-850 px-2 py-1.5">
                <div className="flex items-center gap-2 font-mono text-[10.5px]">
                  <span className={q.http_status === 200 ? "text-ok" : "text-bad"}>
                    {q.http_status}
                  </span>
                  <span className="text-fg">{q.name}</span>
                  <span className="ml-auto text-dim">{q.latency_ms}ms</span>
                </div>
                <div className="mt-0.5 truncate font-mono text-[9.5px] text-dim">
                  {Object.entries(q.params)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(" ") || "no params"}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card title="GRAPH FACTS">
          <ul className="space-y-1.5">
            {ge.graph_facts.map((f, i) => (
              <li
                key={i}
                className="border-l-2 border-accent/50 pl-2 text-[11.5px] leading-[17px] text-fg-2"
              >
                {f}
              </li>
            ))}
          </ul>
        </Card>

        <Card title="FACT vs INTERPRETATION">
          <p className="text-[11.5px] leading-[18px] text-fg-2">
            {ge.graph_fact_vs_interpretation}
          </p>
        </Card>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* tab 2 — investigation                                               */
/* ------------------------------------------------------------------ */

function InvestigationTab({
  payload,
  metrics,
}: {
  payload: CasePayload;
  metrics: SummaryPayload["metrics"] | null;
}) {
  const cf = payload.caseFile;
  const pre = cf.pre_additional_evidence_state;
  const post = cf.post_additional_evidence_state;
  const pd = pre?.preliminary_decision;

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_344px]">
      <div className="space-y-4">
        <Card title="TWO-STAGE DECISION RECORD">
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="border border-line bg-ink-850 p-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold tracking-[0.14em] text-warn uppercase">
                  Pre additional evidence
                </span>
                <Tag tone="warn">{pre?.stage ?? "—"}</Tag>
              </div>
              <p className="mt-2 font-mono text-[11.5px] text-fg-2">
                {pd
                  ? `${pd.verdict} · p=${pd.fraud_probability.toFixed(4)} · pattern ${pd.pattern}`
                  : "—"}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {cf.next_best_actions.initial.map((a) => (
                  <Tag key={a.action} tone="warn">
                    {a.action}
                  </Tag>
                ))}
              </div>
              <div className="mt-2 text-[10.5px] leading-[16px] text-dim">
                evidence requested:{" "}
                {pre?.evidence_requested?.map((r) => r.type).join(", ") || "none"}
              </div>
            </div>

            <div className="border border-line bg-ink-850 p-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold tracking-[0.14em] text-ok uppercase">
                  Post additional evidence
                </span>
                <Tag tone={post?.additional_evidence_received ? "ok" : "warn"}>
                  received:{" "}
                  {String(post?.additional_evidence_received ?? false)}
                </Tag>
              </div>
              <p className="mt-2 font-mono text-[11.5px] text-fg-2">
                {cf.decision.decision} · p={cf.case.fraud_probability.toFixed(4)}{" "}
                · pattern {cf.case.pattern}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {cf.next_best_actions.final.map((a) => (
                  <Tag key={a.action} tone="ok">
                    {a.action}
                  </Tag>
                ))}
              </div>
              <div className="mt-2 text-[10.5px] leading-[16px] text-dim">
                status {cf.decision.status} · approval{" "}
                {cf.required_approval_route.join(", ")}
              </div>
            </div>
          </div>

          <div className="mt-3 border border-line bg-ink-850 p-3">
            <div className="text-[10px] font-bold tracking-[0.14em] text-dim uppercase">
              What changed
            </div>
            <p className="mt-1 text-[12px] leading-[19px] text-fg-2">
              {cf.next_best_actions.what_changed}
            </p>
          </div>
        </Card>

        <Card
          title="INVESTIGATION RECORD"
          right={<span className="font-mono text-[10px] text-dim">{cf.stop_reason.slice(0, 0)}{cf.latency_s.toFixed(2)}s recorded</span>}
        >
          <ol className="space-y-2">
            {cf.investigation_record.map((s) => (
              <li
                key={s.step}
                className="flex gap-3 border border-line bg-ink-850 px-3 py-2"
              >
                <span className="font-mono text-[11px] text-accent">
                  {String(s.step).padStart(2, "0")}
                </span>
                <div className="min-w-0">
                  <div className="text-[11.5px] font-bold tracking-[0.08em] text-fg">
                    {s.name}
                  </div>
                  <p className="mt-0.5 text-[11.5px] leading-[17px] text-fg-2">
                    {s.detail}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </Card>

        <Card title="AUDIT">
          <div className="grid gap-3 font-mono text-[11.5px] sm:grid-cols-2">
            <div className="flex justify-between border-b border-line/60 pb-1">
              <span className="text-dim">tool_calls</span>
              <span className="text-fg">{cf.tool_calls}</span>
            </div>
            <div className="flex justify-between border-b border-line/60 pb-1">
              <span className="text-dim">tokens</span>
              <span className="text-fg">{cf.tokens} — no LLM key</span>
            </div>
            <div className="flex justify-between border-b border-line/60 pb-1">
              <span className="text-dim">latency_s</span>
              <span className="text-fg">{cf.latency_s.toFixed(2)}</span>
            </div>
            <div className="flex justify-between border-b border-line/60 pb-1">
              <span className="text-dim">stop_reason</span>
              <span className="max-w-[62%] truncate text-right text-fg">
                {cf.stop_reason}
              </span>
            </div>
          </div>
          <p className="mt-3 border-t border-line pt-2 text-[11px] leading-[17px] text-dim">
            {cf.stop_reason}
          </p>
        </Card>
      </div>

      <div className="space-y-4">
        <AgentPipeline
          cf={cf}
          shapLocal={payload.shapLocal}
          e2e={payload.e2e}
          stage={9}
          replaying={false}
        />
        {metrics ? (
          <Card title="MODEL INPUTS FOR THIS RUN">
            <div className="space-y-1 font-mono text-[11px] text-fg-2">
              <div className="flex justify-between">
                <span className="text-dim">model</span>
                <span>{metrics.model.split(".").pop()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-dim">features</span>
                <span>{metrics.n_features}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-dim">e2e wall clock</span>
                <span>{payload.e2e?.wall_clock_s.toFixed(2) ?? "—"}s</span>
              </div>
              <div className="flex justify-between">
                <span className="text-dim">live GSQL calls</span>
                <span>
                  {Array.isArray(payload.e2e?.live_gsql_calls)
                    ? `${payload.e2e.live_gsql_calls.length} queries recorded`
                    : payload.e2e?.live_gsql_calls ?? "—"}
                </span>
              </div>
            </div>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* tab 3 — evidence                                                    */
/* ------------------------------------------------------------------ */

function EvidenceTab({ cf }: { cf: CasePayload["caseFile"] }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Fill className="h-[680px]">
        <EvidencePanel cf={cf} />
      </Fill>

      <div className="space-y-4">
        <Card
          title="FINDINGS"
          right={<Tag tone="accent">{cf.findings.length}</Tag>}
        >
          <div className="space-y-2">
            {cf.findings.map((f) => (
              <div key={f.finding_id} className="border border-line bg-ink-850 p-2.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10.5px] font-bold text-accent">
                    {f.finding_id}
                  </span>
                  <span className="text-[12px] font-semibold text-fg">
                    {f.title}
                  </span>
                  <span className="ml-auto text-[9px] tracking-wider text-dim uppercase">
                    {f.type.replace("_", " ")}
                  </span>
                </div>
                <p className="mt-1 text-[11.5px] leading-[17px] text-fg-2">
                  {f.statement}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {f.evidence_ids.map((e) => (
                    <Tag key={e}>{e}</Tag>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card
          title="ADDITIONAL EVIDENCE CHAIN"
          right={
            <Tag tone={cf.evidence_requests.length ? "ok" : "neutral"}>
              {cf.evidence_requests.length ? "INSUFFICIENT → ACQUIRED" : "NOT REQUIRED"}
            </Tag>
          }
        >
          {cf.evidence_requests.length ? (
            <div className="space-y-2">
              {cf.evidence_requests.map((r, i) => (
                <div key={i} className="border border-line bg-ink-850 p-2.5">
                  <div className="flex items-center gap-2 font-mono text-[10.5px]">
                    <span className="text-accent">{r.type}</span>
                    <span className="text-dim">after step {r.asked_after_step}</span>
                  </div>
                  <p className="mt-1 text-[11.5px] leading-[17px] text-fg-2">
                    “{r.assumed_response}”
                  </p>
                </div>
              ))}
              <div className="border-l-2 border-accent/60 pl-2 text-[11px] leading-[17px] text-dim">
                {cf.post_additional_evidence_state.additional_evidence_received
                  ? "Recorded as received, then re-investigated — the decision above is the post-evidence state."
                  : "Requested but no response recorded."}
              </div>
            </div>
          ) : (
            <p className="text-[11.5px] leading-[17px] text-dim">
              No additional evidence was requested. {cf.stop_reason}
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* tab 4 — model & xai                                                 */
/* ------------------------------------------------------------------ */

function ModelTab({
  payload,
  metrics,
}: {
  payload: CasePayload;
  metrics: SummaryPayload["metrics"] | null;
}) {
  const cf = payload.caseFile;
  if (!metrics) return <Loading what="models/metrics.json" />;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-2">
        <Fill className="h-[420px]">
          <MlPanel
            cf={cf}
            shapLocal={payload.shapLocal}
            e2e={payload.e2e}
            metrics={metrics}
          />
        </Fill>
        <Fill className="h-[420px]">
          <XaiPanel shapLocal={payload.shapLocal} shapGlobal={payload.shapGlobal} />
        </Fill>
      </div>

      <Card title="HOW TO READ THIS">
        <div className="grid gap-3 text-[11.5px] leading-[18px] text-fg-2 lg:grid-cols-3">
          <p>
            <span className="font-bold text-fg">Model score</span> is the
            classifier output for this case from{" "}
            <span className="font-mono">validation/phase3_e2e.json</span> — an
            input to the decision, not the decision itself.
          </p>
          <p>
            <span className="font-bold text-fg">risk_score</span> is the
            pre-computed dataset column. It is excluded from training as label
            leakage and shown only as context.
          </p>
          <p>
            <span className="font-bold text-fg">SHAP</span> decomposes that score
            into per-feature contributions: red pushes toward fraud, green
            pushes back toward legitimate.
          </p>
        </div>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* tab 5 — next best action                                            */
/* ------------------------------------------------------------------ */

function ActionsTab({ cf }: { cf: CasePayload["caseFile"] }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Fill className="h-[520px]">
        <ActionPanel cf={cf} />
      </Fill>

      <div className="space-y-4">
        <Card title="ACTIONS TAKEN">
          <div className="space-y-1.5">
            {cf.actions_taken.map((a) => (
              <div
                key={a.action}
                className="flex items-center gap-2 border border-line bg-ink-850 px-2.5 py-1.5"
              >
                <span className="font-mono text-[11px] text-fg">{a.action}</span>
                <span className="ml-auto font-mono text-[9.5px] text-dim">
                  {a.route}
                </span>
              </div>
            ))}
          </div>
        </Card>

        {!!cf.actions_recommended_awaiting_approval?.length && (
          <Card title="AWAITING APPROVAL" right={<Tag tone="warn">L1 / L2</Tag>}>
            <div className="space-y-1.5">
              {cf.actions_recommended_awaiting_approval.map((a) => (
                <div
                  key={a.action}
                  className="flex items-center gap-2 border border-warn/40 bg-warn/5 px-2.5 py-1.5"
                >
                  <span className="font-mono text-[11px] text-warn">
                    {a.action}
                  </span>
                  <span className="ml-auto font-mono text-[9.5px] text-dim">
                    {a.route}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Card title="APPROVAL ROUTE & SAR">
          <div className="space-y-1 font-mono text-[11.5px]">
            <div className="flex justify-between border-b border-line/60 pb-1">
              <span className="text-dim">route</span>
              <span className="text-fg">{cf.required_approval_route.join(", ")}</span>
            </div>
            <div className="flex justify-between border-b border-line/60 pb-1">
              <span className="text-dim">sar filed</span>
              <span className={cf.sar.file ? "text-bad" : "text-ok"}>
                {String(cf.sar.file)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-dim">graph write</span>
              <span className="text-bad">{cf.graph_write.status}</span>
            </div>
          </div>
          <p className="mt-2 text-[11.5px] leading-[17px] text-fg-2">
            {cf.sar_status.reason}
          </p>
        </Card>

        <Card title="CASE SUMMARY">
          <p className="text-[12px] leading-[19px] text-fg-2">{cf.case.summary}</p>
        </Card>
      </div>
    </div>
  );
}
