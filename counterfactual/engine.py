"""Counterfactual engine (Phase 4) — what would have to change.

Answers "what would have to change?" with REAL computations only:

  1. MODEL counterfactuals   — the flagged transaction's feature vector is
     perturbed and re-scored by the trained model (models/fraud_model.pkl).
     The baseline score is checked against the value already recorded in the
     case file, so a mismatch is reported instead of hidden.
  2. POLICY counterfactuals  — policies/rules.py is re-evaluated with modified
     facts (fewer graph facts, lower probability) to show exactly which gate
     flips a recommendation from allowed to denied.

Nothing here writes to the graph, the case files or the model. Every number is
produced by executing code in this repository; no value is invented.

Run:  python scripts/build_counterfactual.py        (all 20 cases -> JSON)
Out:  counterfactual/results.json
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ml.train as mltrain  # noqa: E402  (feature builder — same code as training)


class _CachedPandas:
    """`pandas` proxy that memoizes `read_csv`.

    graph_features() re-reads ~90 MB of edge CSVs on every call. The edge files
    are locked (Phase 2, never reloaded), pandas 3 copy-on-write makes shallow
    copies isolated, and every call site is read-only — so a cache is safe and
    turns a 50 s case analysis into a sub-second one after warm-up. All other
    pandas attributes are delegated unchanged.
    """

    def __init__(self, real):
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_cache", {})

    def read_csv(self, path, *args, **kwargs):
        cache = object.__getattribute__(self, "_cache")
        key = (str(path), repr(args), repr(sorted(kwargs.items())))
        frame = cache.get(key)
        if frame is None:
            frame = object.__getattribute__(self, "_real").read_csv(path, *args, **kwargs)
            cache[key] = frame
        return frame.copy(deep=False)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_real"), name)


mltrain.pd = _CachedPandas(pd)

# Decision thresholds, identical to scripts/build_cases.py (Section 6).
P_FRAUD = 0.70
P_LEGIT = 0.30

TXCOLS = ["txn_id", "customer_id", "card_id", "card1_num", "ts", "dt_seconds",
          "amount", "product_cd", "channel", "risk_score", "addr1", "addr2",
          "dist1", "dist2", "p_emaildomain", "r_emaildomain"]

# Graph-derived features grouped by the evidence they represent, so a scenario
# asks a question an analyst would actually ask ("what if the device linkage
# were not there?").
GRAPH_FEATURES = [
    "card_txn_degree", "customer_card_degree", "card_owner_degree",
    "card_prev_degree", "card_next_degree", "prev_time_delta_hours",
    "prev_amount_ratio", "card_mean_time_delta", "device_shared_txn_degree",
    "device_distinct_cards", "device_has_edge", "device_newness",
    "purchaser_domain_degree", "recipient_domain_degree", "region_degree",
    "txn_in_closed_cases", "card_historical_cases", "card_on_card_cases",
]

SCENARIOS: List[Dict[str, Any]] = [
    {"id": "graph_structure_removed",
     "question": "What would the score be if the graph contributed no structure at all?",
     "features": GRAPH_FEATURES, "to": 0.0},
    {"id": "historical_linkage_removed",
     "question": "What if this transaction had no prior closed-case linkage?",
     "features": ["txn_in_closed_cases", "card_historical_cases",
                  "card_on_card_cases"], "to": 0.0},
    {"id": "device_linkage_removed",
     "question": "What if no device profile were shared with other cards?",
     "features": ["device_shared_txn_degree", "device_distinct_cards",
                  "device_has_edge"], "to": 0.0},
    {"id": "burst_removed",
     "question": "What if the card showed no transaction burst on this day?",
     "features": ["card_txn_degree", "card_prev_degree", "card_next_degree"],
     "to": 0.0},
    {"id": "region_signal_removed",
     "question": "What if the billing region carried no history?",
     "features": ["region_degree"], "to": 0.0},
]

# Cached, immutable-once-loaded process state.
_CACHE: Dict[str, Any] = {}


def _load() -> Dict[str, Any]:
    if _CACHE:
        return _CACHE
    t0 = time.time()
    with open(os.path.join(ROOT, "models", "fraud_model.pkl"), "rb") as fh:
        bundle = pickle.load(fh)
    # Score single-threaded *in this process only* (the pickle on disk is never
    # touched): every predict_proba() call would otherwise spin up and tear down
    # a joblib process pool, which dominates the runtime of a sweep. Results are
    # identical — RandomForest probability is deterministic regardless of n_jobs.
    try:
        bundle["model"].set_params(n_jobs=1)
    except Exception:
        pass
    _CACHE["model"] = bundle["model"]
    _CACHE["features"] = list(bundle["features"])

    tx = pd.read_csv(os.path.join(ROOT, "data", "vertices", "transaction.csv"),
                     usecols=TXCOLS, dtype=str)
    tx["amount_f"] = pd.to_numeric(tx["amount"], errors="coerce")
    _CACHE["tx"] = tx.set_index("txn_id", drop=False)
    _CACHE["load_s"] = round(time.time() - t0, 2)
    return _CACHE


def _model_features(txn_ids: List[str]) -> pd.DataFrame:
    """Feature frame for the given transactions — byte-for-byte the same
    pipeline used by ml/train.py and scripts/build_cases.py."""
    st = _load()
    tx_by_id = st["tx"]
    rows = [t for t in txn_ids if t in tx_by_id.index]
    if not rows:
        raise ValueError("no transaction ids resolve in data/vertices/transaction.csv: %r"
                         % (txn_ids,))
    sub = tx_by_id.loc[rows][TXCOLS].copy()
    F = mltrain.graph_features(sub)
    A = mltrain.transaction_attrs(sub)
    X = pd.concat([A, F.drop(columns=["txn_id", "card_id", "customer_id"])], axis=1)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)[st["features"]]
    return X


def _score(X: pd.DataFrame) -> np.ndarray:
    return _load()["model"].predict_proba(X)[:, 1]


def threshold_verdict(p: float) -> str:
    """Threshold-only verdict (Section 6). Corroboration rules in the full
    builder are NOT applied here — this is deliberately labelled 'threshold'."""
    if p >= P_FRAUD:
        return "fraud"
    if p <= P_LEGIT:
        return "legitimate"
    return "uncertain"


def _shap_top(X: pd.DataFrame, k: int = 6) -> List[Tuple[str, float]]:
    """Top-k |SHAP| features for the single row in X (real explainer)."""
    try:
        import shap
    except Exception:
        return []
    try:
        expl = shap.TreeExplainer(_load()["model"])
        sv = expl.shap_values(X)
        if isinstance(sv, list):
            sv = sv[1]
        sv = np.asarray(sv)
        if sv.ndim == 3:
            sv = sv[:, :, 1]
        row = sv[0]
    except Exception:
        return []
    feats = _load()["features"]
    order = np.argsort(-np.abs(row))[:k]
    return [(feats[i], round(float(row[i]), 5)) for i in order]


# ---------------------------------------------------------------------------
# policy counterfactuals — real calls into policies/rules.py
# ---------------------------------------------------------------------------
def policy_counterfactuals(facts: Dict[str, Any],
                           variants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Evaluate the same candidate action under baseline and modified facts."""
    sys.path.insert(0, ROOT)
    from policies import rules  # noqa: PLC0415

    candidates = list(rules.ACTIONS)
    out: List[Dict[str, Any]] = []
    for variant in variants:
        vname = variant["name"]
        vfacts = dict(facts)
        vfacts.update(variant.get("facts", {}))
        rows = []
        for action in candidates:
            base_ok, base_why = rules.validate(action, facts)
            ok, why = rules.validate(action, vfacts)
            rows.append({
                "action": action,
                "baseline_allowed": base_ok, "baseline_reason": base_why,
                "variant_allowed": ok, "variant_reason": why,
                "changed": base_ok != ok,
            })
        out.append({
            "variant": vname,
            "description": variant["description"],
            "facts_used": {k: vfacts.get(k) for k in
                           ("risk_probability", "graph_evidence_count",
                            "historical_case_count", "uncertainty")},
            "results": rows,
            "changed_count": sum(1 for r in rows if r["changed"]),
        })
    return out


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------
def model_analysis(txn_ids: List[str], *, primary_hint: str = "",
                   recorded_model_p: Optional[float] = None,
                   recorded_model_txn: str = "") -> Dict[str, Any]:
    """Model-level counterfactuals for a set of transactions (case-file free).

    Used both by analyse() (which supplies the recorded model score from the
    case evidence) and by the LangGraph agent (which supplies only transaction
    ids from its own graph investigation). Baseline + every scenario are scored
    in ONE predict_proba call.
    """
    t0 = time.time()
    try:
        X = _model_features(txn_ids)
    except Exception as exc:
        return {"status": "FEATURE_ERROR", "detail": str(exc)}

    # Primary row: the transaction the recorded model score belongs to,
    # otherwise the hinted (flagged) transaction — never an average over the set.
    order = list(X.index)
    primary = 0
    for candidate in (recorded_model_txn, primary_hint):
        if candidate and candidate in order:
            primary = order.index(candidate)
            break
    P = X.iloc[[primary]]
    primary_txn = str(order[primary])

    # ---- build every counterfactual row, score them in ONE model call ----
    # (predict_proba is deterministic; batching avoids per-call pool spin-up)
    rows: List[pd.DataFrame] = []
    slots: Dict[str, int] = {}

    def _slot(name: str, frame: pd.DataFrame) -> None:
        slots[name] = len(rows)
        rows.append(frame)

    _slot("baseline", P)

    # ---- model scenarios -------------------------------------------------
    scen_rows = []
    for i, sc in enumerate(SCENARIOS):
        Xc = P.copy()
        for f in sc["features"]:
            if f in Xc.columns:
                Xc[f] = sc["to"]
        scen_rows.append((sc, Xc))
        _slot("scen:%d" % i, Xc)

    # ---- minimal single-feature change to a decision boundary ------------
    top = _shap_top(P, k=6)
    st = _load()
    feat_rows = []  # (feature, shap, current, value, row_index, frame)
    for feat, contrib in top:
        if feat not in P.columns:
            continue
        cur = float(P.iloc[0][feat])
        lo, hi = (0.0, max(1.0, abs(cur) * 4))
        for val in np.linspace(lo, hi, 41):
            Xc = P.copy()
            Xc[feat] = val
            feat_rows.append((feat, contrib, cur, float(val), len(rows), Xc))
            rows.append(Xc)

    big = pd.concat(rows, axis=0)
    probs = _score(big)

    baseline_p = float(probs[slots["baseline"]])
    scenarios = []
    for i, (sc, Xc) in enumerate(scen_rows):
        p = float(probs[slots["scen:%d" % i]])
        scenarios.append({
            "id": sc["id"],
            "question": sc["question"],
            "features_changed": [f for f in sc["features"] if f in X.columns],
            "probability": round(p, 4),
            "delta": round(p - baseline_p, 4),
            "threshold_verdict": threshold_verdict(p),
            "flips_threshold": threshold_verdict(p) != threshold_verdict(baseline_p),
        })

    # group the sweep results per feature (first crossing wins)
    boundary = P_FRAUD if baseline_p >= P_FRAUD else P_LEGIT
    direction = "below" if boundary == P_FRAUD else "above"
    per_feat: Dict[str, Dict[str, Any]] = {}
    for feat, contrib, cur, val, idx, _frame in feat_rows:
        p = float(probs[idx])
        crosses = (p < boundary) if boundary == P_FRAUD else (p > boundary)
        d = per_feat.setdefault(feat, {
            "feature": feat, "shap_value": contrib,
            "current_value": round(cur, 4), "boundary": boundary,
            "direction": direction, "crosses_on_grid": False,
            "nearest_value": None, "probability_at_nearest": None,
            "observed_range_note": "grid spans [0, %.2f]; every point re-scored"
                                   % max(1.0, abs(cur) * 4),
        })
        if crosses and not d["crosses_on_grid"]:
            d["crosses_on_grid"] = True
            d["nearest_value"] = round(val, 4)
            d["probability_at_nearest"] = round(p, 4)

    return {
        "status": "OK",
        "transaction_ids": txn_ids,
        "primary_transaction_id": primary_txn,
        "baseline": {
            "probability": round(baseline_p, 4),
            "threshold_verdict": threshold_verdict(baseline_p),
            "recorded_model_probability": recorded_model_p,
            "recorded_model_txn": recorded_model_txn,
            "matches_recorded_model": (
                None if recorded_model_p is None
                else abs(round(baseline_p, 4) - recorded_model_p) <= 0.0005),
            "note": ("recorded_model_probability is the raw model score in "
                     "the case evidence (the match target); the calibrated "
                     "decision probability from Section 6 is a different "
                     "quantity and is never used as the match target."),
        },
        "model_scenarios": scenarios,
        "feature_counterfactuals": list(per_feat.values()),
        "model": st["model"].__class__.__name__,
        "n_features": len(st["features"]),
        "elapsed_s": round(time.time() - t0, 2),
        "_features": X,
    }


