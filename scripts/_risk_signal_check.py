"""Does risk_score actually predict fraud in the labeled history?

README: "risk_score ... Above 0.7, most flagged transactions turn out to be
legitimate." Verify that against closed_cases_history (the only truth we have)
at ALERT level: first_fraud_txn_id for confirmed cases, the single transaction
for cleared cases.
"""
from __future__ import annotations

import io
import os
import sys

import pandas as pd

if not getattr(sys.stdout, "_hhg_wrapped", False):
    _w = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _w._hhg_wrapped = True
    sys.stdout = _w

ROOT = r"D:\HHG"
DS = os.path.join(ROOT, "DATASET")


def main():
    cc = pd.read_csv(os.path.join(DS, "closed_cases_history.csv"), dtype=str)
    tx = pd.read_csv(os.path.join(ROOT, "data", "vertices", "transaction.csv"),
                     usecols=["txn_id", "risk_score"], dtype=str)
    tx["risk"] = pd.to_numeric(tx["risk_score"], errors="coerce")
    rmap = tx.set_index("txn_id")["risk"]

    pos = cc.loc[cc["outcome"] == "confirmed_fraud", "first_fraud_txn_id"].dropna()
    pos = pos[pos != ""]
    neg = cc.loc[cc["outcome"] == "cleared", "txn_ids"].dropna()
    neg = [s for s in neg]

    df = pd.concat([
        pd.DataFrame({"txn_id": pos, "label": 1}),
        pd.DataFrame({"txn_id": neg, "label": 0}),
    ], ignore_index=True)
    df = df[df["txn_id"].isin(rmap.index)]
    df["risk"] = df["txn_id"].map(rmap)
    print("alerts: fraud=%d cleared=%d" % (int((df.label == 1).sum()),
                                           int((df.label == 0).sum())))

    has = df[df["risk"].notna()]
    print("risk_score present on %d/%d alerts" % (len(has), len(df)))

    for thr in (0.5, 0.6, 0.7, 0.8, 0.9):
        sub = has[has["risk"] >= thr]
        if not len(sub):
            print("  risk >= %.1f : none" % thr)
            continue
        p = (sub["label"] == 1).mean()
        print("  risk >= %.1f : n=%4d  P(fraud)=%.3f  -> %s"
              % (thr, len(sub), p, "mostly legitimate" if p < 0.5 else "mostly fraud"))

    for thr in (0.5, 0.6, 0.7, 0.8):
        sub = has[has["risk"] < thr]
        if len(sub):
            print("  risk <  %.1f : n=%4d  P(fraud)=%.3f" % (thr, len(sub), (sub.label == 1).mean()))

    print("\nrisk_score quartiles: fraud %s | cleared %s"
          % (has[has.label == 1]["risk"].quantile([.25, .5, .75]).round(2).tolist(),
             has[has.label == 0]["risk"].quantile([.25, .5, .75]).round(2).tolist()))

    # same check for the benchmark's own flagged transactions
    pack = pd.read_csv(os.path.join(DS, "case_pack.csv"), dtype=str)
    print("\nbenchmark flagged txns risk_score:",
          ", ".join("%s=%s" % (r.case_id, r.risk_score or "-")
                    for r in pack.itertuples() if r.risk_score))


if __name__ == "__main__":
    main()
