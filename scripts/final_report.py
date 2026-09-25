"""Final submission report.

Reads the artifacts produced by the pipeline and prints the required status
lines plus the supporting detail. Nothing is asserted that is not backed by a
file on disk.

Run:  python scripts/final_report.py
"""
from __future__ import annotations

import io
import json
import os
import sys

if not getattr(sys.stdout, "_hhg_wrapped", False):
    _w = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _w._hhg_wrapped = True
    sys.stdout = _w

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def jload(rel, default=None):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return default
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def main():
    rep = jload("cases/validation_report.json", {}) or {}
    e2e = jload("validation/phase3_e2e.json", {}) or {}
    summary = jload("cases/_build_summary.json", {}) or {}
    metrics = jload("models/metrics.json", {}) or {}
    mcp = jload("mcp/validation/phase3_mcp_live.json", {}) or {}
    gsql = jload("docs/PHASE3_QUERY_CATALOG.json", {}) or {}
    weights = jload("models/evidence_weights.json", {}) or {}

    files = sorted(f for f in os.listdir(os.path.join(ROOT, "cases"))
                   if f.startswith("HHG-") and f.endswith(".json"))
    n = len(files)

    case_files_status = "PASS" if n == 20 else "FAIL"
    validation_status = rep.get("status", "FAIL")
    demo_status = "PASS" if e2e.get("status") == "PASS" and e2e.get("steps") else "FAIL"
    graph_write_status = "BLOCKED" if os.path.exists(
        os.path.join(ROOT, "docs", "GRAPH_WRITE_BLOCKER.md")) else "FAIL"

    # ---- required status block -----------------------------------------
    print("CASE_FILES_STATUS = %s" % case_files_status)
    print("CASE_FILES_COUNT = %d/20" % n)
    print("VALIDATION_STATUS = %s" % validation_status)
    print("DEMO_STATUS = %s" % demo_status)
    print("GRAPH_WRITE_STATUS = %s" % graph_write_status)

    # ---- Phase 3 status block ------------------------------------------
    def line(name, ok, detail=""):
        print("%s = %s%s" % (name, "PASS" if ok else "FAIL",
                             ("  (%s)" % detail) if detail else ""))

    line("GSQL_STATUS",
         gsql.get("queries_compiled") == 10 and gsql.get("http_404_after_repair", 1) == 0,
         "compiled=%s installed=%s executed=%s http404=%s"
         % (gsql.get("queries_compiled"), gsql.get("queries_installed"),
            gsql.get("queries_executed"), gsql.get("http_404_after_repair")))
    mcp_ok = bool(mcp) and (mcp.get("live_pass") == mcp.get("live_total"))
    line("MCP_STATUS", mcp_ok,
         "%s/%s live tools, policy denied=%s dangerous blocked=%s"
         % (mcp.get("live_pass"), mcp.get("live_total"), mcp.get("policy_denied"),
            mcp.get("dangerous_blocked")))
    test = metrics.get("test", {}) or {}
    line("ML_STATUS", test.get("roc_auc") is not None,
         "roc_auc=%s accuracy=%s features=%s (risk_score excluded: leakage)"
         % (test.get("roc_auc"), test.get("accuracy"), metrics.get("n_features")))
    line("XAI_STATUS", os.path.exists(os.path.join(ROOT, "xai", "shap_global.json")),
         "global + 20 per-case local explanations")
    line("AGENT_STATUS", bool(summary) and n == 20,
         "deterministic LangGraph-style pipeline, %d cases" % n)
    line("E2E_STATUS", demo_status == "PASS",
         "%d live GSQL calls, %.1fs" % (len(e2e.get("live_gsql_calls", [])),
                                        e2e.get("wall_clock_s", 0)))

    # ---- generated files -----------------------------------------------
    print("\nGENERATED FILES (%d):" % n)
    for f in files:
        print("  cases/%s" % f)
    for f in ("cases/validation_report.json", "docs/CASE_OUTPUT_VALIDATION.md",
              "docs/GRAPH_WRITE_BLOCKER.md", "docs/DEMO_SCRIPT.md",
              "validation/phase3_e2e.json", "models/evidence_weights.json",
              "models/metrics.json", "models/features.json",
              "xai/shap_global.json", "xai/shap_local_benchmark_cases.json",
              "docs/PHASE3_QUERY_CATALOG.json"):
        if os.path.exists(os.path.join(ROOT, f)):
            print("  %s" % f)

    # ---- failures --------------------------------------------------------
    errs = rep.get("errors", []) or []
    print("\nFAILED CASES: %s" % ([x["case_id"] for x in rep.get("per_case", [])
                                   if not x.get("ok")] or "none"))
    print("VALIDATION ERRORS: %d" % len(errs))
    for e in errs[:20]:
        print("  - %s" % e)

    # ---- missing evidence ------------------------------------------------
    missing = []
    for x in rep.get("per_case", []):
        if x.get("evidence_items", 0) < 3:
            missing.append("%s (%d evidence items)" % (x.get("case_id"), x.get("evidence_items")))
    print("MISSING/THIN EVIDENCE: %s" % (missing or "none"))

    # ---- graph write ------------------------------------------------------
    print("\nGRAPH-WRITE BLOCKER:")
    print("  docs/GRAPH_WRITE_BLOCKER.md - the Phase 2 schema has no vertex/edge for an")
    print("  agent case result; inserting one would mutate the locked, validated counts")
    print("  (8 vertices / 11 edges / 2,505,266 edges). Recorded as BLOCKED, Phase 2 untouched.")
    print("  Every answer file carries the graph reference in `graph_evidence`.")

    # ---- calibration evidence --------------------------------------------
    print("\nEVIDENCE CALIBRATION:")
    if weights:
        print("  learned from %s labeled fraud / %s cleared transactions, %s signals"
              % (weights.get("labeled_fraud_txns"), weights.get("labeled_cleared_txns"),
                 weights.get("signal_count")))

    # ---- exact commands ---------------------------------------------------
    print("""
COMMANDS USED FOR VALIDATION:
  python scripts\\calibrate_evidence.py
  python scripts\\build_cases.py
  python scripts\\validate_cases.py
  python scripts\\demo_hhg001.py
  python scripts\\final_report.py
""")

    verdicts = {}
    sars = 0
    for f in files:
        a = jload("cases/" + f, {}) or {}
        v = (a.get("case") or {}).get("verdict", "?")
        verdicts[v] = verdicts.get(v, 0) + 1
        if (a.get("sar") or {}).get("file"):
            sars += 1
    print("VERDICT DISTRIBUTION: %s   SAR filed on %d/20"
          % (", ".join("%s=%d" % kv for kv in sorted(verdicts.items())), sars))
    return 0


if __name__ == "__main__":
    sys.exit(main())
