"use client";

import {
  Bar,
  Card,
  ErrorNote,
  Loading,
  PageHeader,
  Section,
  StatTile,
  Tag,
} from "@/components/kit";
import { useJson } from "@/lib/useJson";
import type { ModelPayload } from "@/lib/types";

export default function ModelPage() {
  const { data, error, loading } = useJson<ModelPayload>("/api/model");

  if (error) return <ErrorNote what="/api/model" message={error} />;
  if (loading || !data) return <Loading what="models/metrics.json" />;

  const m = data.metrics;
  const w = data.weights;
  const cm = m.test.confusion_matrix;
  const [tn, fp] = cm?.[0] ?? [0, 0];
  const [fn, tp] = cm?.[1] ?? [0, 0];

  const fi = m.feature_importance_top15 ?? [];
  const maxFi = Math.max(0.0001, ...fi.map((f) => f.importance));

  const sg = data.shapGlobal;
  const shapRows = sg?.mean_abs_shap_top15 ?? [];
  const maxShap = Math.max(0.0001, ...shapRows.map((f) => f.mean_abs_shap));

  const signals = w
    ? Object.entries(w.weights).sort(
        (a, b) => Math.abs(b[1]) - Math.abs(a[1]),
      )
    : [];
  const maxW = Math.max(1, ...signals.map(([, v]) => Math.abs(v)));

  return (
    <div className="fade-up pb-16">
      <PageHeader
        eyebrow="MODULE 04 · MODEL & XAI"
        title="The classifier, its evidence and its explanations"
        lede="A supervised fraud model trained on the closed-case history, with SHAP attribution for every decision. The pre-computed risk_score column is excluded from training as label leakage and is only ever displayed as context."
        actions={<Tag tone="warn">risk_score EXCLUDED</Tag>}
        meta={
          <span className="font-mono text-[10px] text-dim">
            models/metrics.json · xai/shap_global.json
          </span>
        }
      />

      {/* ---------- metrics ---------- */}
      <Section
        eyebrow="HELD-OUT PERFORMANCE"
        title="Binary transaction-level fraud risk"
      >
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <StatTile label="Model" value={shortModel(m.model)} sub={m.task} />
          <StatTile
            label="ROC-AUC"
            value={m.test.roc_auc.toFixed(4)}
            tone="var(--color-ok)"
            sub="held-out test"
          />
          <StatTile
            label="Accuracy"
            value={m.test.accuracy.toFixed(4)}
            tone="var(--color-ok)"
            sub={`${m.n_samples} samples`}
          />
          <StatTile
            label="Precision"
            value={m.test.precision.toFixed(4)}
            sub="of flagged, truly fraud"
          />
          <StatTile
            label="Recall"
            value={m.test.recall.toFixed(4)}
            sub="of fraud, caught"
          />
          <StatTile
            label="F1"
            value={m.test.f1.toFixed(4)}
            sub={`${m.n_features} features`}
          />
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <Card title="FEATURE IMPORTANCE · TOP 15">
            <div className="space-y-1.5">
              {fi.map((f) => (
                <div key={f.feature} className="flex items-center gap-3">
                  <span className="w-[150px] shrink-0 truncate font-mono text-[11px] text-fg-2">
                    {f.feature}
                  </span>
                  <div className="min-w-0 flex-1">
                    <Bar
                      value={f.importance}
                      max={maxFi}
                      tone="var(--color-accent)"
                      height={10}
                    />
                  </div>
                  <span className="w-[54px] shrink-0 text-right font-mono text-[11px] text-fg">
                    {f.importance.toFixed(4)}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-2.5 border-t border-line pt-2 text-[11px] leading-[17px] text-dim">
              Split-based impurity importance from{" "}
              <span className="font-mono">models/metrics.json</span>. Label
              source:{" "}
              <span className="font-mono text-fg-2">{m.label_source}</span>.
            </p>
          </Card>

          <div className="space-y-4">
            <Card title="CONFUSION MATRIX">
              <div className="grid grid-cols-[auto_1fr_1fr] gap-1 text-center font-mono text-[12px]">
                <span />
                <span className="text-[9.5px] tracking-wider text-dim uppercase">
                  pred fraud
                </span>
                <span className="text-[9.5px] tracking-wider text-dim uppercase">
                  pred clear
                </span>

                <span className="text-[9.5px] tracking-wider text-dim uppercase">
                  act fraud
                </span>
                <span className="border border-ok/40 bg-ok/10 py-2 text-ok">
                  {tp}
                </span>
                <span className="border border-bad/40 bg-bad/10 py-2 text-bad">
                  {fn}
                </span>

                <span className="text-[9.5px] tracking-wider text-dim uppercase">
                  act clear
                </span>
                <span className="border border-bad/40 bg-bad/10 py-2 text-bad">
                  {fp}
                </span>
                <span className="border border-ok/40 bg-ok/10 py-2 text-ok">
                  {tn}
                </span>
              </div>
              <p className="mt-2 text-[10.5px] leading-[15px] text-dim">
                Precision {m.test.precision.toFixed(3)} = {tp}/({tp}+{fp}) ·
                Recall {m.test.recall.toFixed(3)} = {tp}/({tp}+{fn}).
              </p>
            </Card>

            <Card title="TRAINING">
              <div className="space-y-1 font-mono text-[11.5px] text-fg-2">
                <Row k="samples" v={String(m.n_samples)} />
                <Row k="features" v={String(m.n_features)} />
                <Row
                  k="positive rate"
                  v={m.positive_rate_train.toFixed(4)}
                />
                <Row k="trained at" v={m.trained_at} />
                <Row k="train time" v={`${m.train_seconds.toFixed(2)}s`} />
                <Row k="excluded" v={m.features_excluded.join(", ")} warn />
              </div>
            </Card>
          </div>
        </div>
      </Section>

      {/* ---------- SHAP global ---------- */}
      <Section
        eyebrow="EXPLAINABILITY"
        title="Global SHAP attribution — what drives the score"
        lede="Mean absolute SHAP value per feature across the benchmark cases: the further right, the more that feature moves the prediction in either direction."
        className="border-t border-line"
      >
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
          <Card
            title="GLOBAL SHAP · TOP 15"
            right={
              <span className="font-mono text-[10px] text-dim">
                {sg
                  ? `baseline ${sg.baseline_output_mean.toFixed(4)} · ${sg.n_rows_explained} rows`
                  : "—"}
              </span>
            }
          >
            <div className="space-y-1.5">
              {shapRows.map((f) => (
                <div key={f.feature} className="flex items-center gap-3">
                  <span className="w-[150px] shrink-0 truncate font-mono text-[11px] text-fg-2">
                    {f.feature}
                  </span>
                  <div className="min-w-0 flex-1">
                    <Bar
                      value={f.mean_abs_shap}
                      max={maxShap}
                      tone="var(--color-violet)"
                      height={10}
                    />
                  </div>
                  <span className="w-[64px] shrink-0 text-right font-mono text-[11px] text-fg">
                    {f.mean_abs_shap.toFixed(4)}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-2.5 border-t border-line pt-2 text-[11px] leading-[17px] text-dim">
              Source <span className="font-mono">xai/shap_global.json</span>.
              Per-case attribution lives on each case page under MODEL &amp; XAI.
            </p>
          </Card>

          <Card
            title="EVIDENCE SIGNAL WEIGHTS"
            right={
              <span className="font-mono text-[10px] text-dim">
                {w?.signal_count ?? "—"} signals
              </span>
            }
          >
            {w ? (
              <>
                <p className="text-[11.5px] leading-[17px] text-fg-2">
                  {w.method}. Positive weight pushes toward fraud, negative
                  weight pushes toward legitimate.
                </p>
                <div className="mt-2.5 max-h-[330px] space-y-1.5 overflow-auto pr-1">
                  {signals.map(([name, weight]) => {
                    const r = w.rates?.[name];
                    const positive = weight >= 0;
                    return (
                      <div key={name} className="border border-line bg-ink-850 px-2 py-1.5">
                        <div className="flex items-center gap-2">
                          <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-fg">
                            {name}
                          </span>
                          <span
                            className="font-mono text-[11px] font-bold"
                            style={{
                              color: positive
                                ? "var(--color-bad)"
                                : "var(--color-ok)",
                            }}
                          >
                            {positive ? "+" : ""}
                            {weight.toFixed(3)}
                          </span>
                        </div>
                        <div className="mt-1">
                          <Bar
                            value={Math.abs(weight)}
                            max={maxW}
                            tone={
                              positive
                                ? "var(--color-bad)"
                                : "var(--color-ok)"
                            }
                            height={6}
                          />
                        </div>
                        {r ? (
                          <div className="mt-1 flex justify-between font-mono text-[9px] text-dim">
                            <span>fraud {(r.fraud_rate * 100).toFixed(3)}%</span>
                            <span>
                              cleared {(r.cleared_rate * 100).toFixed(3)}%
                            </span>
                            <span>
                              hits {r.fraud_hits}/{r.cleared_hits}
                            </span>
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
                <div className="mt-2 border-t border-line pt-2 text-[10.5px] leading-[15px] text-dim">
                  Labeled {w.labeled_fraud_txns.toLocaleString()} fraud /{" "}
                  {w.labeled_cleared_txns.toLocaleString()} cleared. Leakage
                  guard: {w.leakage_guard}.
                </div>
              </>
            ) : (
              <p className="text-[11.5px] text-dim">
                models/evidence_weights.json not available.
              </p>
            )}
          </Card>
        </div>
      </Section>

      {/* ---------- how to read ---------- */}
      <Section
        eyebrow="HOW TO READ IT"
        title="Three rules this model follows"
        className="border-t border-line"
      >
        <div className="grid gap-3 md:grid-cols-3">
          {[
            {
              n: "01",
              t: "Score is an input, not a verdict",
              d: "The benchmark warns that above 0.7 most flagged transactions turn out to be legitimate, so the probability is always shown next to the graph evidence and the decision rationale.",
            },
            {
              n: "02",
              t: "No leakage features",
              d: "risk_score is a pre-computed dataset column that already encodes the outcome. It is excluded from training and displayed only as context.",
            },
            {
              n: "03",
              t: "Every prediction is decomposed",
              d: "SHAP turns the score into per-feature contributions, so the analyst sees which signals pushed toward fraud and which pushed back toward legitimate.",
            },
          ].map((c) => (
            <div key={c.n} className="border border-line bg-ink-900 p-4">
              <div className="font-mono text-[11px] tracking-[0.2em] text-accent">
                RULE {c.n}
              </div>
              <h3 className="mt-2 text-[14px] font-bold text-fg">{c.t}</h3>
              <p className="mt-1.5 text-[11.5px] leading-[18px] text-fg-2">
                {c.d}
              </p>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

function Row({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-line/60 pb-1 last:border-0">
      <span className="text-dim">{k}</span>
      <span
        className={`truncate text-right ${warn ? "text-warn" : "text-fg"}`}
        title={v}
      >
        {v}
      </span>
    </div>
  );
}

function shortModel(full: string): string {
  const tail = full.split(".").pop() ?? full;
  return tail.replace("Classifier", "");
}
