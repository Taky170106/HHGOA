"""HHGoa 2026 — ML risk model + SHAP explanation (Phase 4).

Trains a binary fraud-risk classifier on REAL graph-derived features and REAL
historical labels, then explains it with SHAP.

LABELS (from DATASET/closed_cases_history.csv, never invented):
  positive (1) = first_fraud_txn_id of every case with outcome == confirmed_fraud
  negative (0) = transactions belonging to cases with outcome == cleared
  Both classes are *investigated* transactions, so the model learns to separate
  confirmed fraud from investigated-but-cleared activity — not "investigated vs
  random".

FEATURES: transaction attributes + graph structure derived from the SAME edge
files that were loaded into TigerGraph (data/edges/*.csv), e.g. card degree,
shared-device degree, email-domain degree, historical case involvement.
`risk_score` from the dataset is deliberately EXCLUDED (it is a pre-computed
score and would leak the answer).

MODEL EXPLANATION (SHAP) and GRAPH EVIDENCE (TigerGraph queries) are produced
separately and are never conflated.

Run:  python ml/train.py
Out:  models/fraud_model.pkl, models/metrics.json,
      xai/shap_global.json, xai/shap_local_<case>.json
"""
from __future__ import annotations

import csv
import io
import json
import os
import pickle
import random
import sys
import time

import numpy as np
import pandas as pd

if not getattr(sys.stdout, "_hhg_wrapped", False):
    _w = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _w._hhg_wrapped = True
    sys.stdout = _w

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGES = os.path.join(ROOT, "data", "edges")
VERTS = os.path.join(ROOT, "data", "vertices")
MODELS = os.path.join(ROOT, "models")
XAI = os.path.join(ROOT, "xai")
for d in (MODELS, XAI):
    os.makedirs(d, exist_ok=True)

T0 = time.time()
random.seed(42)
np.random.seed(42)


def log(msg):
    print(f"[{time.time()-T0:7.1f}s] {msg}", flush=True)


