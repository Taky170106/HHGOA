"use client";

import { Chip, Empty, Panel } from "./ui";
import type {
  CaseFile,
  E2eRun,
  ShapLocalEntry,
} from "@/lib/types";

interface StageDef {
  key: string;
  ir?: string;
  e2e?: string;
}

/** The nine stages of the investigation pipeline, in execution order. */
const STAGES: StageDef[] = [
  { key: "TRIGGER", ir: "TRIGGER", e2e: "CASE" },
  { key: "TRIAGE", ir: "CASE" },
  { key: "GRAPH INVESTIGATION", ir: "GRAPH_INVESTIGATION", e2e: "GRAPH_EVIDENCE" },
  { key: "EVIDENCE", ir: "EVIDENCE_COLLECTION" },
  { key: "ML ANALYSIS", e2e: "RISK_SCORE" },
  { key: "XAI", e2e: "XAI" },
  { key: "UNCERTAINTY", ir: "DECISION" },
  { key: "POLICY", ir: "APPROVAL_ROUTE" },
  { key: "NEXT BEST ACTION", ir: "NEXT_BEST_ACTION" },
];

export function AgentPipeline({
  cf,
  shapLocal,
  e2e,
  stage,
  replaying,
}: {
  cf: CaseFile;
  shapLocal: ShapLocalEntry | null;
  e2e: E2eRun | null;
  stage: number;
  replaying: boolean;
}) {
  const ir = new Map(cf.investigation_record.map((s) => [s.name, s.detail]));
  const es = new Map((e2e?.steps ?? []).map((s) => [s.name, s.detail]));

  const modelEvidence = cf.case.evidence.find(
    (e) => e.evidence_class === "model_analytical",
  );

  const detailFor = (s: StageDef): string => {
    if (s.e2e && es.has(s.e2e)) return es.get(s.e2e)!;
    if (s.ir && ir.has(s.ir)) return ir.get(s.ir)!;
    if (s.key === "ML ANALYSIS" && modelEvidence) return modelEvidence.claim;
    if (s.key === "XAI" && shapLocal) {
      const top = shapLocal.top_contributing_features
        .slice(0, 3)
        .map((f) => `${f.feature} (${f.shap_value >= 0 ? "+" : ""}${f.shap_value})`)
        .join(", ");
      return `SHAP contributions for txn ${shapLocal.txn_id}: ${top}.`;
    }
    return "recorded in the case file";
  };

  return (
    <aside className="flex w-[344px] shrink-0 flex-col gap-1 overflow-y-auto">
      <Panel
        title="AGENT EXECUTION"
        right={
          <Chip tone={replaying ? "accent" : "ok"}>
            {replaying ? "REPLAY" : "COMPLETE"}
          </Chip>
        }
        className="min-h-0 shrink-0"
        bodyClass="p-0"
      >
        <ol className="px-2 py-1">
          {STAGES.map((s, i) => {
            const done = i < stage;
            return (
              <li
                key={s.key}
                className={`flex gap-2.5 pb-1 last:pb-0 ${done ? "stage-in" : "opacity-40"}`}
              >
                <div className="flex w-4 shrink-0 flex-col items-center">
                  <span
                    className={`mt-[2px] flex h-4 w-4 items-center justify-center rounded-full border text-[9px] ${
                      done
                        ? "border-ok/70 bg-ok/20 text-ok"
                        : "border-line text-dim"
                    }`}
                  >
                    {done ? "✓" : i + 1}
                  </span>
                  {i < STAGES.length - 1 && (
                    <span
                      className={`mt-0.5 w-px flex-1 ${done ? "bg-ok/40" : "bg-line"}`}
                    />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[10.5px] font-bold tracking-[0.09em] text-fg">
                    {s.key}
                  </div>
                  <div
                    className={`line-clamp-2 text-[10px] leading-[13px] ${done ? "text-fg-2" : "text-dim"}`}
                  >
                    {truncate(done ? detailFor(s) : "awaiting", 78)}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>

        <div className="flex shrink-0 items-center gap-2.5 border-t border-line bg-ink-850 px-2 py-[5px] text-[9.5px]">
          <span className="text-dim">
            RECORDED{" "}
            <b className="font-mono font-bold text-accent">
              {cf.latency_s.toFixed(2)}s
            </b>
          </span>
          <span className="text-dim">
            {e2e ? "DEMO WALL CLOCK" : "LIVE DEMO"}{" "}
            <b className="font-mono font-bold text-accent">
              {e2e ? `${e2e.wall_clock_s.toFixed(2)}s` : "—"}
            </b>
          </span>
          <span className="text-dim">
            TOOL CALLS{" "}
            <b className="font-mono font-bold text-accent">{cf.tool_calls}</b>
          </span>
          <span className="ml-auto font-mono text-dim">{cf.tokens} tokens</span>
        </div>
      </Panel>

      <Sufficiency cf={cf} />
      <Counterfactual cf={cf} />
    </aside>
  );
}

function Sufficiency({ cf }: { cf: CaseFile }) {
  const requests = cf.evidence_requests ?? [];
  const received =
    cf.post_additional_evidence_state?.additional_evidence_received === true;
  const request = requests[0];

  const sufficient = requests.length === 0 || received;

  const basis =
    requests.length === 0
      ? `No additional evidence was requested — ${cf.stop_reason}`
      : received
        ? `Recorded response: "${request?.assumed_response ?? "received"}"`
        : `Requested ${request?.type ?? "evidence"} at step ${request?.asked_after_step ?? "?"} — no response recorded`;

  return (
    <Panel
      title="EVIDENCE SUFFICIENCY"
      right={
        <Chip tone={sufficient ? "ok" : "bad"}>
          ● {sufficient ? "SUFFICIENT" : "INSUFFICIENT"}
        </Chip>
      }
      className="min-h-0 shrink-0"
      bodyClass="p-2"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10.5px]">
        <span className="text-fg-2">
          evidence on file{" "}
          <b className="font-mono font-bold text-fg">
            {cf.case.evidence.length}
          </b>
        </span>
        <span className="text-fg-2">
          additional evidence{" "}
          <b
            className={`font-mono font-bold ${sufficient ? "text-ok" : "text-bad"}`}
          >
            {requests.length === 0
              ? "not required"
              : received
                ? "received"
                : "pending"}
          </b>
        </span>
      </div>

      <p className="mt-1 line-clamp-1 border-l-2 border-line pl-2 text-[9.5px] leading-[13px] text-dim">
        {truncate(basis, 165)}
      </p>

      {!sufficient && (
        <div className="mt-2 space-y-1">
          {["EVIDENCE VALUE", "CONTROLLED ACQUISITION", "RE-ANALYSIS"].map(
            (s, i) => (
              <div
                key={s}
                className="flex items-center gap-2 border border-warn/40 bg-warn/10 px-2 py-1 text-[10px] font-semibold text-warn"
              >
                <span className="font-mono">{i + 1}</span>
                {s}
                {i < 2 && <span className="ml-auto">↓</span>}
              </div>
            ),
          )}
        </div>
      )}
    </Panel>
  );
}

function Counterfactual({ cf }: { cf: CaseFile }) {
  const fin = cf.next_best_actions.final;
  const request = cf.evidence_requests[0];
  const exposure = cf.case.exposure_usd;

  const rows: [string, string][] = [
    [
      "Action",
      fin.length
        ? `${fin.map((a) => a.action).slice(0, 3).join(", ")}${fin.length > 3 ? ` +${fin.length - 3}` : ""}`
        : "—",
    ],
    [
      "Impact",
      `${cf.case.status} · exposure $${exposure.toFixed(2)} · ${
        cf.sar.file ? "SAR filed" : "no SAR"
      }`,
    ],
    [
      "Residual Risk",
      `p = ${cf.case.fraud_probability.toFixed(4)} · pattern ${cf.case.pattern}`,
    ],
    [
      "Required Evidence",
      request
        ? `${request.type} — "${truncate(request.assumed_response, 54)}"`
        : "none outstanding — Section 6 stop",
    ],
  ];

  return (
    <Panel
      title="COUNTERFACTUAL ANALYSIS"
      titleClass="tracking-[0.05em]"
      right={
        <span className="border border-warn/60 bg-warn/10 px-1 py-[1px] text-[8px] font-bold tracking-[0.03em] text-warn">
          ARCHITECTURAL WORKFLOW
        </span>
      }
      className="min-h-0 shrink-0"
      bodyClass="p-2"
    >
      <table className="w-full table-fixed text-[10px]">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} className="border-b border-line/60 last:border-0">
              <td className="w-[76px] py-[3px] pr-2 align-top text-[9px] tracking-[0.06em] text-dim uppercase">
                {k}
              </td>
              <td className="py-[3px] font-mono leading-[13.5px] text-fg-2">
                <span title={v} className="block truncate">
                  {v}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p
        title="No counterfactual/ module exists in this repository, so no simulation was run — the rows above are the recorded case outcome, not a computed alternative."
        className="mt-1 truncate text-[9px] leading-[12.5px] text-dim"
      >
        No <span className="font-mono">counterfactual/</span> module exists here —
        rows are the recorded outcome, not a simulation.
      </p>
    </Panel>
  );
}

export function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

export function NoData({ text }: { text: string }) {
  return <Empty text={text} />;
}
