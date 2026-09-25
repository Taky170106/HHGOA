"use client";

import { Chip, Empty } from "./ui";
import { truncate } from "./AgentPipeline";
import { actionLabel, verdictColor } from "@/lib/classify";
import { ARCHITECTURE, STATUS_LABEL, type LayerStatus } from "@/lib/architecture";
import type { CaseFile, ShapLocalEntry } from "@/lib/types";

const TONE: Record<LayerStatus, string> = {
  live: "ok",
  wip: "warn",
  arch: "neutral",
};

/* ------------------------------------------------------------------ */
/* Node detail card over the graph                                     */
/* ------------------------------------------------------------------ */

export function NodeDetails({
  cf,
  nodeId,
  onClose,
}: {
  cf: CaseFile;
  nodeId: string;
  onClose: () => void;
}) {
  const ge = cf.graph_evidence;
  const facts = (ge.graph_facts ?? []).filter((f) => f.includes(nodeId));
  const interp = (ge.investigation_interpretation ?? []).filter((f) =>
    f.includes(nodeId),
  );
  const ev = cf.case.evidence.filter((e) => e.entity_ids?.includes(nodeId));
  const type =
    Object.entries(ge.entities ?? {}).find(
      ([k, ids]) => k !== "connected_card_ids" && ids?.includes(nodeId),
    )?.[0] ??
    ge.edges.find((e) => e.from === nodeId || e.to === nodeId)?.from_type ??
    "Vertex";

  return (
    <div className="absolute top-9 right-2 z-10 w-[340px] border border-line bg-ink-900 shadow-2xl">
      <header className="flex items-center gap-2 border-b border-line bg-ink-850 px-2.5 py-1.5">
        <span className="font-mono text-[12px] font-bold text-accent">
          {nodeId}
        </span>
        <Chip>{type}</Chip>
        <button
          type="button"
          onClick={onClose}
          className="ml-auto h-5 w-5 border border-line text-[11px] text-fg-2 hover:bg-ink-700"
        >
          ✕
        </button>
      </header>

      <div className="max-h-[380px] overflow-auto p-2.5">
        <Section title="GRAPH FACTS">
          {facts.length ? (
            facts.map((f, i) => (
              <p key={i} className="mb-1 text-[10px] leading-[15px] text-fg-2">
                {f}
              </p>
            ))
          ) : (
            <Empty text="No stored graph fact names this vertex." />
          )}
        </Section>

        <Section title="INVESTIGATION INTERPRETATION">
          {interp.length ? (
            interp.map((f, i) => (
              <p key={i} className="mb-1 text-[10px] leading-[15px] text-fg-2">
                {f}
              </p>
            ))
          ) : (
            <p className="text-[10px] text-dim">
              This vertex appears only as a graph fact above.
            </p>
          )}
        </Section>

        <Section title={`EVIDENCE (${ev.length})`}>
          {ev.length ? (
            ev.map((e) => (
              <div
                key={e.evidence_id}
                className="mb-1 border border-line bg-ink-850 px-1.5 py-1"
              >
                <span className="font-mono text-[9.5px] font-bold text-accent">
                  {e.evidence_id}
                </span>{" "}
                <span className="text-[9px] text-dim">{e.source}</span>
                <p className="text-[10px] leading-[15px] text-fg-2">
                  {e.claim}
                </p>
              </div>
            ))
          ) : (
            <p className="text-[10px] text-dim">
              No evidence item references this vertex.
            </p>
          )}
        </Section>

        <Section title="QUERIES TOUCHING THIS CASE">
          <div className="space-y-0.5">
            {ge.queries.map((q) => (
              <div
                key={q.name}
                className="flex items-center gap-2 font-mono text-[9.5px]"
              >
                <span className="text-ok">HTTP {q.http_status}</span>
                <span className="text-fg-2">{q.name}</span>
                <span className="ml-auto text-dim">{q.latency_ms}ms</span>
              </div>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-2 last:mb-0">
      <div className="label mb-1">{title}</div>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Case record drawer                                                  */
/* ------------------------------------------------------------------ */

const TABS = [
  "Case",
  "Evidence",
  "Findings",
  "Decision",
  "SAR",
  "Next Best Action",
  "Approval",
  "Audit",
] as const;

export function CaseDrawer({
  cf,
  shapLocal,
  open,
  onClose,
  tab,
  setTab,
  variant = "modal",
}: {
  cf: CaseFile;
  shapLocal: ShapLocalEntry | null;
  open?: boolean;
  onClose?: () => void;
  tab: number;
  setTab: (n: number) => void;
  variant?: "modal" | "inline";
}) {
  const inline = variant === "inline";
  if (!inline && !open) return null;

  const panel = (
    <div
      className={
        inline
          ? "flex min-h-0 flex-1 flex-col border border-line bg-ink-900"
          : "mx-auto mt-8 flex h-[calc(100vh-90px)] w-[1440px] max-w-[96vw] flex-col border border-line bg-ink-900 shadow-2xl"
      }
    >
        <header className="flex items-center gap-3 border-b border-line bg-ink-850 px-4 py-2.5">
          <span className="text-[12px] font-bold tracking-[0.16em] text-fg">
            CASE RECORD
          </span>
          <span className="font-mono text-[15px] font-bold text-accent">
            {cf.case_id}
          </span>
          <Chip tone={cf.case.verdict === "fraud" ? "bad" : cf.case.verdict === "legitimate" ? "ok" : "warn"}>
            {cf.case.verdict.toUpperCase()}
          </Chip>
          <Chip>{cf.case.status}</Chip>
          <span className="ml-auto text-[10px] text-dim">
            cases/{cf.case_id}.json
          </span>
          {inline ? null : (
            <button
              type="button"
              onClick={() => onClose?.()}
              className="h-7 border border-line px-2.5 text-[11px] text-fg-2 hover:bg-ink-700"
            >
              CLOSE ✕
            </button>
          )}
        </header>

        <nav className="flex gap-1 border-b border-line bg-ink-850 px-3 py-1.5">
          {TABS.map((t, i) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(i)}
              className={`px-2.5 py-1 text-[10.5px] tracking-wide ${
                tab === i
                  ? "border border-accent/60 bg-accent/15 font-semibold text-accent"
                  : "border border-transparent text-fg-2 hover:text-fg"
              }`}
            >
              {t}
            </button>
          ))}
        </nav>

        <div className="min-h-0 flex-1 overflow-auto p-4">
          {tab === 0 && <TabCase cf={cf} />}
          {tab === 1 && <TabEvidence cf={cf} />}
          {tab === 2 && <TabFindings cf={cf} />}
          {tab === 3 && <TabDecision cf={cf} shapLocal={shapLocal} />}
          {tab === 4 && <TabSar cf={cf} />}
          {tab === 5 && <TabActions cf={cf} />}
          {tab === 6 && <TabApproval cf={cf} />}
          {tab === 7 && <TabAudit cf={cf} />}
        </div>
      </div>
  );

  if (inline) return panel;

  return (
    <div className="fixed inset-0 z-40 flex flex-col bg-ink-950/80">{panel}</div>
  );
}

function Field({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex gap-3 border-b border-line/60 py-1.5 last:border-0">
      <span className="w-[190px] shrink-0 text-[10px] tracking-[0.09em] text-dim uppercase">
        {k}
      </span>
      <span className="min-w-0 flex-1 font-mono text-[11.5px] leading-[17px] text-fg-2">
        {v}
      </span>
    </div>
  );
}

function TabCase({ cf }: { cf: CaseFile }) {
  const c = cf.case;
  return (
    <div className="grid grid-cols-2 gap-x-8">
      <div>
        <Field k="case_id" v={cf.case_id} />
        <Field k="status" v={c.status} />
        <Field
          k="verdict"
          v={<span style={{ color: verdictColor(c.verdict) }}>{c.verdict}</span>}
        />
        <Field k="fraud_probability" v={c.fraud_probability.toFixed(4)} />
        <Field k="pattern" v={c.pattern} />
        <Field k="pattern_description" v={c.pattern_description} />
        <Field
          k="affected_txn_ids"
          v={c.affected_txn_ids.length ? c.affected_txn_ids.join(", ") : "(none — legitimate)"}
        />
        <Field
          k="first_suspicious_txn_id"
          v={c.first_suspicious_txn_id || "(none)"}
        />
      </div>
      <div>
        <Field k="connected_card_ids" v={c.connected_card_ids.join(", ") || "(none)"} />
        <Field
          k="connected_device_profiles"
          v={c.connected_device_profiles.join(", ") || "(none)"}
        />
        <Field k="exposure_usd" v={`$${c.exposure_usd.toFixed(2)}`} />
        <Field k="evidence_items" v={String(c.evidence.length)} />
        <Field
          k="similar_prior_cases"
          v={c.similar_prior_cases.join(", ") || "(none)"}
        />
        <Field
          k="written_to_graph / graph_case_id"
          v={`${c.written_to_graph} / ${c.graph_case_id || "(empty)"}`}
        />
        <Field k="tool_calls / tokens / latency_s" v={`${cf.tool_calls} / ${cf.tokens} / ${cf.latency_s}`} />
      </div>
      <div className="col-span-2 mt-3">
        <div className="label mb-1">SUMMARY</div>
        <p className="border border-line bg-ink-850 p-3 text-[12px] leading-[19px] text-fg-2">
          {c.summary}
        </p>
      </div>
      <div className="col-span-2 mt-3">
        <div className="label mb-1">STOP REASON</div>
        <p className="border border-line bg-ink-850 p-3 text-[11.5px] leading-[18px] text-fg-2">
          {cf.stop_reason}
        </p>
      </div>
    </div>
  );
}

function TabEvidence({ cf }: { cf: CaseFile }) {
  return (
    <div className="space-y-1.5">
      {cf.case.evidence.map((e) => (
        <div key={e.evidence_id} className="border border-line bg-ink-850 p-2.5">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-bold text-accent">
              {e.evidence_id}
            </span>
            <Chip>{e.evidence_class.replace("_", " ")}</Chip>
            <Chip>{e.source}</Chip>
            <span className="ml-auto truncate font-mono text-[10px] text-dim">
              {e.ref}
            </span>
          </div>
          <p className="mt-1.5 text-[12px] leading-[18px] text-fg-2">{e.claim}</p>
          <div className="mt-1 text-[9.5px] text-dim">
            entities: {e.entity_ids.join(", ") || "—"}
          </div>
        </div>
      ))}
    </div>
  );
}

function TabFindings({ cf }: { cf: CaseFile }) {
  return (
    <div className="space-y-1.5">
      {cf.findings.map((f) => (
        <div key={f.finding_id} className="border border-line bg-ink-850 p-2.5">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-bold text-accent">
              {f.finding_id}
            </span>
            <span className="text-[12px] font-semibold text-fg">{f.title}</span>
            <Chip>{f.type.replace("_", " ")}</Chip>
            <span className="ml-auto font-mono text-[9.5px] text-dim">
              {f.evidence_ids.join(" ") || "—"}
            </span>
          </div>
          <p className="mt-1.5 text-[12px] leading-[18px] text-fg-2">
            {f.statement}
          </p>
        </div>
      ))}
      <div className="mt-3">
        <div className="label mb-1">GRAPH FACT vs INVESTIGATION INTERPRETATION</div>
        <p className="border border-line bg-ink-850 p-3 text-[11.5px] leading-[18px] text-fg-2">
          {cf.graph_evidence.graph_fact_vs_interpretation}
        </p>
      </div>
    </div>
  );
}

function TabDecision({ cf, shapLocal }: { cf: CaseFile; shapLocal: ShapLocalEntry | null }) {
  const pre = cf.pre_additional_evidence_state;
  const post = cf.post_additional_evidence_state;
  const pd = pre?.preliminary_decision;
  const ud = post?.updated_decision ?? cf.decision;

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="border border-line bg-ink-850 p-3">
        <div className="label mb-2">PRE-ADDITIONAL-EVIDENCE STATE</div>
        <Field k="stage" v={pre?.stage ?? "—"} />
        <Field k="evidence_requested" v={pre?.evidence_requested?.map((r) => r.type).join(", ") || "none"} />
        <Field
          k="preliminary verdict"
          v={pd ? `${pd.verdict} · p=${pd.fraud_probability.toFixed(4)} · ${pd.pattern}` : "—"}
        />
        <Field
          k="preliminary status"
          v={pd?.status ?? "—"}
        />
        <Field
          k="initial actions"
          v={cf.next_best_actions.initial.map((a) => a.action).join(", ")}
        />
      </div>

      <div className="border border-line bg-ink-850 p-3">
        <div className="label mb-2">POST-ADDITIONAL-EVIDENCE STATE</div>
        <Field
          k="additional_evidence_received"
          v={
            <span style={{ color: post?.additional_evidence_received ? "var(--color-ok)" : "var(--color-warn)" }}>
              {String(post?.additional_evidence_received ?? false)}
            </span>
          }
        />
        <Field
          k="updated verdict"
          v={`${ud.decision} · p=${cf.case.fraud_probability.toFixed(4)} · ${cf.case.pattern}`}
        />
        <Field k="updated status" v={ud.status} />
        <Field k="what_changed" v={cf.next_best_actions.what_changed} />
      </div>

      <div className="col-span-2">
        <div className="label mb-1">RATIONALE</div>
        <p className="border border-line bg-ink-850 p-3 text-[12px] leading-[19px] text-fg-2">
          {cf.decision.rationale}
        </p>
      </div>

      <div className="col-span-2 grid grid-cols-3 gap-3">
        <div className="border border-line bg-ink-850 p-3">
          <div className="label mb-1">SUPPORTING EVIDENCE IDS</div>
          <p className="font-mono text-[11px] leading-[17px] text-fg-2">
            {cf.decision.supporting_evidence_ids.join(", ")}
          </p>
        </div>
        <div className="border border-line bg-ink-850 p-3">
          <div className="label mb-1">POLICY RULES APPLIED</div>
          <p className="font-mono text-[11px] leading-[17px] text-fg-2">
            {cf.decision.policy_rules.join(", ") || "—"}
          </p>
        </div>
        <div className="border border-line bg-ink-850 p-3">
          <div className="label mb-1">SHAP INPUT</div>
          {shapLocal ? (
            <p className="font-mono text-[11px] leading-[17px] text-fg-2">
              txn {shapLocal.txn_id} · risk_score {shapLocal.risk_score} ·{" "}
              {shapLocal.top_contributing_features.length} features ·{" "}
              {shapLocal.model_prediction}
            </p>
          ) : (
            <p className="text-[11px] text-dim">No local SHAP entry stored.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function TabSar({ cf }: { cf: CaseFile }) {
  const s = cf.sar;
  if (!s.file) {
    return (
      <div className="space-y-3">
        <div className="border border-line bg-ink-850 p-3">
          <div className="label mb-1">SAR FILED</div>
          <p className="font-mono text-[13px] font-bold text-ok">false</p>
        </div>
        <div className="border border-line bg-ink-850 p-3">
          <div className="label mb-1">REASON</div>
          <p className="text-[12px] leading-[19px] text-fg-2">{s.reason}</p>
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        <div className="border border-bad/50 bg-bad/10 p-3">
          <div className="label mb-1">SAR FILED</div>
          <p className="font-mono text-[13px] font-bold text-bad">true</p>
        </div>
        <div className="border border-line bg-ink-850 p-3">
          <div className="label mb-1">TOTAL AMOUNT</div>
          <p className="font-mono text-[13px] font-bold text-fg">
            ${s.total_amount_usd.toFixed(2)}
          </p>
        </div>
        <div className="border border-line bg-ink-850 p-3">
          <div className="label mb-1">SUBJECTS</div>
          <p className="font-mono text-[12px] text-fg-2">{s.subjects.join(", ")}</p>
        </div>
        <div className="border border-line bg-ink-850 p-3">
          <div className="label mb-1">ACTIVITY DATES</div>
          <p className="font-mono text-[12px] text-fg-2">{s.activity_dates.join(", ")}</p>
        </div>
      </div>
      <div>
        <div className="label mb-1">REASON</div>
        <p className="border border-line bg-ink-850 p-3 text-[12px] leading-[19px] text-fg-2">
          {s.reason}
        </p>
      </div>
      <div>
        <div className="label mb-1">NARRATIVE</div>
        <p className="border border-line bg-ink-850 p-3 text-[12px] leading-[20px] text-fg-2">
          {s.narrative}
        </p>
      </div>
    </div>
  );
}

function TabActions({ cf }: { cf: CaseFile }) {
  const render = (title: string, list: typeof cf.next_best_actions.initial, tone?: string) => (
    <div>
      <div className="label mb-1.5">{title}</div>
      <div className="space-y-1">
        {list.map((a) => (
          <div key={a.action} className="border border-line bg-ink-850 p-2">
            <div className="flex items-center gap-2">
              <span className="px-1.5 py-[1px] text-[11px] font-bold" style={{ border: `1px solid ${tone ?? "var(--color-line)"}`, color: tone ?? "var(--color-fg)" }}>
                {actionLabel(a.action)}
              </span>
              <span className="font-mono text-[11px] text-fg">{a.action}</span>
              <Chip tone={a.route === "auto" ? "neutral" : "warn"}>{a.route}</Chip>
            </div>
            <p className="mt-1 text-[11px] leading-[16px] text-fg-2">{a.reason}</p>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="space-y-3">
      {render("INITIAL", cf.next_best_actions.initial, "var(--color-warn)")}
      <div className="border border-line bg-ink-850 p-2.5">
        <div className="label mb-1">WHAT CHANGED</div>
        <p className="text-[11.5px] leading-[18px] text-fg-2">
          {cf.next_best_actions.what_changed}
        </p>
      </div>
      {render("FINAL", cf.next_best_actions.final, verdictColor(cf.case.verdict))}
      <div>
        <div className="label mb-1.5">ACTIONS TAKEN</div>
        <div className="space-y-1">
          {cf.actions_taken.map((a) => (
            <div key={a.action} className="border border-line bg-ink-850 p-2 font-mono text-[11px] text-fg-2">
              {a.action} <span className="text-dim">[{a.route}]</span>
            </div>
          ))}
        </div>
      </div>
      {!!cf.actions_recommended_awaiting_approval?.length && (
        <div>
          <div className="label mb-1.5">AWAITING APPROVAL</div>
          <div className="space-y-1">
            {cf.actions_recommended_awaiting_approval.map((a) => (
              <div key={a.action} className="border border-warn/40 bg-warn/5 p-2 font-mono text-[11px] text-warn">
                {a.action} <span className="opacity-70">[{a.route}]</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TabApproval({ cf }: { cf: CaseFile }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="border border-line bg-ink-850 p-3">
        <div className="label mb-2">REQUIRED APPROVAL ROUTE</div>
        <div className="space-y-1">
          {cf.required_approval_route.map((r) => (
            <div key={r} className="flex items-center gap-2 font-mono text-[12px] text-fg-2">
              <span className={`h-1.5 w-1.5 rounded-full ${r === "auto" ? "bg-ok" : "bg-warn"}`} />
              {r === "auto" ? "auto — no approval required" : `${r} — analyst/L2 sign-off`}
            </div>
          ))}
        </div>
        <div className="label mt-3 mb-1.5">SAR STATUS</div>
        <Field k="file" v={String(cf.sar_status.file)} />
        <Field k="required_approval_route" v={cf.sar_status.required_approval_route} />
        <Field k="reason" v={cf.sar_status.reason} />
      </div>

      <div className="border border-line bg-ink-850 p-3">
        <div className="label mb-2">GRAPH WRITE</div>
        <div className="mb-2 flex items-center gap-2">
          <Chip tone="bad">{cf.graph_write.status}</Chip>
          <Chip>documented, not executed</Chip>
        </div>
        <Field k="written_to_graph" v={String(cf.graph_write.written_to_graph)} />
        <Field k="graph_case_id" v={cf.graph_write.graph_case_id || "(empty)"} />
        <Field k="reference" v={cf.graph_write.reference} />
        <p className="mt-2 text-[11px] leading-[17px] text-dim">
          {truncate(cf.graph_write.reason, 320)}
        </p>
      </div>

      <div className="col-span-2">
        <div className="label mb-1.5">EVIDENCE REQUESTS</div>
        {cf.evidence_requests.length ? (
          <div className="space-y-1">
            {cf.evidence_requests.map((r, i) => (
              <div key={i} className="border border-line bg-ink-850 p-2">
                <span className="font-mono text-[11px] text-accent">{r.type}</span>
                <span className="ml-3 text-[10px] text-dim">
                  after step {r.asked_after_step}
                </span>
                <p className="mt-1 text-[11.5px] text-fg-2">
                  “{r.assumed_response}”
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[11.5px] text-dim">No additional evidence requested.</p>
        )}
      </div>
    </div>
  );
}

function TabAudit({ cf }: { cf: CaseFile }) {
  const ge = cf.graph_evidence;
  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <div className="label mb-1.5">INVESTIGATION RECORD</div>
        <ol className="space-y-1.5">
          {cf.investigation_record.map((s) => (
            <li key={s.step} className="border border-line bg-ink-850 p-2">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-accent">
                  {String(s.step).padStart(2, "0")}
                </span>
                <span className="text-[11px] font-bold tracking-wide text-fg">
                  {s.name}
                </span>
              </div>
              <p className="mt-1 text-[11px] leading-[16px] text-fg-2">
                {s.detail}
              </p>
            </li>
          ))}
        </ol>
      </div>

      <div className="space-y-3">
        <div className="border border-line bg-ink-850 p-3">
          <div className="label mb-2">AUDIT COUNTERS</div>
          <Field k="tool_calls" v={String(cf.tool_calls)} />
          <Field k="tokens" v={`${cf.tokens} — no LLM key in this environment`} />
          <Field k="latency_s" v={cf.latency_s.toFixed(2)} />
          <Field k="stop_reason" v={cf.stop_reason} />
        </div>

        <div className="border border-line bg-ink-850 p-3">
          <div className="label mb-2">GRAPH EVIDENCE — QUERIES</div>
          {ge.queries.map((q) => (
            <div key={q.name} className="flex items-center gap-2 font-mono text-[11px] py-0.5">
              <span className={q.http_status === 200 ? "text-ok" : "text-bad"}>
                {q.http_status}
              </span>
              <span className="text-fg-2">{q.name}</span>
              <span className="text-dim">{JSON.stringify(q.params)}</span>
              <span className="ml-auto text-dim">{q.latency_ms}ms</span>
            </div>
          ))}
        </div>

        <div className="border border-line bg-ink-850 p-3">
          <div className="label mb-2">GRAPH EVIDENCE — EDGES ({ge.edges.length})</div>
          <div className="space-y-0.5 font-mono text-[11px]">
            {ge.edges.map((e, i) => (
              <div key={i} className="text-fg-2">
                <span className="text-dim">{e.from_type}</span> {e.from}{" "}
                <span className="text-accent">-{e.edge}-&gt;</span>{" "}
                <span className="text-dim">{e.to_type}</span> {e.to}
              </div>
            ))}
          </div>
        </div>

        <div className="border border-line bg-ink-850 p-3">
          <div className="label mb-2">PHASE 2 BASELINE</div>
          <p className="font-mono text-[11px] leading-[17px] text-fg-2">
            {typeof ge.phase_2_baseline === "string"
              ? ge.phase_2_baseline
              : JSON.stringify(ge.phase_2_baseline)}
          </p>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Architecture modal                                                  */
/* ------------------------------------------------------------------ */

export function ArchitectureModal({
  open,
  onClose,
  tg,
}: {
  open: boolean;
  onClose: () => void;
  tg: { ok: boolean; http_status: number; latency_ms: number } | null;
}) {
  if (!open) return null;
  const counts = ARCHITECTURE.reduce(
    (a, l) => ({ ...a, [l.status]: (a[l.status] ?? 0) + 1 }),
    {} as Record<string, number>,
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/85">
      <div className="flex max-h-[88vh] w-[1180px] max-w-[95vw] flex-col border border-line bg-ink-900 shadow-2xl">
        <header className="flex items-center gap-3 border-b border-line bg-ink-850 px-4 py-2.5">
          <span className="text-[12px] font-bold tracking-[0.16em] text-fg">
            SYSTEM ARCHITECTURE
          </span>
          <Chip tone="ok">{counts.live ?? 0} LIVE VERIFIED</Chip>
          <Chip tone="warn">{counts.wip ?? 0} IN PROGRESS</Chip>
          <Chip>{counts.arch ?? 0} ARCHITECTURAL</Chip>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto h-7 border border-line px-2.5 text-[11px] text-fg-2 hover:bg-ink-700"
          >
            CLOSE ✕
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-auto p-4">
          <ol className="space-y-1.5">
            {ARCHITECTURE.map((l, i) => {
              const resolved = {
                ...l,
                detail:
                  l.name === "TigerGraph"
                    ? `${l.detail} — live probe: ${tg ? `HTTP ${tg.http_status} (${tg.latency_ms}ms)` : "probing…"}.`
                    : l.detail,
              };
              return (
                <li key={l.name} className="flex items-stretch gap-2">
                  <div className="flex w-9 shrink-0 flex-col items-center">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full border border-line bg-ink-850 font-mono text-[10px] text-dim">
                      {i + 1}
                    </span>
                    {i < ARCHITECTURE.length - 1 && (
                      <span className="w-px flex-1 bg-line" />
                    )}
                  </div>

                  <div className="flex min-w-0 flex-1 items-start gap-3 border border-line bg-ink-850 px-3 py-2">
                    <span className="w-[170px] shrink-0 text-[12.5px] font-bold tracking-wide text-fg">
                      {l.name}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[11.5px] leading-[17px] text-fg-2">
                        {resolved.detail}
                      </p>
                      <p className="mt-0.5 font-mono text-[10px] text-dim">
                        {l.evidence}
                      </p>
                    </div>
                    <Chip tone={TONE[l.status] as "ok" | "warn" | "neutral"}>
                      {STATUS_LABEL[l.status]}
                    </Chip>
                  </div>
                </li>
              );
            })}
          </ol>

          <p className="mt-4 border-t border-line pt-3 text-[11px] leading-[17px] text-dim">
            LIVE VERIFIED = an artifact in this repository passed validation, or a
            read-only probe answered while this page was open. IN PROGRESS =
            dependency or state definition exists, pipeline not wired
            end-to-end. ARCHITECTURAL = described by the design, not implemented
            here — no layer in that state is presented as running.
          </p>
        </div>
      </div>
    </div>
  );
}
