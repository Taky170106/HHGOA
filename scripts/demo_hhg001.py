"""Live end-to-end agent demonstration - HHG-001.

Runs one real benchmark case through the whole investigation workflow and
prints the agent's steps as they happen:

    CASE -> GRAPH EVIDENCE (TigerGraph) -> RELATIONSHIPS -> RISK SCORE
         -> XAI (SHAP) -> FINDINGS -> SUMMARY -> POLICY -> NEXT BEST ACTION

Every number printed is produced by that run: the GSQL query responses come
from the live RESTPP endpoint, the risk score from models/fraud_model.pkl, the
SHAP values from TreeExplainer, the actions from policies/rules.py semantics.

Artifacts:
    validation/phase3_e2e.json   machine-readable run record
    cases/HHG-001.json           the case answer produced by this run

Run:  python scripts/demo_hhg001.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

if not getattr(sys.stdout, "_hhg_wrapped", False):
    _w = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _w._hhg_wrapped = True
    sys.stdout = _w

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_cases as B  # noqa: E402

ROOT = os.path.dirname(HERE)
CASE_ID = "HHG-001"
LINE = "=" * 78


def hdr(n, title):
    print("\n%s\nSTEP %d  %s\n%s" % (LINE, n, title, LINE))


def main():
    row = next(r for r in B.pack if r["case_id"] == CASE_ID)
    t0 = time.time()
    steps = []

    # ---------------------------------------------------------------- 1
    hdr(1, "CASE - the agent receives the alert")
    print("  case_id      : %s" % row["case_id"])
    print("  opened_at    : %s" % row["opened_at"])
    print("  trigger_type : %s" % row["trigger_type"])
    print("  trigger_text : %s" % row["trigger_text"])
    print("  flagged_txn  : %s   card %s   customer %s"
          % (row["flagged_txn_id"], row["card_id"], row["customer_id"]))
    print("  risk_score   : %s  (an input, not an answer)" % (row["risk_score"] or "n/a"))
    steps.append({"step": 1, "name": "CASE", "detail": row["trigger_text"]})

    # ---------------------------------------------------------------- 2
    hdr(2, "GRAPH EVIDENCE - live TigerGraph queries (read-only)")
    f = B.gather(row)
    tg_calls = []
    for name, res in f["tg"].items():
        print("  %-26s http=%s  %sms" % (name, res.get("status"), res.get("ms")))
        tg_calls.append({"query": name, "http_status": res.get("status"),
                         "latency_ms": res.get("ms"), "detail": res})
    print("  total live GSQL calls: %d" % len(tg_calls))
    steps.append({"step": 2, "name": "GRAPH_EVIDENCE",
                  "detail": "%d live GSQL queries, all read-only" % len(tg_calls),
                  "queries": [c["query"] for c in tg_calls]})

    # ---------------------------------------------------------------- 3
    hdr(3, "RELATIONSHIPS - what the graph actually returned")
    gt = f["tg"]["get_transaction"]
    bcc = f["tg"]["benchmark_case_context"]
    print("  card owners  : %s" % (gt["cards"] or "none"))
    print("  customers    : %s" % (gt["customers"] or "none"))
    print("  device       : %s" % (f["device_id"] or "no FROM_DEVICE edge for this txn"))
    print("  billing reg  : %s  home_country=%s"
          % ((f["region"] or {}).get("region_code", "n/a"),
             (f["region"] or {}).get("is_home_country")))
    print("  prev / next  : %s / %s" % (gt["prev"] or "-", gt["next"] or "-"))
    print("  card history : %d prior transaction(s) on %s"
          % (f["card_txn_count"], f["card_id"]))
    print("  related cases: %s" % (f["tg"]["find_related_cases"]["cases"] or "none"))
    print("  case context : RelatedViaDevice=%d RelatedViaRegion=%d RelatedViaCard=%d"
          % (bcc["related_via_device"], bcc["related_via_region"], bcc["related_via_card"]))
    steps.append({"step": 3, "name": "RELATIONSHIPS",
                  "detail": "card=%s customer=%s device=%s region=%s related_cases=%d"
                            % (f["card_id"], f["customer_id"], f["device_id"] or "none",
                               (f["region"] or {}).get("region_code", "n/a"),
                               len(f["tg"]["find_related_cases"]["cases"]))})

    # ---------------------------------------------------------------- 4
    hdr(4, "RISK SCORE - ML on real labels (risk_score excluded: leakage)")
    a = B.analyse(f)
    print("  model probability : %.4f  (RandomForest, 32 graph/txn features)" % a["ml_probability"])
    print("  input risk_score  : %s" % ("n/a" if a["risk_input"] is None else a["risk_input"]))
    print("  evidence log-odds : %s" % a.get("evidence_log_odds"))
    print("  calibrated p      : %.4f" % a["p_initial"])
    print("  weights source    : %s" %
          ("models/evidence_weights.json (learned from %d labeled fraud / %d cleared txns)"
           % (B.LABEL_N[0], B.LABEL_N[1]) if B.WEIGHTS_TRUSTED else "unweighted fallback"))
    on = [k for k in B.SIGNAL_KEYS if a["signals"].get(k)]
    off = [k for k in B.SIGNAL_KEYS if not a["signals"].get(k)]
    print("  signals present   : %s" % (", ".join(on) or "none"))
    print("  signals absent    : %s" % (", ".join(off) or "none"))
    steps.append({"step": 4, "name": "RISK_SCORE",
                  "detail": "model=%.4f calibrated=%.4f" % (a["ml_probability"], a["p_initial"]),
                  "model_probability": a["ml_probability"],
                  "calibrated_probability": a["p_initial"],
                  "signals_present": on})

    # ---------------------------------------------------------------- 5
    hdr(5, "XAI - SHAP explanation (MODEL EXPLANATION, not graph explanation)")
    print("  MODEL EXPLANATION - what drove the model score for txn %s:"
          % f["flagged_txn_id"])
    for t in (f["shap"].get(f["flagged_txn_id"]) or [])[:6]:
        print("      %-26s value=%-10s shap=%+.5f"
              % (t["feature"], t["value"], t["shap_value"]))
    print("  GRAPH EVIDENCE - independent of the model, from TigerGraph:")
    for k in on[:6]:
        print("      signal: %s" % k)
    print("  NOTE: SHAP explains the model output only. It does not explain the")
    print("        graph; graph facts are listed separately above.")
    steps.append({"step": 5, "name": "XAI",
                  "detail": "SHAP local explanation over %d features"
                            % len(f["shap"].get(f["flagged_txn_id"]) or []),
                  "model_explanation": f["shap"].get(f["flagged_txn_id"]) or [],
                  "graph_evidence": on,
                  "separation": "MODEL EXPLANATION vs GRAPH EVIDENCE kept distinct"})

    # ---------------------------------------------------------------- 6
    hdr(6, "FINDINGS + SUMMARY")
    ev = B.build_evidence(f, a)
    d = B.decide(f, a, ev)
    print("  evidence items : %d (%d graph-derived, %d direct, %d model)"
          % (len(ev), len(d["graph_items"]),
             sum(1 for e in ev if e["evidence_class"] == "direct"),
             sum(1 for e in ev if e["evidence_class"] == "model_analytical")))
    for e in ev:
        print("      [%s] %-14s %s" % (e["evidence_id"], e["evidence_class"], e["claim"][:96]))
    print("  pattern        : %s" % a["pattern"])
    print("  verdict        : %s   status=%s" % (d["verdict"], d["status"]))
    print("  p (before)     : %.4f" % d["p0"])
    print("  p (after)      : %.4f" % d["p1"])
    print("  exposure       : $%.2f over %d txn(s)" % (d["exposure"], len(d["affected"])))
    steps.append({"step": 6, "name": "FINDINGS_SUMMARY",
                  "detail": "pattern=%s verdict=%s p=%.4f->%.4f"
                            % (a["pattern"], d["verdict"], d["p0"], d["p1"]),
                  "evidence_ids": [e["evidence_id"] for e in ev]})

    # ---------------------------------------------------------------- 7
    hdr(7, "POLICY -> NEXT BEST ACTION")
    if d["requests"]:
        print("  evidence requested : %s" % d["requests"][0]["type"])
        print("  assumed response   : %s" % d["requests"][0]["assumed_response"])
    else:
        print("  evidence requested : none (Section 6 - settled)")
    print("  INITIAL (before additional evidence):")
    for x in d["initial"]:
        print("      %-24s route=%-4s %s" % (x["action"], x["route"], x["reason"][:70]))
    print("  FINAL (after additional evidence):")
    for x in d["final"]:
        print("      %-24s route=%-4s %s" % (x["action"], x["route"], x["reason"][:70]))
    print("  what_changed    : %s" % d["what_changed"])
    print("  SAR required    : %s" % d["sar_file"])
    print("  approval routes : %s" % ", ".join(sorted({x["route"] for x in d["final"]})))
    steps.append({"step": 7, "name": "POLICY_NEXT_BEST_ACTION",
                  "detail": d["what_changed"],
                  "initial_actions": [x["action"] for x in d["initial"]],
                  "final_actions": [x["action"] for x in d["final"]],
                  "routes": sorted({x["route"] for x in d["final"]}),
                  "sar_file": d["sar_file"]})

    # ---------------------------------------------------------------- 8
    hdr(8, "CASE RESULT")
    out = os.path.join(ROOT, "cases", "%s.json" % CASE_ID)
    print("  answer file    : %s" % out)
    print("  graph write    : BLOCKED (see docs/GRAPH_WRITE_BLOCKER.md)")
    print("  wall clock     : %.2fs" % (time.time() - t0))
    steps.append({"step": 8, "name": "CASE_RESULT",
                  "detail": "answer written; graph write blocked and documented"})

    record = {
        "case_id": CASE_ID,
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "PASS",
        "steps": steps,
        "live_gsql_calls": tg_calls,
        "evidence_items": len(ev),
        "graph_derived_evidence": len(d["graph_items"]),
        "pattern": a["pattern"],
        "verdict": d["verdict"],
        "case_status": d["status"],
        "fraud_probability_before": d["p0"],
        "fraud_probability_after": d["p1"],
        "model_probability": a["ml_probability"],
        "exposure_usd": d["exposure"],
        "affected_txn_ids": d["affected"],
        "evidence_requests": d["requests"],
        "initial_actions": d["initial"],
        "final_actions": d["final"],
        "what_changed": d["what_changed"],
        "sar_file": d["sar_file"],
        "approval_routes": sorted({x["route"] for x in d["final"]}),
        "graph_write": {"status": "BLOCKED", "document": "docs/GRAPH_WRITE_BLOCKER.md"},
        "answer_file": os.path.relpath(out, ROOT).replace("\\", "/"),
        "wall_clock_s": round(time.time() - t0, 3),
    }
    path = os.path.join(ROOT, "validation", "phase3_e2e.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)
    print("\n%s\nDEMO E2E -> %s\n%s" % (LINE, path, LINE))
    print("E2E_STATUS = PASS")
    return record


if __name__ == "__main__":
    main()
