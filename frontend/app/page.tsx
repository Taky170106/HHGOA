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
  Reveal,
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

export default function LandingPage() {
  const { data, error, loading } = useSummary();

  if (error) return <ErrorNote what="/api/summary" message={error} />;
  if (loading || !data) return <Loading what="cases/validation_report.json" />;

  const gsql = data.gsql;
  const mcp = data.mcp as Record<string, number | string>;
  const evidenceTotal = data.cases.reduce((s, c) => s + c.evidence_items, 0);

  return (
    <div className="fade-up pb-16">
      {/* ---------------- hero ---------------- */}
      <section className="relative overflow-hidden border-b border-line hero-grid">
        <Container className="pt-20 pb-16">
          <div className="grid items-start gap-12 lg:grid-cols-[1.08fr_0.92fr]">
            <div>
              <Eyebrow>AGENTIC FRAUD INTELLIGENCE · HHGOA 2026</Eyebrow>

              <h1 className="font-display mt-5 text-[76px] leading-[0.94] font-semibold tracking-[-0.03em]">
                <span className="sheen">GRAVEX</span>
              </h1>

              <p className="font-display mt-3 max-w-[640px] text-[26px] leading-[1.22] font-medium tracking-[-0.01em] text-fg">
                Agentic fraud investigation,{" "}
                <span className="text-accent">grounded in the graph.</span>
              </p>

              <p className="mt-5 max-w-[660px] text-[14.5px] leading-[24px] text-fg-2">
                Twenty benchmark cases triaged against a locked TigerGraph of{" "}
                <span className="font-mono text-fg">8</span> vertex types,{" "}
                <span className="font-mono text-fg">11</span> edge types and{" "}
                <span className="font-mono text-fg">2,505,266</span> loaded
                edges. The language model reasons over evidence — it never
                invents it, never writes to the graph, and every recommendation
                is traceable to a query, an evidence item and a recorded
                decision.
              </p>

              <div className="mt-8 flex flex-wrap gap-2.5">
                <Button href="/dashboard" variant="primary">
                  OPEN THE CONSOLE →
                </Button>
                <Button href="/investigation">▶ RUN INVESTIGATION</Button>
                <Button href="/cases">BROWSE 20 CASES</Button>
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

      {/* ---------------- live proof strip ---------------- */}
      <section className="border-b border-line bg-ink-900">
        <Container className="grid grid-cols-2 gap-0 md:grid-cols-3 xl:grid-cols-6">
          {[
            {
              label: "Cases",
              value: String(data.cases.length),
              sub: `${data.cases_passed} passed · ${data.total_errors} errors`,
              tone: undefined,
            },
            {
              label: "Fraud / SAR",
              value: `${data.counts.fraud} / ${data.sar_filed}`,
              sub: "filed after review",
              tone: "var(--color-bad)",
            },
            {
              label: "Uncertain",
              value: String(data.counts.uncertain),
              sub: "evidence-limited",
              tone: "var(--color-warn)",
            },
            {
              label: "Legitimate",
              value: String(data.counts.legitimate),
              sub: "closed, no SAR",
              tone: "var(--color-ok)",
            },
            {
              label: "ROC-AUC",
              value: data.metrics.test.roc_auc.toFixed(4),
              sub: `accuracy ${data.metrics.test.accuracy.toFixed(4)}`,
              tone: "var(--color-ok)",
            },
            {
              label: "Loaded edges",
              value: "2,505,266",
              sub: "locked Phase 2 baseline",
              tone: undefined,
            },
          ].map((s, i) => (
            <Reveal key={s.label} delay={i * 70}>
              <div className="h-full border-r border-line px-4 py-5 last:border-r-0">
                <div className="text-[9.5px] font-semibold tracking-[0.16em] text-dim uppercase">
                  {s.label}
                </div>
                <div
                  className="mt-1.5 font-mono text-[30px] leading-9 font-bold"
                  style={s.tone ? { color: s.tone } : undefined}
                >
                  {s.value}
                </div>
                <div className="mt-0.5 text-[10.5px] text-dim">{s.sub}</div>
              </div>
            </Reveal>
          ))}
        </Container>
      </section>

      {/* ---------------- how it works: pipeline ---------------- */}
      <Section
        eyebrow="NINE-STAGE AGENT PIPELINE"
        title="One ordered state machine, every case, every time"
        lede="TRIAGE reads the graph, INVESTIGATE queries it, EVIDENCE scores what was found, UNCERTAINTY decides whether that is enough — and only then does POLICY constrain the action the agent may propose."
      >
        <div className="relative mb-6 grid gap-2 md:grid-cols-3 xl:grid-cols-9">
          <div className="absolute inset-x-0 -bottom-[17px] hidden h-px overflow-hidden bg-line md:block">
            <div className="flow-line h-full w-full" />
          </div>
          {PIPELINE.map((s, i) => (
            <Reveal key={s} delay={i * 60}>
              <div className="lift relative h-full border border-line bg-ink-900 px-3 py-3.5">
                <div className="font-mono text-[10px] tracking-[0.18em] text-accent">
                  {String(i + 1).padStart(2, "0")}
                </div>
                <div className="mt-1.5 text-[11px] leading-[15px] font-bold text-fg">
                  {s}
                </div>
                <div className="mt-2 h-px w-6 bg-accent/50" />
              </div>
            </Reveal>
          ))}
        </div>

        <div className="mt-5 flex flex-wrap gap-2.5">
          <Button href="/investigation" variant="primary">
            ▶ RUN IT ON HHG-001
          </Button>
          <Button href="/cases/HHG-001">SEE THE RECORDED RUN</Button>
        </div>
      </Section>

      {/* ---------------- modules ---------------- */}
      <Section
        eyebrow="THE CONSOLE"
        title="Six modules — one job each"
        lede="Start at the case list, open a case, run the agent, then read the model that scored it and the architecture that constrains it. Every screen reads the repository artifacts directly."
        className="border-t border-line"
      >
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {MODULES.map((m, i) => (
            <Reveal key={m.n} delay={(i % 3) * 80}>
              <ModuleCard {...m} />
            </Reveal>
          ))}
        </div>
      </Section>

      {/* ---------------- distribution / benchmark honesty ---------------- */}
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
            So the agent separates suspicion from proof —{" "}
            <span className="font-mono text-fg">uncertain</span> is a
            first-class outcome, not a failure to decide.
          </>
        }
        className="border-t border-line"
      >
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <Card>
            <div className="flex h-8 w-full overflow-hidden border border-line">
              {[
                { k: "FRAUD", v: data.counts.fraud, c: "var(--color-bad)" },
                { k: "UNCERTAIN", v: data.counts.uncertain, c: "var(--color-warn)" },
                { k: "LEGITIMATE", v: data.counts.legitimate, c: "var(--color-ok)" },
              ].map((s) => (
                <div
                  key={s.k}
                  className="flex items-center justify-center text-[10px] font-bold text-ink-950"
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

            <div className="mt-3.5 grid gap-3 sm:grid-cols-3">
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
                    <span
                      className="font-mono text-[15px] font-bold"
                      style={{ color: s.c }}
                    >
                      {s.v}
                    </span>
                  </div>
                  <div className="mt-1">
                    <Bar value={s.v} max={data.cases.length} tone={s.c} />
                  </div>
                </div>
              ))}
            </div>

            <p className="mt-3.5 border-t border-line pt-2.5 text-[11px] leading-[17px] text-dim">
              Above 0.7 the benchmark warns most flagged transactions turn out to
              be legitimate, so the score is an input to review — not a verdict.{" "}
              <span className="font-mono">risk_score</span> is excluded from the
              model as label leakage and shown as context only.
            </p>
          </Card>

          <Card
            title="GRAPH WRITE BLOCKER"
            right={<Tag tone="bad">BLOCKED</Tag>}
          >
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

      {/* ---------------- evidence + graph facts ---------------- */}
      <Section
        eyebrow="EVIDENCE FIRST"
        title={`${evidenceTotal} evidence items across 20 case files`}
        lede="Every recommendation carries supporting, contradicting or context evidence with a source, a direction and a graph provenance — and when evidence runs out the agent says so instead of guessing."
        className="border-t border-line"
      >
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <div className="grid gap-3 sm:grid-cols-2">
            {GRAPH_FACTS.map((f, i) => (
              <Reveal key={f.label} delay={(i % 2) * 80}>
                <StatTile
                  label={f.label}
                  value={f.value}
                  sub={f.source}
                  source={f.source}
                />
              </Reveal>
            ))}
          </div>

          <Card title="LIVE PROOF — REAL COMMAND OUTPUT">
            <div className="space-y-3">
              <Terminal
                title={VALIDATION_RUN.cmd}
                lines={VALIDATION_RUN.out}
              />
              <Terminal title={DEMO_RUN.cmd} lines={DEMO_RUN.out} />
            </div>
          </Card>
        </div>
      </Section>

      {/* ---------------- final CTA ---------------- */}
      <section className="border-t border-line hero-grid">
        <Container className="py-14">
          <div className="flex flex-wrap items-end justify-between gap-8">
            <div>
              <Eyebrow>OPEN GRAVEX</Eyebrow>
              <h2 className="font-display mt-3 max-w-[720px] text-[34px] leading-[1.1] font-semibold tracking-[-0.02em] text-fg">
                Start with the case list. End with a{" "}
                <span className="text-accent">next best action</span> you can
                audit line by line.
              </h2>
              <div className="mt-6 flex flex-wrap gap-2.5">
                <Button href="/dashboard" variant="primary">
                  OPEN THE CONSOLE →
                </Button>
                <Button href="/architecture">SYSTEM ARCHITECTURE</Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-x-8 gap-y-2.5 font-mono text-[11px] text-dim">
              <span>cases</span>
              <span className="text-fg">20/20 validated</span>
              <span>graph write</span>
              <span className="text-bad">blocked by design</span>
              <span>LLM tokens</span>
              <span className="text-fg">0 (keyless run)</span>
              <span>model</span>
              <span className="text-ok">
                ROC-AUC {data.metrics.test.roc_auc.toFixed(4)}
              </span>
            </div>
          </div>
        </Container>
      </section>
    </div>
  );
}
