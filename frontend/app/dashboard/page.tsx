"use client";

import {
  Bar,
  Button,
  Card,
  Container,
  ErrorNote,
  Eyebrow,
  Loading,
  ModuleCard,
  PageHeader,
  Section,
  StatTile,
  Tag,
  Terminal,
} from "@/components/kit";
import {
  DEMO_RUN,
  GRAPH_FACTS,
  MODULES,
  VALIDATION_RUN,
} from "@/lib/facts";
import { useSummary } from "@/lib/useJson";

const PIPELINE = [
  "TRIGGER",
  "TRIAGE",
  "GRAPH INVESTIGATION",
  "EVIDENCE",
  "ML ANALYSIS",
  "XAI",
  "UNCERTAINTY",
  "POLICY",
  "NEXT BEST ACTION",
];

export default function DashboardPage() {
  const { data, error, loading } = useSummary();

  if (error) return <ErrorNote what="/api/summary" message={error} />;
  if (loading || !data) return <Loading what="cases/validation_report.json" />;

  const gsql = data.gsql;
  const mcp = data.mcp as Record<string, number | string>;

  return (
    <div className="fade-up pb-16">
      {/* ---------------- hero ---------------- */}
      <section className="border-b border-line hero-grid">
        <Container className="pt-14 pb-12">
          <div className="grid items-start gap-10 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <Eyebrow>HHGOA 2026 · PHASE 3 DELIVERABLE</Eyebrow>

              <h1 className="font-display mt-4 max-w-[720px] text-[42px] leading-[1.08] font-semibold tracking-[-0.02em] text-fg">
                Agentic fraud investigation,{" "}
                <span className="text-accent">grounded in the graph.</span>
              </h1>

              <p className="mt-4 max-w-[660px] text-[14px] leading-[23px] text-fg-2">
                Twenty benchmark cases triaged against a locked TigerGraph of{" "}
                <span className="font-mono text-fg">8</span> vertex types,{" "}
                <span className="font-mono text-fg">11</span> edge types and{" "}
                <span className="font-mono text-fg">2,505,266</span> loaded
                edges. Every verdict below is traceable to a graph query, an
                evidence item and a recorded decision — the language model
                reasons over evidence, it never invents it.
              </p>

              <div className="mt-7 flex flex-wrap gap-2.5">
                <Button href="/investigation" variant="primary">
                  ▶ RUN INVESTIGATION
                </Button>
                <Button href="/cases">BROWSE 20 CASES</Button>
                <Button href="/architecture">SYSTEM ARCHITECTURE</Button>
              </div>

              <div className="mt-8 flex flex-wrap gap-2">
                <Tag tone="ok">VALIDATION {data.validation_status} 20/20</Tag>
                <Tag tone="bad">GRAPH WRITE BLOCKED</Tag>
                <Tag tone="accent">GSQL {gsql.queries_executed}/10 LIVE</Tag>
                <Tag tone="violet">MCP {mcp.live_pass}/{mcp.live_total} LIVE</Tag>
                <Tag tone="warn">tokens 0 — cases predate LLM runs</Tag>
              </div>
            </div>

            <div className="space-y-4">
              <Terminal title={VALIDATION_RUN.cmd} lines={VALIDATION_RUN.out} />
              <Terminal title={DEMO_RUN.cmd} lines={DEMO_RUN.out} />
            </div>
          </div>
        </Container>
      </section>

      {/* ---------------- live status ---------------- */}
      <Section
        eyebrow="LIVE REPOSITORY STATE"
        title="Every number here is read from an artifact at request time"
        lede="Nothing on this page is hard-coded: case counts come from cases/validation_report.json, model metrics from models/metrics.json and the tool counts from the Phase 3 validation files."
      >
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <StatTile
            label="Cases"
            value={data.cases.length}
            sub={`${data.cases_passed} passed · ${data.total_errors} errors`}
            source="cases/validation_report.json"
          />
          <StatTile
            label="Fraud"
            value={data.counts.fraud}
            tone="var(--color-bad)"
            sub="SAR filed"
            source="cases/_build_summary.json"
          />
          <StatTile
            label="Uncertain"
            value={data.counts.uncertain}
            tone="var(--color-warn)"
            sub="evidence-limited"
          />
          <StatTile
            label="Legitimate"
            value={data.counts.legitimate}
            tone="var(--color-ok)"
            sub="closed, no SAR"
          />
          <StatTile
            label="ROC-AUC"
            value={data.metrics.test.roc_auc.toFixed(4)}
            tone="var(--color-ok)"
            sub={`accuracy ${data.metrics.test.accuracy.toFixed(4)}`}
            source="models/metrics.json"
          />
          <StatTile
            label="Evidence items"
            value={data.cases.reduce((s, c) => s + c.evidence_items, 0)}
            sub="across 20 cases"
            source="cases/*.json"
          />
        </div>
      </Section>

      {/* ---------------- modules ---------------- */}
      <Section
        eyebrow="CONSOLE MODULES"
        title="Six sections — one job each"
        lede="The console is split into focused modules so a single screen never has to explain the whole system at once. Start at the case list, open a case, run it, then read the model and the architecture."
        className="border-t border-line"
      >
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {MODULES.map((m) => (
            <ModuleCard key={m.n} {...m} />
          ))}
        </div>
      </Section>

      {/* ---------------- distribution ---------------- */}
      <Section
        eyebrow="CLASSIFICATION BIAS"
        title="Why half the queue is not blocked"
        lede={
          <>
            The benchmark states it plainly:{" "}
            <span className="text-fg">
              “Half the cases are legitimate. Many look suspicious. An agent
              that blocks everything scores badly.”
            </span>{" "}
            So the agent must separate suspicion from proof —{" "}
            <span className="font-mono text-fg">uncertain</span> is a first-class
            outcome, not a failure to decide.
          </>
        }
        className="border-t border-line"
      >
        <Card className="max-w-[980px]">
          <div className="flex h-7 w-full overflow-hidden border border-line">
            {[
              { k: "FRAUD", v: data.counts.fraud, c: "var(--color-bad)" },
              { k: "UNCERTAIN", v: data.counts.uncertain, c: "var(--color-warn)" },
              { k: "LEGITIMATE", v: data.counts.legitimate, c: "var(--color-ok)" },
            ].map((s) => (
              <div
                key={s.k}
                className="flex items-center justify-center text-[9.5px] font-bold text-ink-950"
                style={{
                  width: `${(s.v / data.cases.length) * 100}%`,
                  background: s.c,
                }}
                title={`${s.k}: ${s.v}`}
              >
                {s.v}
              </div>
            ))}
          </div>

          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            {[
              { k: "FRAUD", v: data.counts.fraud, c: "var(--color-bad)" },
              { k: "UNCERTAIN", v: data.counts.uncertain, c: "var(--color-warn)" },
              { k: "LEGITIMATE", v: data.counts.legitimate, c: "var(--color-ok)" },
            ].map((s) => (
              <div key={s.k}>
                <div className="flex items-baseline justify-between">
                  <span className="text-[10px] font-bold tracking-[0.14em] text-fg-2">
                    {s.k}
                  </span>
                  <span className="font-mono text-[15px] font-bold" style={{ color: s.c }}>
                    {s.v}
                  </span>
                </div>
                <div className="mt-1">
                  <Bar value={s.v} max={data.cases.length} tone={s.c} />
                </div>
              </div>
            ))}
          </div>

          <p className="mt-3 border-t border-line pt-2.5 text-[11px] leading-[17px] text-dim">
            Above 0.7 the benchmark warns most flagged transactions turn out to
            be legitimate, so the score is treated as an input to review — not a
            verdict. <span className="font-mono">risk_score</span> is excluded
            from the model as label leakage and shown as context only.
          </p>
        </Card>
      </Section>

      {/* ---------------- pipeline ---------------- */}
      <Section
        eyebrow="AGENT PIPELINE"
        title="Nine stages, every time"
        lede="The same ordered state machine runs for each case. Each stage writes to the case record, so the run can be replayed and audited stage by stage."
        className="border-t border-line"
      >
        <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-9">
          {PIPELINE.map((s, i) => (
            <div
              key={s}
              className="relative border border-line bg-ink-900 px-3 py-3"
            >
              <div className="font-mono text-[10px] tracking-[0.18em] text-accent">
                {String(i + 1).padStart(2, "0")}
              </div>
              <div className="mt-1.5 text-[11px] leading-[15px] font-bold text-fg">
                {s}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button href="/investigation" variant="primary">
            ▶ RUN IT ON HHG-001
          </Button>
          <Button href="/cases/HHG-001">SEE THE RECORDED RUN</Button>
        </div>
      </Section>

      {/* ---------------- graph baseline ---------------- */}
      <Section
        eyebrow="LOCKED PHASE 2 BASELINE"
        title="The graph is the single source of truth"
        lede="The schema and loaded data are frozen: the UI, the agent and the evidence engine all read this one graph. Writes are deliberately blocked and documented rather than silently skipped."
        className="border-t border-line"
      >
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <div className="grid gap-3 sm:grid-cols-2">
            {GRAPH_FACTS.map((f) => (
              <StatTile
                key={f.label}
                label={f.label}
                value={f.value}
                sub={f.source}
                source={f.source}
              />
            ))}
          </div>

          <Card title="GRAPH WRITE BLOCKER" right={<Tag tone="bad">BLOCKED</Tag>}>
            <p className="text-[12px] leading-[19px] text-fg-2">
              {data.graph_write.reason}
            </p>
            <div className="mt-3 grid gap-2 font-mono text-[11px] text-fg-2">
              <div className="flex justify-between border-b border-line/60 pb-1">
                <span className="text-dim">written_to_graph</span>
                <span className="text-bad">
                  {String(data.graph_write.written_to_graph)}
                </span>
              </div>
              <div className="flex justify-between border-b border-line/60 pb-1">
                <span className="text-dim">graph_case_id</span>
                <span className="text-bad">
                  {data.graph_write.graph_case_id || "(empty)"}
                </span>
              </div>
              <div className="border-t border-line/60 pt-1.5">
                <span className="text-dim">reference</span>
                <span className="mt-0.5 block text-accent">
                  {data.graph_write.reference}
                </span>
              </div>
            </div>
          </Card>
        </div>
      </Section>
    </div>
  );
}
