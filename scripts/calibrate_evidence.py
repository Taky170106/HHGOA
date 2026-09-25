"""Calibrate evidence weights from the labeled closed-case history.

The benchmark ships real labels: `closed_cases_history.csv` marks each closed
case as `confirmed_fraud` or `cleared`, and `involves` edges give every
transaction of every case. For each evidence signal we observe

    P(signal | fraud transaction)      P(signal | cleared transaction)

and set the signal's log-likelihood-ratio weight

    w = ln( (n_fraud + 1) / (N_fraud + 2) ) - ln( (n_clear + 1) / (N_clear + 2) )

so a signal that is *more* common on legitimate transactions earns a negative
(weight-reducing) contribution and one that is more common on fraud earns a
positive contribution. This is why the classifier does not simply block
everything: the weights come from the data, not from a hand-tuned rule.

Target-leakage guard: when scoring the transaction of closed case C, case C
itself is excluded from the case-memory signals (`exclude_case`), so a case can
never be evidence for itself.

Output: models/evidence_weights.json
Run:    python scripts/calibrate_evidence.py
"""
from __future__ import annotations

import io
import json
import math
import os
import sys

import numpy as np

if not getattr(sys.stdout, "_hhg_wrapped", False):
    _w = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _w._hhg_wrapped = True
    sys.stdout = _w

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_cases as B  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    inv, outcome = B.inv, B.CASE_OUTCOME
    inv = inv[inv["to_txn_id"].isin(B.tx_by_id.index)]

    pos_cases = set(outcome) & B.CONFIRMED
    neg_cases = set(outcome) & B.CLEARED
    pos_txns, neg_txns = set(), set()
    for k, grp in inv.groupby("from_case_id")["to_txn_id"]:
        if k in pos_cases:
            pos_txns |= set(grp)
        elif k in neg_cases:
            neg_txns |= set(grp)
    pos_txns -= neg_txns

    print("labeled transactions: fraud=%d cleared=%d" % (len(pos_txns), len(neg_txns)))

    counts = {k: [0, 0] for k in B.SIGNAL_KEYS}   # [fraud hits, cleared hits]
    npf = npl = 0
    for tag, txns in (("fraud", pos_txns), ("cleared", neg_txns)):
        for t in txns:
            c = B.TXN_CASE.get(str(t))
            s = B.signals_for(str(t), exclude_case=c)
            for k in B.SIGNAL_KEYS:
                if s.get(k):
                    counts[k][0 if tag == "fraud" else 1] += 1
        if tag == "fraud":
            npf = len(txns)

    npl = len(neg_txns)
    weights, rates = {}, {}
    for k in B.SIGNAL_KEYS:
        nf, nl = counts[k][0], counts[k][1]
        pf = (nf + 1) / (npf + 2)
        pl = (nl + 1) / (npl + 2)
        w = math.log(pf) - math.log(pl)
        weights[k] = round(max(-1.6, min(1.6, w)), 4)
        rates[k] = {"fraud_rate": round(pf, 5), "cleared_rate": round(pl, 5),
                    "fraud_hits": nf, "cleared_hits": nl, "weight": weights[k]}
        print("  %-20s fraud=%6.3f cleared=%6.3f  w=%+.3f" % (k, pf, pl, weights[k]))

    out = {
        "source": "DATASET/closed_cases_history.csv + data/edges/involves.csv",
        "method": "log-likelihood ratio with Laplace smoothing, per evidence signal",
        "labeled_fraud_txns": npf,
        "labeled_cleared_txns": npl,
        "signal_count": len(B.SIGNAL_KEYS),
        "weights": weights,
        "rates": rates,
        "leakage_guard": "the containing closed case is excluded from case-memory signals",
    }
    path = os.path.join(ROOT, "models", "evidence_weights.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("WROTE", path)
    return out


if __name__ == "__main__":
    main()