def analyse(case_id: str) -> Dict[str, Any]:
    """Full counterfactual analysis for one case file (read-only)."""
    t0 = time.time()
    case_path = os.path.join(ROOT, "cases", "%s.json" % case_id)
    if not os.path.exists(case_path):
        return {"case_id": case_id, "status": "NOT_FOUND",
                "detail": "cases/%s.json does not exist" % case_id}
    with open(case_path, encoding="utf-8") as fh:
        case = json.load(fh)

    # resolve the transaction(s) the case is about
    affected = list(case["case"].get("affected_txn_ids") or [])
    flagged = case["case"].get("first_suspicious_txn_id") or ""
    entities = (case.get("graph_evidence") or {}).get("entities") or {}
    graph_txns = [str(t) for t in (entities.get("Transaction") or [])]

    # The case's *recorded model score* (evidence item "Model score for
    # transaction ... is X.XXXX") names the transaction it was computed on —
    # in multi-transaction cases that is not necessarily first_suspicious_txn_id.
    # It is the apples-to-apples match target for the raw model output; the
    # calibrated decision probability (pre/post) is a different quantity built
    # by scripts/build_cases.py Section 6 and is never used as the match target.
    import re as _re
    recorded_model_p = None
    recorded_model_txn = ""
    for _ev in case["case"].get("evidence", []):
        m = _re.search(r"Model score for transaction (\S+) is ([0-9.]+)",
                       str(_ev.get("claim", "")))
        if m:
            recorded_model_txn, recorded_model_p = m.group(1), float(m.group(2))
            break

    txn_ids = affected or ([flagged] if flagged else []) or graph_txns[:1]
    # include the recorded model-score transaction so the comparison is exact
    if recorded_model_txn and recorded_model_txn not in txn_ids:
        txn_ids = txn_ids + [recorded_model_txn]
    if not txn_ids:
        return {"case_id": case_id, "status": "NO_TRANSACTION",
                "detail": "case file names no transaction to analyse",
                "computed_at": _now()}

    ma = model_analysis(txn_ids,
                        primary_hint=(recorded_model_txn or flagged),
                        recorded_model_p=recorded_model_p,
                        recorded_model_txn=recorded_model_txn)
    if ma.get("status") != "OK":
        return {"case_id": case_id, "status": ma["status"],
                "detail": ma.get("detail"), "computed_at": _now()}
    baseline_p = ma["baseline"]["probability"]
    scenarios = ma["model_scenarios"]
    feature_counterfactuals = ma["feature_counterfactuals"]
    primary_txn = ma["primary_transaction_id"]
    st = _load()
    X = ma.pop("_features")

    pre_p = ((case.get("pre_additional_evidence_state") or {})
             .get("preliminary_decision") or {}).get("fraud_probability")
    post_p = case["case"].get("fraud_probability")
    recorded_model_p = ma["baseline"].get("recorded_model_probability")
    recorded_model_txn = ma["baseline"].get("recorded_model_txn")

    # ---- policy counterfactuals -----------------------------------------
    graph_items = [e for e in case["case"].get("evidence", [])
                   if e.get("evidence_class") == "derived_graph"]
    hist_n = len(case["case"].get("similar_prior_cases") or [])
    facts = {
        "risk_probability": float(post_p if post_p is not None else baseline_p),
        "graph_evidence_count": len(graph_items),
        "historical_case_count": hist_n,
        "uncertainty": "INSUFFICIENT" if case.get("evidence_requests") else "SUFFICIENT",
    }
    variants = [
        {"name": "one_graph_fact_removed",
         "description": "Drop one derived-graph fact from the evidence set.",
         "facts": {"graph_evidence_count": max(0, len(graph_items) - 1)}},
        {"name": "no_graph_evidence",
         "description": "The graph query returned nothing for this case.",
         "facts": {"graph_evidence_count": 0}},
        {"name": "no_historical_linkage",
         "description": "No closed case in history links to these entities.",
         "facts": {"historical_case_count": 0}},
        {"name": "probability_below_escalation",
         "description": "The model scored the transaction below 0.75.",
         "facts": {"risk_probability": round(min(0.74, float(post_p or 0.0)), 4)}},
        {"name": "evidence_insufficient",
         "description": "Evidence sufficiency is INSUFFICIENT at decision time.",
         "facts": {"uncertainty": "INSUFFICIENT"}},
    ]
    try:
        policy = policy_counterfactuals(facts, variants)
    except Exception as exc:
        policy = [{"error": "policy evaluation failed: %s" % exc}]

    return {
        "case_id": case_id,
        "status": "OK",
        "computed_at": _now(),
        "engine": "counterfactual/engine.py",
        "model": st["model"].__class__.__name__,
        "n_features": len(st["features"]),
        "thresholds": {"fraud": P_FRAUD, "legitimate": P_LEGIT,
                       "rule": "Section 6 threshold-only verdict"},
        "transaction_ids": txn_ids,
        "primary_transaction_id": primary_txn,
        "baseline": {
            "probability": round(baseline_p, 4),
            "threshold_verdict": threshold_verdict(baseline_p),
            "recorded_model_probability": recorded_model_p,
            "recorded_model_txn": recorded_model_txn,
            "matches_recorded_model": (
                None if recorded_model_p is None
                else abs(round(baseline_p, 4) - recorded_model_p) <= 0.0005),
            "recorded_pre_probability": pre_p,
            "recorded_post_probability": post_p,
            "note": ("recorded_model_probability is the raw model score in the "
                     "case evidence (the match target); recorded_pre/post are "
                     "the calibrated decision probability from Section 6, a "
                     "different quantity."),
        },
        "model_scenarios": scenarios,
        "feature_counterfactuals": feature_counterfactuals,
        "policy_facts": facts,
        "policy_counterfactuals": policy,
        "disclaimer": ("Model counterfactuals re-score the recorded feature "
                       "vector; policy counterfactuals re-run "
                       "policies/rules.py. Neither writes to the graph."),
        "elapsed_s": round(time.time() - t0, 2),
    }


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    cid = sys.argv[1] if len(sys.argv) > 1 else "HHG-001"
    print(json.dumps(analyse(cid), indent=2))
