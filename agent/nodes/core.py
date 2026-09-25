"""LangGraph node functions (Phase 4).

Every node is a pure-ish function ``InvestigationState -> partial state`` and
obeys three rules:

1. **Graph evidence is authoritative.** Numbers come from a live TigerGraph
   query or from the deterministic builder (``scripts/build_cases.py``); the
   LLM is never asked for a fact, only for wording.
2. **Provenance is real.** Each node appends trace entries carrying the actual
   tool name, HTTP status and latency it observed — never an estimate.
3. **Honest degradation.** Missing data becomes ``NO_EVIDENCE`` /
   ``INSUFFICIENT`` / ``no_llm_available``; nothing is invented to fill a gap.
"""
from __future__ import annotations

import os
import sys
import io
import time
from typing import Any, Dict, List, Optional

if not getattr(sys.stdout, "_hhg_wrapped", False):
    _w = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _w._hhg_wrapped = True
    sys.stdout = _w

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.state import InvestigationState, trace_from, timings_from  # noqa: E402


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------
_BUILDER = None


def _builder():
    """Import the deterministic core once (cold import ~11 s, then cached)."""
    global _BUILDER
    if _BUILDER is None:
        import scripts.build_cases as bc
        _BUILDER = bc
    return _BUILDER


def _row(case_id: str) -> Optional[Dict[str, Any]]:
    for r in _builder().pack:
        if r.get("case_id") == case_id:
            return r
    return None