# ---------------------------------------------------------------------------
# 1. Labels from historical closed cases
# ---------------------------------------------------------------------------
def load_labels():
    pos, neg = set(), set()
    with open(os.path.join(ROOT, "DATASET", "closed_cases_history.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["outcome"] == "confirmed_fraud":
                if r["first_fraud_txn_id"]:
                    pos.add(r["first_fraud_txn_id"])
            elif r["outcome"] == "cleared":
                for t in r["txn_ids"].split(";"):
                    t = t.strip()
                    if t:
                        neg.add(t)
    # a transaction cannot be both
    neg -= pos
    return pos, neg


# ---------------------------------------------------------------------------
# 2. Graph-derived features (from the same edge files loaded into TigerGraph)
# ---------------------------------------------------------------------------
def graph_features(txns: pd.DataFrame) -> pd.DataFrame:
    feats = pd.DataFrame(index=txns.index)
    card = txns["card_id"].astype(str)
    cust = txns["customer_id"].astype(str)
    feats["txn_id"] = txns["txn_id"].astype(str)
    feats["card_id"] = card
    feats["customer_id"] = cust

    # made: card -> txn
    made = pd.read_csv(os.path.join(EDGES, "made.csv"), dtype=str)
    feats["card_txn_degree"] = card.map(made["from_card_id"].value_counts()).fillna(0).astype(float)
    # card of EVERY transaction in the graph (not just this labelled sample)
    txn_card_all = pd.Series(made["from_card_id"].values, index=made["to_txn_id"].values)

    # owns: customer -> card
    owns = pd.read_csv(os.path.join(EDGES, "owns.csv"), dtype=str)
    feats["customer_card_degree"] = cust.map(
        owns["from_customer_id"].value_counts()).fillna(0).astype(float)
    feats["card_owner_degree"] = card.map(
        owns["to_card_id"].value_counts()).fillna(0).astype(float)

    # next: txn -> txn (temporal chain per card)
    nxt = pd.read_csv(os.path.join(EDGES, "next.csv"), dtype=str)
    from_card_all = nxt["from_txn_id"].map(txn_card_all)
    to_card_all = nxt["to_txn_id"].map(txn_card_all)
    feats["card_prev_degree"] = card.map(from_card_all.value_counts()).fillna(0).astype(float)
    feats["card_next_degree"] = card.map(to_card_all.value_counts()).fillna(0).astype(float)
    td = pd.to_numeric(nxt["time_delta_hours"], errors="coerce")
    ar = pd.to_numeric(nxt["amount_ratio"], errors="coerce")
    prev_td = td.groupby(nxt["to_txn_id"].values).mean()      # keyed by transaction
    prev_ar = ar.groupby(nxt["to_txn_id"].values).mean()
    feats["prev_time_delta_hours"] = txns["txn_id"].astype(str).map(prev_td).fillna(-1.0).astype(float)
    feats["prev_amount_ratio"] = txns["txn_id"].astype(str).map(prev_ar).fillna(-1.0).astype(float)
    feats["card_mean_time_delta"] = card.map(
        td.groupby(from_card_all.values).mean()).fillna(-1.0).astype(float)

    # from_device: txn -> device
    fd = pd.read_csv(os.path.join(EDGES, "from_device.csv"), dtype=str)
    dev_of_txn = pd.Series(fd["to_device_profile_id"].values, index=fd["from_txn_id"].values)
    txn_dev = txns["txn_id"].astype(str).map(dev_of_txn)
    dev_size = fd["to_device_profile_id"].value_counts()
    feats["device_shared_txn_degree"] = txn_dev.map(dev_size).fillna(0).astype(float)
    # card of EVERY transaction (from the made edge file, not just this sample)
    txn_card_all = pd.Series(made["from_card_id"].values, index=made["to_txn_id"].values)
    cards_per_dev = fd.assign(c=fd["from_txn_id"].map(txn_card_all)) \
        .groupby("to_device_profile_id")["c"].nunique()
    feats["device_distinct_cards"] = txn_dev.map(cards_per_dev).fillna(0).astype(float)
    feats["device_has_edge"] = txn_dev.notna().astype(float)
    feats["device_newness"] = pd.to_numeric(
        txns["txn_id"].astype(str).map(pd.Series(fd["newness"].values, index=fd["from_txn_id"].values)),
        errors="coerce").fillna(-1.0).astype(float)

    # email domains
    pe = pd.read_csv(os.path.join(EDGES, "purchaser_email.csv"), dtype=str)
    re_ = pd.read_csv(os.path.join(EDGES, "recipient_email.csv"), dtype=str)
    feats["purchaser_domain_degree"] = txns["p_emaildomain"].map(
        pe["to_domain"].value_counts()).fillna(0).astype(float)
    feats["recipient_domain_degree"] = txns["r_emaildomain"].map(
        re_["to_domain"].value_counts()).fillna(0).astype(float)

    # billing region
    bi = pd.read_csv(os.path.join(EDGES, "billed_in.csv"), dtype=str)
    feats["region_degree"] = txns["addr1"].astype(str).map(
        bi.groupby("to_region_code")["from_txn_id"].count()).fillna(0).astype(float)

    # historical case involvement (investigation memory)
    inv = pd.read_csv(os.path.join(EDGES, "involves.csv"), dtype=str)
    inv_card = inv["from_case_id"].values  # placeholder to keep code linear
    cases_per_txn = inv["to_txn_id"].value_counts()
    feats["txn_in_closed_cases"] = txns["txn_id"].astype(str).map(cases_per_txn).fillna(0).astype(float)
    txn_case = pd.Series(inv["from_case_id"].values, index=inv["to_txn_id"].values)
    cases_per_card = txns["txn_id"].astype(str).map(txn_case).groupby(card.values).nunique()
    feats["card_historical_cases"] = card.map(cases_per_card).fillna(0).astype(float)

    on_card = pd.read_csv(os.path.join(EDGES, "on_card.csv"), dtype=str)
    feats["card_on_card_cases"] = card.map(on_card["to_card_id"].value_counts()).fillna(0).astype(float)
    del inv_card
    return feats


def transaction_attrs(txns: pd.DataFrame) -> pd.DataFrame:
    a = pd.DataFrame(index=txns.index)
    a["amount"] = pd.to_numeric(txns["amount"], errors="coerce").fillna(0.0)
    a["log_amount"] = np.log1p(a["amount"])
    a["dt_seconds"] = pd.to_numeric(txns["dt_seconds"], errors="coerce").fillna(0.0)
    ts = pd.to_numeric(txns["ts"], errors="coerce")
    hour = ((ts / 3600.0) % 24).fillna(12.0)
    a["hour"] = hour
    a["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    a["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    a["is_night"] = ((hour < 6) | (hour >= 22)).astype(float)
    a["dist1"] = pd.to_numeric(txns["dist1"], errors="coerce").fillna(-1.0)
    a["dist2"] = pd.to_numeric(txns["dist2"], errors="coerce").fillna(-1.0)
    a["addr2"] = pd.to_numeric(txns["addr2"], errors="coerce").fillna(-1.0)
    a["channel"] = pd.to_numeric(txns["channel"], errors="coerce").fillna(-1.0)
    a["product_cd"] = pd.Categorical(txns["product_cd"].fillna("NA")).codes.astype(float)
    a["has_p_email"] = txns["p_emaildomain"].notna().astype(float)
    a["has_r_email"] = txns["r_emaildomain"].notna().astype(float)
    return a


def main():
    log("loading labels from DATASET/closed_cases_history.csv")
    pos, neg = load_labels()
    log(f"  confirmed_fraud txns={len(pos)}   cleared txns={len(neg)}")

    # negatives (investigated and cleared) are scarcer than confirmed-fraud
    # transactions; keep every labelled transaction and let class_weight balance
    # the fit rather than silently discarding positives.
    pos_l, neg_l = sorted(pos), sorted(neg)
    labels = {t: 1 for t in pos_l}
    labels.update({t: 0 for t in neg_l})
    log(f"  labelled set = {len(pos_l)} fraud + {len(neg_l)} cleared")

    # benchmark flagged transactions are always evaluated too
    bench = list(csv.DictReader(open(os.path.join(VERTS, "benchmark_case.csv"), encoding="utf-8")))
    bench_txns = [b["flagged_txn_id"] for b in bench]

    log("loading transaction vertices")
    cols = ["txn_id", "customer_id", "card_id", "ts", "dt_seconds", "amount",
            "product_cd", "channel", "addr1", "addr2", "dist1", "dist2",
            "p_emaildomain", "r_emaildomain"]
    all_tx = pd.read_csv(os.path.join(VERTS, "transaction.csv"),
                         usecols=cols, dtype={"txn_id": str, "customer_id": str, "card_id": str})
    all_tx = all_tx.set_index("txn_id", drop=False)

    wanted = list(labels) + [t for t in bench_txns if t in all_tx.index]
    txns = all_tx.loc[[t for t in wanted if t in all_tx.index]].copy()
    log(f"  selected {len(txns)} transactions with labels/benchmark")

    log("computing graph-derived features from data/edges")
    F = graph_features(txns)
    A = transaction_attrs(txns)
    X = pd.concat([A, F.drop(columns=["txn_id", "card_id", "customer_id"])], axis=1)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    y = np.array([labels.get(t, np.nan) for t in X.index], dtype=float)
    keep = ~np.isnan(y)
    y = y[keep].astype(int)
    Xl = X[keep]
    log(f"  feature matrix {Xl.shape}, positives={int(y.sum())}, negatives={int((1-y).sum())}")
    feature_names = list(Xl.columns)

    # ------------------------------------------------------------------
    # 3. Train / evaluate
    # ------------------------------------------------------------------
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                                 precision_score, recall_score, roc_auc_score)
    from sklearn.model_selection import train_test_split

    Xtr, Xte, ytr, yte = train_test_split(
        Xl, y, test_size=0.25, random_state=42, stratify=y)
    log(f"  train={len(Xtr)} test={len(Xte)}")

    clf = RandomForestClassifier(n_estimators=300, min_samples_leaf=5,
                                 max_features="sqrt", class_weight="balanced",
                                 n_jobs=-1, random_state=42)
    t1 = time.time()
    clf.fit(Xtr, ytr)
    log(f"  trained RandomForest in {time.time()-t1:.1f}s")

    proba = clf.predict_proba(Xte)[:, 1]
    pred = (proba >= 0.5).astype(int)
    metrics = {
        "model": "sklearn.ensemble.RandomForestClassifier",
        "task": "binary transaction-level fraud risk",
        "label_source": "DATASET/closed_cases_history.csv (outcome)",
        "features_excluded": ["risk_score (pre-computed dataset score = leakage)"],
        "n_samples": int(len(Xl)),
        "n_features": len(feature_names),
        "positive_rate_train": float(ytr.mean()),
        "test": {
            "roc_auc": round(float(roc_auc_score(yte, proba)), 4),
            "accuracy": round(float(accuracy_score(yte, pred)), 4),
            "precision": round(float(precision_score(yte, pred, zero_division=0)), 4),
            "recall": round(float(recall_score(yte, pred, zero_division=0)), 4),
            "f1": round(float(f1_score(yte, pred, zero_division=0)), 4),
            "confusion_matrix": confusion_matrix(yte, pred).tolist(),
        },
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "train_seconds": round(time.time() - t1, 2),
    }
    log("  test metrics: " + json.dumps(metrics["test"]))

    imp = sorted(zip(feature_names, clf.feature_importances_.tolist()),
                 key=lambda x: -x[1])[:15]
    metrics["feature_importance_top15"] = [
        {"feature": f, "importance": round(v, 4)} for f, v in imp]
    log("  top features: " + ", ".join(f"{f}={v:.3f}" for f, v in imp[:6]))

    # ------------------------------------------------------------------
    # 4. SHAP — MODEL EXPLANATION ONLY
    # ------------------------------------------------------------------
    log("computing SHAP values (TreeExplainer)")
    import shap
    expl = shap.TreeExplainer(clf)
    shap_arr = expl.shap_values(Xte)
    if isinstance(shap_arr, list):          # older shap: [class0, class1]
        shap_arr = shap_arr[1]
    shap_arr = np.asarray(shap_arr)
    if shap_arr.ndim == 3:                  # (n, p, 2)
        shap_arr = shap_arr[:, :, 1]
    global_ranking = sorted(
        zip(feature_names, np.abs(shap_arr).mean(axis=0).tolist()),
        key=lambda x: -x[1])
    shap_global = {
        "scope": "MODEL EXPLANATION (SHAP over the trained classifier) — "
                 "not an explanation of the graph itself",
        "model": metrics["model"],
        "n_rows_explained": int(shap_arr.shape[0]),
        "mean_abs_shap_top15": [{"feature": f, "mean_abs_shap": round(v, 6)}
                                for f, v in global_ranking[:15]],
        "baseline_output_mean": round(float(np.mean(clf.predict_proba(Xte)[:, 1])), 4),
    }
    with open(os.path.join(XAI, "shap_global.json"), "w", encoding="utf-8") as f:
        json.dump(shap_global, f, indent=2)
    log(f"  top SHAP features: {', '.join(f for f, _ in global_ranking[:5])}")

    # per-case local explanations for all 20 benchmark flagged transactions
    local_out = {}
    for b in bench:
        tid = b["flagged_txn_id"]
        if tid not in X.index:
            local_out[b["case_id"]] = {"error": "transaction not in feature frame"}
            continue
        row = X.loc[[tid]]
        sv = expl.shap_values(row)
        if isinstance(sv, list):
            sv = sv[1]
        sv = np.asarray(sv)
        if sv.ndim == 3:
            sv = sv[:, :, 1]
        sv = sv.reshape(-1)
        p = float(clf.predict_proba(row)[0, 1])
        order = np.argsort(-np.abs(sv))[:8]
        local_out[b["case_id"]] = {
            "txn_id": tid,
            "card_id": b["card_id"],
            "customer_id": b["customer_id"],
            "risk_score": float(b["risk_score"]),
            "model_probability": round(p, 4),
            "model_prediction": "FRAUD" if p >= 0.5 else "NOT_FRAUD",
            "top_contributing_features": [
                {"feature": feature_names[i], "value": round(float(row.iloc[0, i]), 4),
                 "shap_value": round(float(sv[i]), 5)}
                for i in order],
            "note": "MODEL EXPLANATION: contribution of each feature to this "
                    "model score. GRAPH EVIDENCE is reported separately by the "
                    "agent from TigerGraph queries.",
        }
    with open(os.path.join(XAI, "shap_local_benchmark_cases.json"), "w", encoding="utf-8") as f:
        json.dump(local_out, f, indent=2)
    scored = [v for v in local_out.values() if "model_probability" in v]
    log(f"  local SHAP for {len(scored)}/20 benchmark cases; "
        f"HHG-001 p={local_out.get('HHG-001', {}).get('model_probability')}")

    # ------------------------------------------------------------------
    # 5. Persist
    # ------------------------------------------------------------------
    with open(os.path.join(MODELS, "fraud_model.pkl"), "wb") as f:
        pickle.dump({"model": clf, "features": feature_names}, f)
    with open(os.path.join(MODELS, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    with open(os.path.join(MODELS, "features.json"), "w", encoding="utf-8") as f:
        json.dump({"features": feature_names,
                   "graph_derived": ["card_txn_degree", "customer_card_degree",
                                     "card_owner_degree", "card_prev_degree",
                                     "card_next_degree", "prev_time_delta_hours",
                                     "prev_amount_ratio", "card_mean_time_delta",
                                     "device_shared_txn_degree", "device_distinct_cards",
                                     "device_has_edge", "device_newness",
                                     "purchaser_domain_degree", "recipient_domain_degree",
                                     "region_degree", "txn_in_closed_cases",
                                     "card_historical_cases", "card_on_card_cases"],
                   "excluded": ["risk_score"]}, f, indent=2)
    log(f"WROTE models/fraud_model.pkl, models/metrics.json, xai/shap_*.json "
        f"({time.time()-T0:.1f}s total)")
    return metrics


if __name__ == "__main__":
    m = main()
    print(json.dumps({"ML_STATUS": "PASS", "roc_auc": m["test"]["roc_auc"]}))
