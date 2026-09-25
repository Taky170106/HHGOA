"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import GraphCanvas from "@/components/GraphCanvas";
import { CaseSidebar, TopBar } from "@/components/Chrome";
import { AgentPipeline } from "@/components/AgentPipeline";
import { ActionPanel, EvidencePanel, MlPanel, XaiPanel } from "@/components/Panels";
import {
  ArchitectureModal,
  CaseDrawer,
  NodeDetails,
} from "@/components/Overlays";
import { Empty, Panel } from "@/components/ui";
import { buildGraph } from "@/lib/graph";
import type { CasePayload, CaseSummaryRow, SummaryPayload } from "@/lib/types";

const REPLAY_MS = 6800; // total replay duration, within the 5–8s target
const STAGE_COUNT = 9;

export default function Page() {
  const [summary, setSummary] = useState<SummaryPayload | null>(null);
  const [activeId, setActiveId] = useState("HHG-001");
  const [payload, setPayload] = useState<CasePayload | null>(null);
  const [tg, setTg] = useState<{
    ok: boolean;
    http_status: number;
    latency_ms: number;
    endpoint?: string;
  } | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [archOpen, setArchOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState(0);
  const [stage, setStage] = useState(STAGE_COUNT);
  const [replaying, setReplaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  /* ---------- data ---------- */
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [s, t] = await Promise.all([
          fetch("/api/summary").then((r) => r.json()),
          fetch("/api/tigergraph").then((r) => r.json()),
        ]);
        if (!alive) return;
        setSummary(s as SummaryPayload);
        setTg(t);
      } catch {
        if (alive) setError("Could not load /api/summary");
      }
    };
    void load();
    const probe = setInterval(() => {
      void fetch("/api/tigergraph")
        .then((r) => r.json())
        .then((t) => alive && setTg(t))
        .catch(() => undefined);
    }, 30000);
    return () => {
      alive = false;
      clearInterval(probe);
    };
  }, []);

  useEffect(() => {
    let alive = true;
    setPayload(null);
    setSelectedNode(null);
    setStage(STAGE_COUNT);
    fetch(`/api/case/${activeId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("bad case"))))
      .then((p: CasePayload) => alive && setPayload(p))
      .catch(() => alive && setError(`Could not load ${activeId}`));
    return () => {
      alive = false;
    };
  }, [activeId]);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  /* ---------- replay ---------- */
  const runReplay = useCallback(() => {
    if (replaying) return;
    if (timer.current) clearTimeout(timer.current);
    setReplaying(true);
    setStage(0);
    const step = REPLAY_MS / STAGE_COUNT;
    let i = 0;
    const tick = () => {
      i += 1;
      setStage(i);
      if (i >= STAGE_COUNT) {
        setReplaying(false);
        return;
      }
      timer.current = setTimeout(tick, step);
    };
    timer.current = setTimeout(tick, step);
  }, [replaying]);

  /* ---------- render ---------- */
  const cf = payload?.caseFile ?? null;
  const graph = cf ? buildGraph(cf) : null;
  const row = summary?.cases.find((c) => c.case_id === activeId);
  const totalRows: CaseSummaryRow[] = summary?.cases ?? [];

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="border border-bad/50 bg-bad/10 px-6 py-4 text-[13px] text-bad">
          {error}
        </div>
      </div>
    );
  }

  if (!summary || !cf || !graph || !payload) {
    return (
      <div className="flex h-full flex-col">
        <div className="h-12 border-b border-line bg-ink-900" />
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center">
            <div className="pulse-dot mx-auto mb-3 h-3 w-3 rounded-full bg-accent" />
            <div className="label">LOADING REPOSITORY ARTIFACTS</div>
            <div className="mt-1 font-mono text-[11px] text-dim">
              cases/validation_report.json · cases/{activeId}.json
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <TopBar
        activeCase={activeId}
        caseStatus={cf.case.status}
        tg={tg}
        onRun={runReplay}
        replaying={replaying}
        replayStage={stage}
        onOpenArch={() => setArchOpen(true)}
        onOpenCase={() => setDrawerOpen(true)}
      />

      <div className="flex min-h-0 flex-1">
        <CaseSidebar
          rows={totalRows}
          active={activeId}
          onSelect={setActiveId}
          counts={summary.counts}
          sar={summary.sar_filed}
        />

        {/* centre — graph investigation */}
        <main className="relative flex min-w-0 flex-1 flex-col">
          <div className="flex h-7 shrink-0 items-center gap-3 border-b border-line bg-ink-850 px-3">
            <span className="label">GRAPH INVESTIGATION</span>
            <span className="font-mono text-[10px] text-fg-2">
              {cf.case.pattern}
            </span>
            <span className="text-[10px] text-dim">
              {cf.graph_evidence.single_source_of_truth}
            </span>
            <span className="ml-auto font-mono text-[10px] text-dim">
              {graph.edges.length} edges · source graph_evidence
            </span>
          </div>

          <div className="relative min-h-0 flex-1">
            <GraphCanvas
              nodes={graph.nodes}
              edges={graph.edges}
              selected={selectedNode}
              onSelect={setSelectedNode}
            />
            {selectedNode && (
              <NodeDetails
                cf={cf}
                nodeId={selectedNode}
                onClose={() => setSelectedNode(null)}
              />
            )}
            {replaying && (
              <div className="absolute bottom-2 left-1/2 -translate-x-1/2 border border-accent/60 bg-ink-900/95 px-3 py-1.5 font-mono text-[10.5px] text-accent">
                DEMO REPLAY · stage {stage + 1}/{STAGE_COUNT} · playback of the
                validated {activeId} record (no backend execution)
              </div>
            )}
            {!replaying && (
              <div className="absolute top-2 right-2 border border-line bg-ink-900/90 px-2 py-1 font-mono text-[9.5px] text-dim">
                DEMO REPLAY · ▶ RUN INVESTIGATION
              </div>
            )}
          </div>
        </main>

        <AgentPipeline
          cf={cf}
          shapLocal={payload.shapLocal}
          e2e={payload.e2e}
          stage={stage}
          replaying={replaying}
        />
      </div>

      {/* bottom analytics */}
      <div className="grid h-[310px] shrink-0 grid-cols-4 gap-2 border-t border-line bg-ink-950 p-2">
        <EvidencePanel cf={cf} />
        <MlPanel
          cf={cf}
          shapLocal={payload.shapLocal}
          e2e={payload.e2e}
          metrics={summary.metrics}
        />
        <XaiPanel
          shapLocal={payload.shapLocal}
          shapGlobal={payload.shapGlobal}
        />
        <ActionPanel cf={cf} />
      </div>

      {/* footer status strip */}
      <footer className="flex h-6 shrink-0 items-center gap-4 border-t border-line bg-ink-900 px-3 font-mono text-[9.5px] text-dim">
        <span>
          VALIDATION <span className="text-ok">{summary.validation_status}</span>{" "}
          {summary.cases_passed}/{summary.cases.length}
        </span>
        <span>
          GRAPH WRITE{" "}
          <span className="text-bad">{summary.graph_write.status}</span>
        </span>
        <span>
          SAR <span className="text-bad">{summary.sar_filed}</span>/20
        </span>
        <span>
          TOOL CALLS live {summary.tool_calls.live} · retrieval{" "}
          {summary.tool_calls.retrieval}
        </span>
        <span className="ml-auto">
          {row ? `${row.case_id} · ${row.verdict} · p=${row.fraud_probability.toFixed(4)}` : ""}
        </span>
      </footer>

      <CaseDrawer
        cf={cf}
        shapLocal={payload.shapLocal}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        tab={drawerTab}
        setTab={setDrawerTab}
      />
      <ArchitectureModal
        open={archOpen}
        onClose={() => setArchOpen(false)}
        tg={tg}
      />
    </div>
  );
}
