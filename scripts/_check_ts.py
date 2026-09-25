import io, sys, math
import pandas as pd, numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
TXCOLS = ["txn_id", "customer_id", "card_id", "card1_num", "ts", "dt_seconds", "amount",
          "product_cd", "channel", "risk_score", "addr1", "addr2", "dist1", "dist2",
          "p_emaildomain", "r_emaildomain"]
tx = pd.read_csv(r"D:\HHG\data\vertices\transaction.csv", usecols=TXCOLS, dtype=str)
tx["amount_f"] = pd.to_numeric(tx["amount"], errors="coerce")
tx["ts_f"] = pd.to_numeric(tx["ts"], errors="coerce")
print("rows with NaN ts_f:", int(tx["ts_f"].isna().sum()))
print("rows with NaN amount_f:", int(tx["amount_f"].isna().sum()))
print(tx[tx["ts_f"].isna()][["txn_id", "ts", "dt_seconds", "amount"]].head(20).to_string())
pack = pd.read_csv(r"D:\HHG\DATASET\case_pack.csv", dtype=str)
byid = tx.set_index("txn_id", drop=False)
for _, r in pack.iterrows():
    t = r["flagged_txn_id"]
    row = byid.loc[t]
    ok_ts = math.isfinite(float(row["ts_f"])) if not pd.isna(row["ts_f"]) else False
    if not ok_ts:
        print("BAD", r["case_id"], t, repr(row["ts"]), repr(row["ts_f"]))
print("done")