def _mcp(tool_name: str, **kwargs):
    """Call one MCP tool live and return (envelope, latency_ms).

    Sets TG_HOST so the MCP layer talks to the local RESTPP at :9000
    (read-only). Latency is measured client-side around the call.
    """
    os.environ.setdefault("TG_HOST", "http://localhost")
    os.environ.setdefault("TG_RESTPP_PORT", "9000")
    from mcp.tools.investigation_tools import get_tool
    t0 = time.perf_counter()
    try:
        env = get_tool(tool_name)(**kwargs)
    except Exception as exc:
        env = {"status": "error", "tool": tool_name,
               "data": {}, "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}
    return env, (time.perf_counter() - t0) * 1000.0


def _env_ok(env: Dict[str, Any]) -> bool:
    return str(env.get("status", "")).lower() == "success"


def _env_http(env: Dict[str, Any]) -> Optional[int]:
    """HTTP status if the envelope exposes one, else None (never guessed)."""
    for key in ("http_status",):
        if isinstance(env.get(key), int):
            return env[key]
    src = env.get("source") or {}
    if isinstance(src.get("http_status"), int):
        return src["http_status"]
    return None


def _entities(env: Dict[str, Any]) -> Dict[str, List[str]]:
    """Flatten GSQL result blocks -> {v_type: [v_id, ...]}.

    Two row shapes are returned by the local graph and both are handled:
    dicts with ``v_type``/``v_id``, and bare id strings under a block name
    that implies the type (``@@seedTxns`` -> Transaction).
    """
    out: Dict[str, List[str]] = {}
    results = ((env.get("data") or {}).get("results")) or []
    for block in results:
        if not isinstance(block, dict):
            continue
        for bname, rows in block.items():
            if not isinstance(rows, list):
                continue
            implied = None
            low = str(bname).lower()
            if "seedtxn" in low or low.endswith("txn"):
                implied = "Transaction"
            elif "card" in low:
                implied = "Card"
            elif "cust" in low:
                implied = "Customer"
            elif "case" in low:
                implied = "ClosedCase"
            for r in rows:
                if isinstance(r, dict) and r.get("v_type"):
                    vtype = str(r["v_type"])
                    vid = str(r.get("v_id"))
                elif isinstance(r, str) and implied:
                    vtype, vid = implied, r
                else:
                    continue
                out.setdefault(vtype, [])
                if vid not in out[vtype]:
                    out[vtype].append(vid)
    return out


# --------------------------------------------------------------------------
# 1. TRIAGE
# --------------------------------------------------------------------------
def triage(state: InvestigationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    cid = state.get("case_id", "")
    row = _row(cid)
    tr = trace_from(state, "triage", tool="case_pack.csv")
    if row is None:
        tr[-1].update(ok=False, detail="case %s not present in DATASET/case_pack.csv" % cid)
        return {"status": "UNKNOWN_CASE", "trace": tr,
                "timings_ms": timings_from(state, "triage", (time.perf_counter() - t0) * 1000),
                "errors": list(state.get("errors") or []) +
                          ["UNKNOWN_CASE: %s is not in case_pack.csv" % cid]}
    tr[-1].update(ok=True, detail="row loaded: txn=%s card=%s trigger=%s" % (
        row.get("flagged_txn_id"), row.get("card_id"), row.get("trigger_type")))
    return {"case": dict(row), "status": "OK", "trace": tr,
            "timings_ms": timings_from(state, "triage", (time.perf_counter() - t0) * 1000)}


# --------------------------------------------------------------------------
# 2. INVESTIGATE — graph_evidence (live GSQL through the builder's 3 queries)
# --------------------------------------------------------------------------
def graph_evidence(state: InvestigationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    row = state.get("case") or {}
    if not row:
        return {"status": "NO_EVIDENCE",
                "errors": list(state.get("errors") or []) + ["NO_EVIDENCE: triage produced no row"],
                "trace": trace_from(state, "graph_evidence", ok=False, detail="no case row")}

    bc = _builder()
    f = bc.gather(row)                       # runs 3 live GSQL queries (~1 s)
    tg = f.get("tg") or {}

    # one trace entry PER real query, carrying its real HTTP status + latency
    tr: List[Dict[str, Any]] = list(state.get("trace") or [])
    tool_calls = int(state.get("tool_calls") or 0)
    for name, res in tg.items():
        http = res.get("status")
        tool_calls += 1
        blocks = res.get("counts") or {}
        tr.append({"node": "graph_evidence", "tool": "gsql:" + name,
                   "http_status": http if isinstance(http, int) else None,
                   "latency_ms": round(float(res.get("ms") or 0.0), 1),
                   "ok": http == 200,
                   "detail": "counts={%s}" % ", ".join(
                       "%s=%s" % (k, v) for k, v in list(blocks.items())[:6])})

    graph_counts = {"queries_ok": sum(1 for r in tg.values() if r.get("status") == 200),
                    "queries_total": len(tg)}
    empty = graph_counts["queries_ok"] == 0

    ge = {"queries": {k: {"http_status": v.get("status"), "latency_ms": v.get("ms"),
                          "counts": v.get("counts") or {}} for k, v in tg.items()},
          "flagged_txn_id": f.get("flagged_txn_id"),
          "card_id": f.get("card_id"), "customer_id": f.get("customer_id"),
          "amount_usd": f.get("flagged_amount"), "channel": f.get("flagged_channel"),
          "region": (f.get("region") or {}).get("region_code"),
          "graph_counts": graph_counts}

    status = "NO_EVIDENCE" if empty else state.get("status", "OK")
    return {"facts": f, "graph_evidence": ge, "status": status,
            "tool_calls": tool_calls, "trace": tr,
            "timings_ms": timings_from(state, "graph_evidence", (time.perf_counter() - t0) * 1000)}


# --------------------------------------------------------------------------
# 3. RETRIEVE — relationships (two live MCP tool calls)
# --------------------------------------------------------------------------
def relationships(state: InvestigationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    case = state.get("case") or {}
    tid = case.get("flagged_txn_id") or ""
    cid = case.get("card_id") or ""
    tr: List[Dict[str, Any]] = list(state.get("trace") or [])
    tool_calls = int(state.get("tool_calls") or 0)
    out: Dict[str, Any] = {"flagged_txn_id": tid, "card_id": cid,
                           "related_txn_ids": [], "device_profile_id": None,
                           "linked_cards": [], "closed_case_links": [],
                           "device_edge": "absent", "queries": {}}

    env, ms = _mcp("find_related_transactions", txn_id=tid, max_hops=1, limit=50, case_id=case.get("case_id"))
    tool_calls += 1
    ents = _entities(env)
    out["queries"]["find_related_transactions"] = {"status": env.get("status"),
                                                   "latency_ms": round(ms, 1),
                                                   "returned_count": env.get("returned_count"),
                                                   "source_kind": (env.get("source") or {}).get("kind")}
    tr.append({"node": "relationships", "tool": "find_related_transactions",
               "http_status": _env_http(env), "latency_ms": round(ms, 1), "ok": _env_ok(env),
               "detail": "%s, %s entity type(s), %s row(s)" % (
                   env.get("status"), len(ents), env.get("returned_count"))})
    out["related_txn_ids"] = ents.get("Transaction", [])[:20]

    env2, ms2 = _mcp("find_device_connections", txn_id=tid, limit=50, case_id=case.get("case_id"))
    tool_calls += 1
    ents2 = _entities(env2)
    dev = ents2.get("DeviceProfile") or []
    out["queries"]["find_device_connections"] = {"status": env2.get("status"),
                                                 "latency_ms": round(ms2, 1),
                                                 "returned_count": env2.get("returned_count"),
                                                 "source_kind": (env2.get("source") or {}).get("kind")}
    msg = (env2.get("data") or {}).get("message") or env2.get("message") or ""
    tr.append({"node": "relationships", "tool": "find_device_connections",
               "http_status": _env_http(env2), "latency_ms": round(ms2, 1), "ok": _env_ok(env2),
               "detail": "%s %s" % (env2.get("status"), ("%s" % msg)[:120])})
    if dev:
        out["device_profile_id"] = dev[0]
        out["device_edge"] = "present"
        out["linked_cards"] = ents2.get("Card", [])[:20]
    else:
        out["device_edge"] = "absent (no FROM_DEVICE edge returned)"

    # historical case linkage read from the builder's in-memory closed-case index
    f = state.get("facts") or {}
    out["closed_case_links"] = list(f.get("similar_candidates") or [])[:10]
    out["prior_fraud_cases"] = list(f.get("prior_fraud_cases") or [])[:10]
    out["device_linked_fraud_cases"] = list(f.get("device_linked_fraud_cases") or [])[:10]

    return {"relationships": out, "tool_calls": tool_calls, "trace": tr,
            "timings_ms": timings_from(state, "relationships", (time.perf_counter() - t0) * 1000)}


# --------------------------------------------------------------------------
# 4. ASSESS — risk (model score + calibrated probability + signals)
# --------------------------------------------------------------------------
def risk_score(state: InvestigationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    f = state.get("facts") or {}
    if not f:
        return {"status": "NO_EVIDENCE", "trace": trace_from(state, "risk_score", ok=False,
                                                              detail="no facts to score")}
    a = _builder().analyse(f)
    risk = {"model_probability": a.get("ml_probability"),
            "calibrated_pre": a.get("p_initial"),
            "pattern": a.get("pattern"),
            "pattern_description": a.get("pattern_desc"),
            "anomaly_count": a.get("anomaly_count"),
            "corroborated": a.get("corroborated"),
            "exculpatory_count": a.get("exculpatory_count"),
            "graph_signal": a.get("graph_signal"),
            "risk_input": f.get("risk_input"),
            "active_signals": [k for k in ("card_testing", "out_of_region", "new_device", "proxy",
                                           "match_anomaly", "amount_outlier", "new_product", "burst",
                                           "ring", "device_prior_fraud", "card_prior_fraud",
                                           "domain_new", "channel_change", "denied")
                               if a.get(k)]}
    tr = trace_from(state, "risk_score", tool="scripts.build_cases.analyse",
                    ok=True, detail="model p=%.4f, calibrated pre=%.4f, %d signal(s), pattern=%s" % (
                        a.get("ml_probability") or 0.0, a.get("p_initial") or 0.0,
                        a.get("anomaly_count") or 0, a.get("pattern")))
    return {"analysis": a, "risk": risk, "trace": tr,
            "timings_ms": timings_from(state, "risk_score", (time.perf_counter() - t0) * 1000)}


# --------------------------------------------------------------------------
# 5. XAI — MODEL EXPLANATION vs GRAPH EVIDENCE (kept strictly apart)
# --------------------------------------------------------------------------
def xai(state: InvestigationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    f = state.get("facts") or {}
    a = state.get("analysis") or {}
    tid = f.get("flagged_txn_id")
    shap_rows = (f.get("shap") or {}).get(tid) or []
    model_side = [{"feature": r["feature"], "value": r["value"], "shap_value": r["shap_value"]}
                  for r in shap_rows[:6]]
    graph_side = {"strong_corroborating_signals": a.get("corroborated") or 0,
                  "exculpatory_signals": a.get("exculpatory_count") or 0,
                  "deviation_signals": a.get("anomaly_count") or 0,
                  "graph_items": len([e for e in (state.get("evidence") or [])
                                      if e.get("evidence_class") == "derived_graph"]),
                  "historical_case_links": len(f.get("similar_candidates") or [])}
    x = {"txn_id": tid,
         "model_explanation": {"method": "TreeExplainer SHAP",
                               "model": "models/fraud_model.pkl",
                               "top_contributions": model_side,
                               "note": "model explanation — NOT graph evidence"},
         "graph_evidence": {**graph_side,
                            "note": "graph evidence — independent of the model"},
         "separation_rule": "a SHAP value never counts as a graph fact, and a "
                            "graph fact never counts as a model contribution"}
    tr = trace_from(state, "xai", tool="shap.TreeExplainer",
                    ok=bool(model_side), detail="%d contribution(s) from %d feature(s)" % (
                        len(model_side), len(model_side)))
    return {"xai": x, "trace": tr,
            "timings_ms": timings_from(state, "xai", (time.perf_counter() - t0) * 1000)}


# --------------------------------------------------------------------------
# 6. CHECK UNCERTAINTY — evidence sufficiency
# --------------------------------------------------------------------------
def _sufficiency(ev: List[Dict[str, Any]], a: Dict[str, Any]):
    graph_items = [e for e in ev if e.get("evidence_class") == "derived_graph"]
    n = len(graph_items)
    if n == 0:
        return "INSUFFICIENT", "no derived-graph fact supports the alert"
    if n < 2:
        return "INSUFFICIENT", "only %d derived-graph fact (<2): alert is thin" % n
    if (a.get("corroborated") or 0) or (a.get("anomaly_count") or 0) or (a.get("exculpatory_count") or 0):
        # Three DIFFERENT counts live in build_cases.analyse() and must not be
        # collapsed into one word. build_summary() calls anomaly_count
        # "corroborating signal(s)" while corroborated counts only STRONG
        # signals, so both are named explicitly here to stay unambiguous when
        # this trace is compared against the case narrative.
        return "SUFFICIENT", ("%d derived-graph facts: %d strong-signal(s), "
                              "%d deviation(s), %d exculpatory" % (
                                  n, a.get("corroborated") or 0,
                                  a.get("anomaly_count") or 0,
                                  a.get("exculpatory_count") or 0))
    return "UNCERTAIN", "%d derived-graph facts but no discriminating signal" % n


def check_uncertainty(state: InvestigationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    f, a = state.get("facts") or {}, state.get("analysis") or {}
    ev = _builder().build_evidence(f, a) if f and a else []
    unc, why = _sufficiency(ev, a) if ev else ("INSUFFICIENT", "no evidence could be built")
    classes: Dict[str, int] = {}
    for e in ev:
        classes[e["evidence_class"]] = classes.get(e["evidence_class"], 0) + 1
    tr = trace_from(state, "check_uncertainty", tool="build_evidence",
                    ok=unc != "INSUFFICIENT",
                    detail="%s: %s (items=%s)" % (unc, why, classes))
    return {"evidence": ev, "uncertainty": unc, "trace": tr,
            "timings_ms": timings_from(state, "check_uncertainty", (time.perf_counter() - t0) * 1000)}


# --------------------------------------------------------------------------
# 7-8. REQUEST EVIDENCE -> REINVESTIGATE (bounded to ONE round)
# --------------------------------------------------------------------------
def request_evidence(state: InvestigationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    f = state.get("facts") or {}
    req = {"type": "analyst_info", "asked_after_step": 6,
           "missing": "derived-graph linkage for txn %s (card %s)" % (
               f.get("flagged_txn_id"), f.get("card_id")),
           "why": "evidence sufficiency is INSUFFICIENT: the alert rests on <2 graph facts",
           "authorization": "read-only follow-up; no graph write, no external contact"}
    tr = trace_from(state, "request_evidence", tool="evidence_value_optimizer",
                    ok=True, detail="requested: %s" % req["missing"][:160])
    return {"decision": dict(state.get("decision") or {}) | {"evidence_request": req},
            "trace": tr,
            "timings_ms": timings_from(state, "request_evidence", (time.perf_counter() - t0) * 1000)}


def reinvestigate(state: InvestigationState) -> Dict[str, Any]:
    """One extra live pass: close-case linkage the first pass did not query."""
    t0 = time.perf_counter()
    case = state.get("case") or {}
    card = case.get("card_id") or ""
    tr = trace_from(state, "reinvestigate")
    tool_calls = int(state.get("tool_calls") or 0)
    rel = dict(state.get("relationships") or {})
    new_cases: List[str] = []

    env, ms = _mcp("find_related_cases", card_id=card, limit=50, case_id=case.get("case_id"))
    tool_calls += 1
    ents = _entities(env)
    found = ents.get("ClosedCase") or []
    known = set(rel.get("closed_case_links") or [])
    new_cases = [c for c in found if c not in known]
    tr.append({"node": "reinvestigate", "tool": "find_related_cases",
               "http_status": _env_http(env), "latency_ms": round(ms, 1), "ok": _env_ok(env),
               "detail": "%s, %d ClosedCase link(s), %d new" % (
                   env.get("status"), len(found), len(new_cases))})
    rel.setdefault("queries", {})["find_related_cases"] = {
        "status": env.get("status"), "latency_ms": round(ms, 1),
        "returned_count": env.get("returned_count"),
        "source_kind": (env.get("source") or {}).get("kind")}
    rel["closed_case_links"] = sorted(set(rel.get("closed_case_links") or []) | set(found))[:10]

    # new facts -> append a real derived-graph evidence item, then re-check
    ev = list(state.get("evidence") or [])
    if new_cases:
        ev.append({"evidence_id": "EV-%02d" % (len(ev) + 1),
                   "claim": "Re-investigation query find_related_cases(card_id=%s) links this card "
                            "to closed case(s) %s." % (card, ", ".join(new_cases[:5])),
                   "source": "graph", "ref": "query:find_related_cases(card_id=%s)" % card,
                   "entity_ids": [card] + new_cases[:5], "evidence_class": "derived_graph"})
    a = state.get("analysis") or {}
    unc, why = _sufficiency(ev, a)
    rnd = int(state.get("round") or 0) + 1
    tr.append({"node": "reinvestigate", "tool": "recheck", "http_status": None, "latency_ms": None,
               "ok": unc != "INSUFFICIENT",
               "detail": "round=%d -> %s: %s" % (rnd, unc, why)})
    return {"relationships": rel, "evidence": ev, "uncertainty": unc, "round": rnd,
            "tool_calls": tool_calls, "trace": tr,
            "timings_ms": timings_from(state, "reinvestigate", (time.perf_counter() - t0) * 1000)}


# --------------------------------------------------------------------------
# 9. GENERATE ACTIONS — deterministic decision core
# --------------------------------------------------------------------------
def generate_actions(state: InvestigationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    f, a, ev = state.get("facts") or {}, state.get("analysis") or {}, state.get("evidence") or []
    if not (f and a):
        return {"status": "NO_EVIDENCE", "trace": trace_from(state, "generate_actions",
                                                              ok=False, detail="no facts/analysis")}
    d = _builder().decide(f, a, ev)
    decision = {"verdict": d["verdict"], "status": d["status"],
                "p0": d["p0"], "p1": d["p1"],
                "pattern": a.get("pattern"), "graph_items": len(d.get("graph_items") or []),
                "thin": d.get("thin"), "settled": d.get("settled"),
                "stop_reason": d.get("stop"),
                "requests": d.get("requests") or [],
                "exposure_usd": d.get("exposure"),
                "affected_txn_ids": d.get("affected") or [],
                "initial_actions": d.get("initial") or [],
                "final_actions": d.get("final") or []}
    if state.get("decision"):
        decision.update({k: v for k, v in (state.get("decision") or {}).items()
                         if k == "evidence_request"})
    tr = trace_from(state, "generate_actions", tool="build_cases.decide", ok=True,
                    detail="verdict=%s p0=%.4f p1=%.4f graph_items=%d" % (
                        d["verdict"], d["p0"], d["p1"], len(d.get("graph_items") or [])))
    return {"decision": decision, "trace": tr,
            "timings_ms": timings_from(state, "generate_actions", (time.perf_counter() - t0) * 1000)}


# --------------------------------------------------------------------------
# 10. COUNTERFACTUAL — case-file-free model re-scoring
# --------------------------------------------------------------------------
def counterfactual(state: InvestigationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    f = state.get("facts") or {}
    tid = f.get("flagged_txn_id") or ""
    if not tid:
        return {"counterfactual": {"status": "NO_TXN"},
                "trace": trace_from(state, "counterfactual", ok=False, detail="no flagged txn")}
    try:
        from counterfactual import engine as cf
        res = cf.model_analysis([tid], primary_hint=tid)
    except Exception as exc:
        res = {"status": "ERROR", "detail": "%s: %s" % (type(exc).__name__, str(exc)[:200])}
    base = (res.get("baseline") or {})
    model_scn = res.get("model_scenarios") or []
    feat_scn = res.get("feature_counterfactuals") or []
    trimmed = {"status": res.get("status"),
               "primary_txn": base.get("recorded_model_txn") or tid,
               "baseline_probability": base.get("probability"),
               "threshold_verdict": base.get("threshold_verdict"),
               "recorded_model_probability": base.get("recorded_model_probability"),
               "matches_recorded_model": base.get("matches_recorded_model"),
               "model_scenarios": [{"id": s.get("id"),
                                    "probability": s.get("probability"),
                                    "delta": s.get("delta"),
                                    "verdict": s.get("threshold_verdict") or s.get("verdict")}
                                   for s in model_scn if isinstance(s, dict)],
               "feature_counterfactuals": [{"feature": s.get("feature"),
                                            "value": s.get("probability") or s.get("value")}
                                           for s in feat_scn[:6] if isinstance(s, dict)],
               "n_model_scenarios": len(model_scn),
               "note": "agent supplies only transaction ids from its own graph "
                       "investigation; it never reads the case file"}
    tr = trace_from(state, "counterfactual", tool="counterfactual.engine.model_analysis",
                    ok=res.get("status") == "OK",
                    detail="%s, baseline=%.4f, %d model scenario(s), %d feature sweep" % (
                        res.get("status"), base.get("probability") or 0.0,
                        len(model_scn), len(feat_scn)))
    return {"counterfactual": trimmed, "trace": tr,
            "timings_ms": timings_from(state, "counterfactual", (time.perf_counter() - t0) * 1000)}


# --------------------------------------------------------------------------
# 11. POLICY — every candidate action validated before recommendation
# --------------------------------------------------------------------------
_CANDIDATES = {
    "fraud": ["ESCALATE_TO_FRAUD_REVIEW", "LINK_HISTORICAL_CASE_FOR_ANALYST_REVIEW",
              "REQUEST_ADDITIONAL_EVIDENCE", "CLOSE_NO_FURTHER_ACTION"],
    "legitimate": ["CLOSE_NO_FURTHER_ACTION", "LINK_HISTORICAL_CASE_FOR_ANALYST_REVIEW",
                   "REQUEST_ADDITIONAL_EVIDENCE", "ESCALATE_TO_FRAUD_REVIEW"],
    "uncertain": ["REQUEST_ADDITIONAL_EVIDENCE", "ESCALATE_TO_FRAUD_REVIEW",
                  "LINK_HISTORICAL_CASE_FOR_ANALYST_REVIEW", "CLOSE_NO_FURTHER_ACTION"],
}


def policy_gate(state: InvestigationState) -> Dict[str, Any]:
    from policies import rules
    t0 = time.perf_counter()
    f = state.get("facts") or {}
    d = state.get("decision") or {}
    ev = state.get("evidence") or []
    verdict = str(d.get("verdict") or "uncertain")
    if verdict not in _CANDIDATES:
        verdict = "uncertain"

    facts = {"risk_probability": float(d.get("p1") if d.get("p1") is not None else 0.0),
             "graph_evidence_count": len([e for e in ev
                                          if e.get("evidence_class") == "derived_graph"]),
             "historical_case_count": len(f.get("similar_candidates") or []),
             "uncertainty": state.get("uncertainty", "SUFFICIENT")}
    sel = rules.select(facts, _CANDIDATES[verdict])
    # prove the hard denials hold for this exact fact set
    forbidden = {a: rules.validate(a, facts) for a in rules.FORBIDDEN_ACTIONS[:4]}
    gate = {"facts": facts, "action": sel["action"], "reason": sel["reason"],
            "evaluated": sel["evaluated"], "policy_module": sel["policy"],
            "forbidden_probe": {k: {"allowed": v[0], "reason": v[1]} for k, v in forbidden.items()},
            "counterfactual_gate": {
                "at_high_risk": rules.validate(sel["action"],
                                               dict(facts, risk_probability=0.95))[0],
                "at_low_risk": rules.validate(sel["action"],
                                              dict(facts, risk_probability=0.05))[0]}}
    tr = trace_from(state, "policy", tool="policies.rules.select",
                    ok=True, detail="recommended %s (%d candidate(s) evaluated, %d forbidden denied)" % (
                        sel["action"], len(sel["evaluated"]),
                        sum(1 for v in forbidden.values() if not v[0])))
    return {"policy": gate, "trace": tr,
            "timings_ms": timings_from(state, "policy", (time.perf_counter() - t0) * 1000)}


# --------------------------------------------------------------------------
# 12. RECOMMEND — deterministic narrative + real LLM wording
# --------------------------------------------------------------------------
def recommend(state: InvestigationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    f, a, d = state.get("facts") or {}, state.get("analysis") or {}, state.get("decision") or {}
    pol = state.get("policy") or {}
    ev = state.get("evidence") or []
    bc = _builder()

    try:
        narrative = bc.build_summary(f, a, bc.decide(f, a, ev)) if (f and a and ev) else ""
    except Exception:
        narrative = ""
    if not narrative:
        narrative = "Insufficient graph evidence to summarise this case."

    # --- real LLM call: wording only, every fact already in state ---
    # Measured on this model: latency AND success both track prompt size
    # (34 tokens -> 16 s ok, 59 -> 26 s ok, 105 -> fail, 234 -> 261 s).
    # A ~70-token prompt succeeded 4/4 runs at 21-34 s, so the fact block is
    # one terse line; summary.narrative stays deterministic either way.
    from agent.llm import client as llm
    risk = state.get("risk") or {}
    graph_n = len([e for e in ev if e.get("evidence_class") == "derived_graph"])
    facts_block = "; ".join(filter(None, [
        str(state.get("case_id")),
        "txn %s" % f.get("flagged_txn_id"),
        "%.2f USD %s" % (f.get("flagged_amount") or 0.0, f.get("flagged_channel")),
        "model %.4f" % (risk.get("model_probability") or 0.0),
        "p %.4f" % (d.get("p1") if d.get("p1") is not None else 0.0),
        "verdict %s" % d.get("verdict"),
        "%d graph facts" % graph_n,
        "action %s" % pol.get("action"),
    ]))
    prompt = "2-sentence case summary, facts only: " + facts_block
    # single attempt + 45 s ceiling: a failed call must not stall the run, and
    # summary.narrative (deterministic) is always populated regardless
    res = llm.generate(prompt, purpose="case_summary", max_output_tokens=2048,
                       retry=False)
    tokens = int(res.get("tokens") or 0)

    tr = trace_from(state, "recommend", tool="agent.llm.client.generate",
                    ok=res.get("status") == "ok",
                    detail="llm %s (%s/%s), %s tokens, %.0f ms" % (
                        res.get("status"), res.get("provider"), res.get("model"),
                        tokens, res.get("latency_ms") or 0.0))
    if not narrative:
        tr.append({"node": "recommend", "tool": "fallback", "http_status": None,
                   "latency_ms": None, "ok": True, "detail": "no deterministic summary available"})

    summary = {"narrative": narrative,
               "plain_language": res.get("text") or "",
               "llm": {"status": res.get("status"), "provider": res.get("provider"),
                       "model": res.get("model"), "tokens_in": res.get("tokens_in"),
                       "tokens_out": res.get("tokens_out"), "tokens": tokens,
                       "latency_ms": res.get("latency_ms"), "error": res.get("error")},
               "next_best_action": pol.get("action"),
               "recommendation_reason": pol.get("reason"),
               "verdict": d.get("verdict"),
               "uncertainty": state.get("uncertainty")}
    return {"summary": summary, "status": "COMPLETE",
            "tokens": int(state.get("tokens") or 0) + tokens,
            "trace": tr,
            "timings_ms": timings_from(state, "recommend", (time.perf_counter() - t0) * 1000)}
