"""Run the counterfactual engine over all 20 cases and write one results file.

Read-only: reads cases/*.json + the trained model, writes counterfactual/results.json.
Nothing in cases/, models/ or the graph is modified.

Run:  python scripts/build_counterfactual.py
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from counterfactual import engine  # noqa: E402

T0 = time.time()


def log(m):
    print("[%6.1fs] %s" % (time.time() - T0, m), flush=True)


def main():
    cases_dir = os.path.join(ROOT, "cases")
    ids = sorted(f[:-5] for f in os.listdir(cases_dir)
                 if f.endswith(".json") and f.startswith("HHG-"))
    log("counterfactual run over %d cases" % len(ids))

    out = {}
    status_counts = {}
    match_counts = {"match": 0, "mismatch": 0, "absent": 0}
    flips = 0

    for cid in ids:
        r = engine.analyse(cid)
        out[cid] = r
        st = r.get("status", "?")
        status_counts[st] = status_counts.get(st, 0) + 1
        base = r.get("baseline") or {}
        m = base.get("matches_recorded_model")
        if m is True:
            match_counts["match"] += 1
        elif m is False:
            match_counts["mismatch"] += 1
        else:
            match_counts["absent"] += 1
        flips += sum(1 for s in r.get("model_scenarios", []) if s.get("flips_threshold"))
        log("  %s %s p=%.4f pre=%s (%.2fs)"
            % (cid, st, base.get("probability", -1),
               base.get("recorded_pre_probability"), r.get("elapsed_s", 0)))

    doc = {
        "scope": "counterfactual analysis of all benchmark cases",
        "engine": "counterfactual/engine.py",
        "model": "models/fraud_model.pkl",
        "thresholds": {"fraud": engine.P_FRAUD, "legitimate": engine.P_LEGIT},
        "run": {
            "cases_total": len(ids),
            "status_counts": status_counts,
            "baseline_vs_recorded": match_counts,
            "threshold_flip_scenarios": flips,
            "elapsed_s": round(time.time() - T0, 2),
        },
        "cases": out,
    }
    path = os.path.join(ROOT, "counterfactual", "results.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
    log("wrote %s (%.1f KB)" % (path, os.path.getsize(path) / 1024.0))

    ok = (status_counts.get("OK", 0) == len(ids)
          and match_counts["mismatch"] == 0 and match_counts["absent"] == 0)
    print(json.dumps({"COUNTERFACTUAL": "PASS" if ok else "REVIEW",
                      "run": doc["run"]}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
