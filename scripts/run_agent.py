"""Run the LangGraph investigation agent and record an honest artifact.

    python scripts/run_agent.py HHG-001          # one case
    python scripts/run_agent.py --all            # all 20
    python scripts/run_agent.py --list           # summarize existing runs

Artifacts (NEVER cases/*.json, which stay byte-identical):
    agent/runs/<case_id>.json       full state, trace, timings, llm usage
    validation/phase4_agent_runs.json   batch comparison vs the case files

Exit code 1 if any run errors or disagrees with its case file on verdict or
post-evidence probability (the two facts the agent must reproduce).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

RUNS = os.path.join(ROOT, "agent", "runs")
VALID = os.path.join(ROOT, "validation")


def _dump(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)


def _case_truth(case_id: str):
    """Verdict + post-evidence probability recorded in the (untouched) case file."""
    p = os.path.join(ROOT, "cases", "%s.json" % case_id)
    if not os.path.exists(p):
        return None
    c = json.load(open(p, encoding="utf-8"))
    return {"verdict": (c.get("case") or {}).get("verdict"),
            "p1": (c.get("case") or {}).get("fraud_probability")}


def run_one(case_id: str) -> dict:
    from agent.graph import run_case
    t0 = time.time()
    state = run_case(case_id)
    os.makedirs(RUNS, exist_ok=True)
    _dump(os.path.join(RUNS, "%s.json" % case_id), state)

    truth = _case_truth(case_id)
    dec = state.get("decision") or {}
    got_verdict = dec.get("verdict")
    got_p1 = dec.get("p1")
    verdict_match = bool(truth) and got_verdict == truth["verdict"]
    # probabilities are floats rounded to 4 dp in the case files
    p1_match = bool(truth) and got_p1 is not None and truth["p1"] is not None \
        and abs(float(got_p1) - float(truth["p1"])) <= 0.0005

    rec = {
        "case_id": case_id,
        "status": state.get("status"),
        "uncertainty": state.get("uncertainty"),
        "verdict_agent": got_verdict,
        "verdict_case": truth["verdict"] if truth else None,
        "verdict_match": verdict_match,
        "p1_agent": got_p1,
        "p1_case": truth["p1"] if truth else None,
        "p1_match": p1_match,
        "next_best_action": (state.get("policy") or {}).get("action"),
        "policy_reason": (state.get("policy") or {}).get("reason"),
        "tool_calls": state.get("tool_calls"),
        "tokens": state.get("tokens"),
        "llm_status": ((state.get("summary") or {}).get("llm") or {}).get("status"),
        "trace_len": len(state.get("trace") or []),
        "errors": state.get("errors") or [],
        "latency_s": state.get("latency_s"),
        "wall_s": round(time.time() - t0, 2),
    }
    rec["ok"] = (not rec["errors"]) and state.get("status") in ("OK", "COMPLETE") \
        and verdict_match and p1_match
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("case", nargs="?", help="case id, e.g. HHG-001")
    ap.add_argument("--all", action="store_true", help="run every case in case_pack")
    ap.add_argument("--list", action="store_true", help="summarize existing runs")
    args = ap.parse_args()

    if args.list:
        files = sorted(glob.glob(os.path.join(RUNS, "*.json")))
        print(json.dumps({"runs": len(files),
                          "cases": [os.path.basename(f)[:-5] for f in files]}, indent=2))
        return 0

    if args.all:
        import csv
        ids = [r["case_id"] for r in csv.DictReader(
            open(os.path.join(ROOT, "DATASET", "case_pack.csv"), encoding="utf-8"))]
    elif args.case:
        ids = [args.case]
    else:
        ap.error("give a case id, --all or --list")

    t0 = time.time()
    recs = [run_one(cid) for cid in ids]
    passed = sum(1 for r in recs if r["ok"])
    out = {
        "phase": "phase4_langgraph_agent",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runs_total": len(recs),
        "passed": passed,
        "failed": len(recs) - passed,
        "verdict_matches": sum(1 for r in recs if r["verdict_match"]),
        "p1_matches": sum(1 for r in recs if r["p1_match"]),
        "tool_calls_total": sum(int(r["tool_calls"] or 0) for r in recs),
        "tokens_total": sum(int(r["tokens"] or 0) for r in recs),
        "llm_statuses": sorted({r["llm_status"] for r in recs if r["llm_status"]}),
        "status_counts": {s: sum(1 for r in recs if r["status"] == s)
                          for s in sorted({r["status"] for r in recs if r["status"]})},
        "elapsed_s": round(time.time() - t0, 2),
        "runs": recs,
    }
    out["AGENT"] = "PASS" if out["failed"] == 0 else "FAIL"
    _dump(os.path.join(VALID, "phase4_agent_runs.json"), out)
    print(json.dumps({k: out[k] for k in ("AGENT", "runs_total", "passed", "failed",
                                          "verdict_matches", "p1_matches",
                                          "tool_calls_total", "tokens_total",
                                          "llm_statuses", "status_counts",
                                          "elapsed_s")}, indent=2))
    for r in recs:
        if not r["ok"]:
            print("FAIL %s: status=%s verdict %s vs %s p1 %s vs %s errors=%s"
                  % (r["case_id"], r["status"], r["verdict_agent"], r["verdict_case"],
                     r["p1_agent"], r["p1_case"], r["errors"]), file=sys.stderr)
    return 0 if out["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
