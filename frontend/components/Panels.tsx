"use client";

import { useMemo, useState } from "react";
import { Chip, Empty, Panel } from "./ui";
import {
  CATEGORIES,
  actionLabel,
  categorize,
  direction,
  verdictColor,
} from "@/lib/classify";
import type {
  CaseFile,
  E2eRun,
  ShapGlobal,
  ShapLocalEntry,
  SummaryPayload,
} from "@/lib/types";

const DIR_META = {
  support: { label: "SUPPORTS FRAUD", tone: "bad" as const },
  contradict: { label: "CONTRADICTS", tone: "ok" as const },
  context: { label: "CONTEXT", tone: "neutral" as const },
};

export function EvidencePanel({ cf }: { cf: CaseFile }) {
  const [cat, setCat] = useState<string>("ALL");

  const classified = useMemo(
    () =>
      cf.case.evidence.map((e) => ({
        item: e,
        cat: categorize(e),
        dir: direction(e),
      })),
    [cf],
  );

  const counts = useMemo(() => {
    const m: Record<string, number> = { ALL: classified.length };
    for (const c of CATEGORIES) m[c] = 0;
    for (const x of classified) m[x.cat] = (m[x.cat] ?? 0) + 1;
    return m;
  }, [classified]);

  const shown =
    cat === "ALL" ? classified : classified.filter((x) => x.cat === cat);

  const supports = classified.filter((x) => x.dir.dir === "support").length;
  const contra = classified.filter((x) => x.dir.dir === "contradict").length;
  const context = classified.length - supports - contra;

  return (
    <Panel
      title="EVIDENCE"
      right={
        <span className="font-mono text-[10px] text-dim">
          <span className="text-bad">▲{supports}</span> ·{" "}
          <span className="text-ok">▼{contra}</span> ·{" "}
          <span>—{context}</span>
        </span>
      }
      bodyClass="flex flex-col p-0"
    >
      <div className="flex shrink-0 flex-wrap gap-1 border-b border-line bg-ink-850 px-2 py-1.5">
        {["ALL", ...CATEGORIES].map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setCat(c)}
            className={`rounded-sm border px-1.5 py-[2px] text-[9.5px] tracking-wide ${
              cat === c
                ? "border-accent/60 bg-accent/15 text-accent"
                : "border-line text-fg-2 hover:border-ink-600 hover:text-fg"
            }`}
          >
            {c} <span className="font-mono opacity-70">{counts[c] ?? 0}</span>
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-2">
        <div className="space-y-1.5">
          {shown.map((x) => {
            const meta = DIR_META[x.dir.dir];
            return (
              <article
                key={x.item.evidence_id}
                className="border border-line bg-ink-850 px-2 py-1.5"
              >
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-[9.5px] font-bold text-accent">
                    {x.item.evidence_id}
                  </span>
                  <Chip tone={meta.tone}>
                    {x.dir.dir === "support" ? "▲" : x.dir.dir === "contradict" ? "▼" : "—"}{" "}
                    {meta.label}
                  </Chip>
                  <span className="text-[9px] tracking-wider text-dim uppercase">
                    {x.item.evidence_class.replace("_", " ")}
                  </span>
                  {x.dir.signal ? (
                    <span className="ml-auto truncate font-mono text-[9px] text-dim">
                      {x.dir.signal}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-[10.5px] leading-[15px] text-fg-2">
                  {x.item.claim}
                </p>
                <div className="mt-1 flex items-center gap-2 text-[9px] text-dim">
                  <span className="font-mono">{x.item.source}</span>
                  <span className="truncate font-mono">{x.item.ref}</span>
                </div>
              </article>
            );
          })}
          {!shown.length && <Empty text="No evidence in this category." />}
        </div>

        <p className="mt-2 border-t border-line pt-1.5 text-[9px] leading-[13px] text-dim">
          Direction is the sign of the learned signal weight in{" "}
          <span className="font-mono">models/evidence_weights.json</span> for the
          phrase matched in the claim (21 signals, 14,055 fraud / 900 cleared
          labels). Claims matching no signal are neutral context. Category and
          class are read from the case record.
        </p>
      </div>
    </Panel>
  );
}

export function MlPanel({
  cf,
  shapLocal,
  e2e,
  metrics,
}: {
  cf: CaseFile;
  shapLocal: ShapLocalEntry | null;
  e2e: E2eRun | null;
  metrics: SummaryPayload["metrics"];
}) {
  const modelClaim = cf.case.evidence.find(
    (e) => e.evidence_class === "model_analytical" && /Model score for transaction/.test(e.claim),
  );
  const liveModel = e2e?.model_probability ?? parseModelScore(modelClaim?.claim ?? "");
  const before = cf.pre_additional_evidence_state?.preliminary_decision?.fraud_probability;
  const riskInput = shapLocal?.risk_score ?? null;

  return (
    <Panel title="ML" right={<Chip tone="ok">RISK_SCORE EXCLUDED</Chip>}>
      <div className="grid grid-cols-2 gap-1.5">
        <Cell label="MODEL" value={shortModel(metrics.model)} sub="models/metrics.json" />
        <Cell label="FEATURES" value={metrics.n_features} sub={`${metrics.n_samples} samples`} />
        <Cell
          label="ROC-AUC"
          value={metrics.test.roc_auc.toFixed(4)}
          sub="held-out test"
          tone="var(--color-ok)"
        />
        <Cell
          label="ACCURACY"
          value={metrics.test.accuracy.toFixed(4)}
          sub={`P ${metrics.test.precision.toFixed(3)} · R ${metrics.test.recall.toFixed(3)}`}
          tone="var(--color-ok)"
        />
      </div>

      <div className="mt-1 space-y-1 border border-line bg-ink-850 px-2 py-1">
        <Row
          k="Case model score"
          v={liveModel !== null ? liveModel.toFixed(4) : "—"}
          tone="var(--color-fg)"
        />
        <Row
          k="Case risk_score (input)"
          v={riskInput !== null ? riskInput.toFixed(2) : "not present"}
          tone="var(--color-warn)"
        />
        <Row
          k="p before evidence"
          v={before !== undefined ? before.toFixed(4) : "—"}
        />
        <Row
          k="p after evidence"
          v={cf.case.fraud_probability.toFixed(4)}
          tone={verdictColor(cf.case.verdict)}
        />
        <Row k="Verdict" v={cf.case.verdict} tone={verdictColor(cf.case.verdict)} />
      </div>

      <p className="mt-1 text-[8.5px] leading-[12px] text-dim">
        {metrics.features_excluded.join(" · ")}
        {e2e ? " · live demo phase3_e2e.json" : " · case record"}
      </p>
    </Panel>
  );
}

export function XaiPanel({
  shapLocal,
  shapGlobal,
}: {
  shapLocal: ShapLocalEntry | null;
  shapGlobal: ShapGlobal | null;
}) {
  if (!shapLocal && !shapGlobal) {
    return (
      <Panel title="XAI · SHAP">
        <Empty text="No SHAP explanation stored for this case." />
      </Panel>
    );
  }

  const feats = (shapLocal?.top_contributing_features ?? []).slice(0, 7);
  const maxAbs = Math.max(
    0.0001,
    ...feats.map((f) => Math.abs(f.shap_value)),
  );

  return (
    <Panel
      title="XAI · SHAP"
      right={
        <span className="font-mono text-[9.5px] text-dim">
          {shapGlobal ? `${shapGlobal.n_rows_explained} rows` : "local"}
        </span>
      }
    >
      {shapLocal && (
        <>
          <div className="mb-1 flex items-center justify-between text-[9.5px]">
            <span className="tracking-wider text-dim uppercase">
              txn {shapLocal.txn_id} · prediction {shapLocal.model_prediction}
            </span>
            <span className="font-mono text-fg-2">
              {shapLocal.top_contributing_features.length} features
            </span>
          </div>

          <div className="space-y-[3px]">
            {feats.map((f) => {
              const pos = f.shap_value >= 0;
              const w = (Math.abs(f.shap_value) / maxAbs) * 50;
              return (
                <div key={f.feature} className="flex items-center gap-1.5">
                  <span className="w-[112px] shrink-0 truncate font-mono text-[9.5px] text-fg-2">
                    {f.feature}
                  </span>
                  <div className="relative h-[13px] flex-1 border border-line bg-ink-850">
                    <span className="absolute top-0 bottom-0 left-1/2 w-px bg-line" />
                    <span
                      className="absolute top-[1px] bottom-[1px]"
                      style={{
                        background: pos ? "var(--color-bad)" : "var(--color-ok)",
                        opacity: 0.85,
                        left: pos ? "50%" : `${50 - w}%`,
                        width: `${w}%`,
                      }}
                    />
                  </div>
                  <span
                    className="w-[52px] shrink-0 text-right font-mono text-[9.5px]"
                    style={{ color: pos ? "var(--color-bad)" : "var(--color-ok)" }}
                  >
                    {pos ? "+" : ""}
                    {f.shap_value.toFixed(4)}
                  </span>
                </div>
              );
            })}
          </div>

          <p className="mt-1 text-[8.5px] leading-[12px] text-dim">
            {shapLocal.note}
          </p>
        </>
      )}

      {shapGlobal && (
        <>
          <div className="label mt-2 mb-1 border-t border-line pt-1.5">
            GLOBAL · TOP FEATURES
          </div>
          <div className="flex flex-wrap gap-1">
            {shapGlobal.mean_abs_shap_top15.slice(0, 6).map((f) => (
              <span
                key={f.feature}
                className="border border-line bg-ink-850 px-1.5 py-[1px] font-mono text-[9px] text-fg-2"
                title={`mean |SHAP| = ${f.mean_abs_shap.toFixed(5)}`}
              >
                {f.feature}
                <span className="ml-1 text-dim">
                  {f.mean_abs_shap.toFixed(3)}
                </span>
              </span>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}

export function ActionPanel({ cf }: { cf: CaseFile }) {
  const fin = cf.next_best_actions.final;
  const primary = fin[0];
  const evidence = cf.decision.supporting_evidence_ids;

  return (
    <Panel
      title="NEXT BEST ACTION"
      right={
        <Chip tone={cf.case.verdict === "fraud" ? "bad" : cf.case.verdict === "legitimate" ? "ok" : "warn"}>
          {cf.case.verdict.toUpperCase()}
        </Chip>
      }
      bodyClass="p-2"
    >
      {primary ? (
        <>
          <div className="flex items-center gap-2">
            <span
              className="border px-2 py-1 text-[13px] font-bold tracking-[0.1em]"
              style={{
                color: verdictColor(cf.case.verdict),
                borderColor: verdictColor(cf.case.verdict),
                background: `${verdictColor(cf.case.verdict)}18`,
              }}
            >
              {actionLabel(primary.action)}
            </span>
            <span className="truncate font-mono text-[11px] text-fg-2">
              {primary.action}
            </span>
            <span className="ml-auto shrink-0">
              <Chip tone={primary.route === "auto" ? "neutral" : "warn"}>
                {primary.route === "auto" ? "AUTO" : `APPROVAL ${primary.route}`}
              </Chip>
            </span>
          </div>

          <dl className="mt-1 space-y-0.5 text-[10.5px]">
            <Line k="REASON" v={primary.reason} clamp={2} />
            <Line
              k="EVIDENCE"
              v={`${evidence.length} items cited — ${evidence.join(", ")}`}
              mono
              clamp={2}
            />
            <Line
              k="CONFIDENCE"
              v={`p = ${cf.case.fraud_probability.toFixed(4)} · pattern ${cf.case.pattern}`}
              mono
            />
            <Line
              k="APPROVAL ROUTE"
              v={cf.required_approval_route.join(", ")}
              mono
            />
          </dl>

          <div className="mt-1 border-t border-line pt-1">
            <div className="label mb-0.5">ALL RECOMMENDED ACTIONS</div>
            <div className="flex flex-wrap gap-1">
              {fin.map((a) => (
                <span
                  key={a.action + a.route}
                  title={a.reason}
                  className="border border-line bg-ink-850 px-1.5 py-[1px] font-mono text-[9.5px] text-fg-2"
                >
                  {actionLabel(a.action)}{" "}
                  <span className="text-dim">{a.action}</span>{" "}
                  <span
                    className={a.route === "auto" ? "text-ok" : "text-warn"}
                  >
                    {a.route}
                  </span>
                </span>
              ))}
            </div>
          </div>

          <div className="mt-1 border border-line bg-ink-850 px-2 py-1">
            <div className="label mb-0.5">WHAT CHANGED</div>
            <p className="line-clamp-2 text-[10px] leading-[14px] text-fg-2">
              {cf.next_best_actions.what_changed}
            </p>
          </div>
        </>
      ) : (
        <Empty text="No recommendation recorded." />
      )}
    </Panel>
  );
}

function Cell({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: string;
}) {
  return (
    <div className="border border-line bg-ink-850 px-2 py-[3px]">
      <div className="text-[8.5px] tracking-[0.12em] text-dim">{label}</div>
      <div
        className="truncate font-mono text-[14px] leading-5 font-bold"
        style={tone ? { color: tone } : undefined}
      >
        {value}
      </div>
      {sub && <div className="truncate text-[8.5px] text-dim">{sub}</div>}
    </div>
  );
}

function Row({ k, v, tone }: { k: string; v: string; tone?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-[10px] text-fg-2">{k}</span>
      <span
        className="font-mono text-[11px] font-semibold"
        style={tone ? { color: tone } : undefined}
      >
        {v}
      </span>
    </div>
  );
}

const CLAMP: Record<number, string> = { 2: "line-clamp-2", 3: "line-clamp-3" };

function Line({
  k,
  v,
  mono,
  clamp,
}: {
  k: string;
  v: string;
  mono?: boolean;
  clamp?: number;
}) {
  return (
    <div className="flex gap-2">
      <dt className="w-[104px] shrink-0 text-[9px] tracking-[0.1em] text-dim uppercase">
        {k}
      </dt>
      <dd
        title={v}
        className={`min-w-0 flex-1 leading-[15px] text-fg-2 ${
          mono ? "font-mono text-[10px]" : ""
        } ${clamp ? (CLAMP[clamp] ?? "") : ""}`}
      >
        {v}
      </dd>
    </div>
  );
}

function shortModel(m: string): string {
  if (m.includes("RandomForest")) return "RandomForest";
  if (m.includes("XGB")) return "XGBoost";
  return m.split(".").pop() ?? m;
}

function parseModelScore(claim: string): number | null {
  const m = /Model score for transaction \d+ is ([0-9.]+)/.exec(claim);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isFinite(n) ? n : null;
}
