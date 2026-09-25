"use client";

import {
  Card,
  ErrorNote,
  Loading,
  PageHeader,
  Section,
  StatTile,
  Tag,
} from "@/components/kit";
import { ARCHITECTURE, STATUS_LABEL, type LayerStatus } from "@/lib/architecture";
import { useJson, useSummary, useTigerGraph } from "@/lib/useJson";

/** Shape returned by app/api/agent — the LangGraph runs on disk. */
interface AgentRunLite {
  case_id: string;
  llm_status: string | null;
  tokens: number | null;
}
interface AgentData {
  batch: {
    runs_total?: number;
    passed?: number;
    tokens_total?: number;
    tool_calls_total?: number;
  } | null;
  runs: AgentRunLite[];
}

const TONE: Record<LayerStatus, { text: string; border: string; bg: string }> = {
  live: { text: "var(--color-ok)", border: "border-ok/45", bg: "bg-ok/10" },
  wip: { text: "var(--color-warn)", border: "border-warn/45", bg: "bg-warn/10" },
  arch: { text: "var(--color-dim)", border: "border-line-2", bg: "bg-ink-850" },
};

export default function ArchitecturePage() {
  const { data, error, loading } = useSummary();
  const tg = useTigerGraph();
  // must be declared before the early returns below (hooks are unconditional)
  const ag = useJson<AgentData>("/api/agent");

  if (error) return <ErrorNote what="/api/summary" message={error} />;
  if (loading || !data) return <Loading what="architecture artifacts" />;

  const live = ARCHITECTURE.filter((l) => l.status === "live");
  const wip = ARCHITECTURE.filter((l) => l.status === "wip");
  const arch = ARCHITECTURE.filter((l) => l.status === "arch");
  const gaps = [...wip, ...arch];

  // real LLM usage read from agent/runs/ — never a placeholder
  const runs = ag.data?.runs ?? [];
  const llmOk = runs.filter((r) => r.llm_status === "ok").length;
  const llmTokens = ag.data?.batch?.tokens_total ?? 0;

  const gsql = data.gsql;
  const mcp = data.mcp as Record<string, number | string>;

  return (
    <div className="fade-up pb-16">
      <PageHeader
        eyebrow="MODULE 05 · SYSTEM ARCHITECTURE"
        title="Every layer, with an honest status"
        lede="No layer is marked LIVE unless there is an artifact — or a runtime probe — behind it. Where the design describes something this repository does not implement, the row says ARCHITECTURAL instead of pretending it ran."
        actions={
          <span className="flex gap-2">
            <Tag tone="ok">{live.length} LIVE</Tag>
            <Tag tone="warn">{wip.length} IN PROGRESS</Tag>
            <Tag>{arch.length} ARCHITECTURAL</Tag>
          </span>
        }
        meta={
          <span className="font-mono text-[10px] text-dim">
            {ARCHITECTURE.length} layers · frontend/lib/architecture.ts
          </span>
        }
      />

      {/* ---------- live probes ---------- */}
      <Section
        eyebrow="RUNTIME PROBES"
        title="What is answering right now"
        lede="Probed when this page loads and refreshed every 30 seconds. A read-only RESTPP /echo call — the graph is never modified by the console."
      >
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
          <StatTile
            label="TigerGraph RESTPP"
            value={tg ? String(tg.http_status) : "…"}
            tone={tg?.ok ? "var(--color-ok)" : "var(--color-bad)"}
            sub={tg?.ok ? `${tg.latency_ms}ms · ${tg.endpoint}` : "not reachable"}
            source={tg?.endpoint}
          />
          <StatTile
            label="GSQL executed"
            value={gsql.queries_executed as string | number}
            tone="var(--color-ok)"
            sub={`${gsql.http_404_after_repair} http 404 · read-only`}
            source="docs/PHASE3_QUERY_CATALOG.json"
          />
          <StatTile
            label="MCP tools live"
            value={`${mcp.live_pass}/${mcp.live_total}`}
            tone="var(--color-ok)"
            sub={`${mcp.status}`}
            source="mcp/validation/phase3_mcp_live.json"
          />
          <StatTile
            label="Case validation"
            value={data.validation_status}
            tone="var(--color-ok)"
            sub={`${data.cases_passed}/${data.cases.length} · ${data.total_errors} errors`}
            source="cases/validation_report.json"
          />
          <StatTile
            label="Graph write"
            value="BLOCKED"
            tone="var(--color-bad)"
            sub={data.graph_write.reference}
            source="docs/GRAPH_WRITE_BLOCKER.md"
          />
          <StatTile
            label="Live tool calls"
            value={data.tool_calls.live}
            tone="var(--color-ok)"
            sub={`retrieval ${data.tool_calls.retrieval} · tokens 0`}
            source="cases/_build_summary.json"
          />
          <StatTile
            label="LLM calls"
            value={ag.loading ? "…" : String(runs.length)}
            tone={llmTokens > 0 ? "var(--color-ok)" : "var(--color-warn)"}
            sub={
              ag.data
                ? `${llmOk}/${runs.length} ok · ${llmTokens} tokens`
                : "reading agent/runs/…"
            }
            source="agent/runs/ · validation/phase4_agent_runs.json"
          />
        </div>
      </Section>

      {/* ---------- layer stack ---------- */}
      <Section
        eyebrow="LAYER STACK"
        title="Top to bottom: analyst → console → tools → graph"
        lede="Each row cites the exact artifact that justifies its status. Click through the console modules to see those artifacts in context."
        className="border-t border-line"
      >
        <div className="space-y-2">
          {ARCHITECTURE.map((l, i) => {
            const tone = TONE[l.status];
            return (
              <div
                key={l.name}
                className={`flex gap-4 border ${tone.border} ${tone.bg} px-4 py-3`}
              >
                <div className="flex w-9 shrink-0 flex-col items-center">
                  <span
                    className="font-mono text-[12px] font-bold"
                    style={{ color: tone.text }}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  {i < ARCHITECTURE.length - 1 && (
                    <span className="mt-1 w-px flex-1 bg-line" />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-[14.5px] font-bold text-fg">{l.name}</h3>
                    <span
                      className="border px-1.5 py-[1px] font-mono text-[9px] font-bold tracking-[0.12em]"
                      style={{ color: tone.text, borderColor: `${tone.text}66` }}
                    >
                      {STATUS_LABEL[l.status]}
                    </span>
                  </div>
                  <p className="mt-1 max-w-[900px] text-[12.5px] leading-[19px] text-fg-2">
                    {l.detail}
                  </p>
                  <div className="mt-1.5 flex items-center gap-2">
                    <span className="text-[9px] tracking-[0.14em] text-dim uppercase">
                      Evidence
                    </span>
                    <span className="font-mono text-[10.5px] text-fg-2">
                      {l.evidence}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      {/* ---------- gaps ---------- */}
      <Section
        eyebrow="DECLARED GAPS"
        title="What this repository does not do"
        lede="These are the pieces of the reference architecture that are designed but not wired end-to-end here. They are listed instead of hidden, so no demo screen implies they ran."
        className="border-t border-line"
      >
        <div className="grid gap-3 lg:grid-cols-3">
          {gaps.length === 0 ? (
            <Card
              title="No layer gap remains"
              right={<Tag tone="ok">ALL LAYERS BACKED</Tag>}
            >
              <p className="text-[12px] leading-[18px] text-fg-2">
                All {ARCHITECTURE.length} reference layers now cite an artifact
                that actually ran, so this list is empty rather than padded.
              </p>
              <p className="mt-2 text-[12px] leading-[18px] text-fg-2">
                One limitation is deliberate and stays visible above as a
                BLOCKED probe: the case-result write-back to the graph is not
                performed, and is documented in docs/GRAPH_WRITE_BLOCKER.md.
              </p>
              <div className="mt-2 font-mono text-[10.5px] text-dim">
                frontend/lib/architecture.ts
              </div>
            </Card>
          ) : (
            gaps.map((l) => (
              <Card
                key={l.name}
                title={l.name}
                right={
                  <Tag tone={l.status === "wip" ? "warn" : "neutral"}>
                    {STATUS_LABEL[l.status]}
                  </Tag>
                }
              >
                <p className="text-[12px] leading-[18px] text-fg-2">
                  {l.detail}
                </p>
                <div className="mt-2 font-mono text-[10.5px] text-dim">
                  {l.evidence}
                </div>
              </Card>
            ))
          )}
        </div>
      </Section>

      {/* ---------- data flow ---------- */}
      <Section
        eyebrow="INVESTIGATION FLOW"
        title="How one case moves through the system"
        className="border-t border-line"
      >
        <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
          {[
            {
              n: "01",
              t: "Triage",
              d: "Case facts read from DATASET/case_pack.csv, pattern hypotheses formed.",
            },
            {
              n: "02",
              t: "Graph investigation",
              d: "10 read-only GSQL queries return entities, paths and neighbours as structured evidence.",
            },
            {
              n: "03",
              t: "Evidence",
              d: "Items classified into 5 categories with support / contradict / context direction.",
            },
            {
              n: "04",
              t: "ML + XAI",
              d: "RandomForest probability with SHAP decomposition; risk_score excluded as leakage.",
            },
            {
              n: "05",
              t: "Policy",
              d: "Candidate actions validated against the approval route: auto, L1 or L2.",
            },
            {
              n: "06",
              t: "Next best action",
              d: "Recommendation, evidence sufficiency and the case record — graph write blocked.",
            },
          ].map((s) => (
            <div key={s.n} className="border border-line bg-ink-900 p-3.5">
              <div className="font-mono text-[11px] tracking-[0.2em] text-accent">
                {s.n}
              </div>
              <div className="mt-1.5 text-[13px] font-bold text-fg">{s.t}</div>
              <p className="mt-1 text-[11.5px] leading-[17px] text-fg-2">{s.d}</p>
            </div>
          ))}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Tag tone="accent">START AT /cases</Tag>
          <Tag tone="neutral">RUN AT /investigation</Tag>
          <Tag tone="neutral">MODEL AT /model</Tag>
        </div>
      </Section>
    </div>
  );
}
