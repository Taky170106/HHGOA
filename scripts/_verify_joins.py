import io, os, sys
import pandas as pd
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
R = r"D:\HHG"
for f in ("on_card.csv", "involves.csv", "connected_to.csv"):
    print(f, "->", open(os.path.join(R, "data", "edges", f), encoding="utf-8").readline().strip())

onc = pd.read_csv(os.path.join(R, "data", "edges", "on_card.csv"), dtype=str)
cc = pd.read_csv(os.path.join(R, "data", "vertices", "closed_case.csv"), dtype=str)
out = dict(zip(cc["case_id"], cc["outcome"]))
onc["outcome"] = onc["from_case_id"].map(out)
print("\nclosed cases:", len(cc), " outcome:", cc["outcome"].value_counts().to_dict())
print("on_card edges:", len(onc), " mapped outcome:", onc["outcome"].value_counts(dropna=False).to_dict())
print("distinct cards in on_card:", onc["to_card_id"].nunique())

g = onc.groupby("to_card_id").size()
print("cases per card: mean=%.2f max=%d  cards with >1 case=%d" %
      (g.mean(), g.max(), int((g > 1).sum())))

# how many cases per card, split by outcome mix
mix = onc.groupby("to_card_id")["outcome"].apply(lambda s: tuple(sorted(set(s))))
from collections import Counter
print("outcome mix per card:", Counter(mix).most_common(10))

# n_txns distribution for cleared vs confirmed
for o in ("confirmed_fraud", "cleared"):
    sub = cc[cc["outcome"] == o]
    print(o, "cases=", len(sub), "n_txns head:", sub["n_txns"].astype(int).describe().to_dict())

inv = pd.read_csv(R + r"\data\edges\involves.csv", dtype=str)
print("involves edges:", len(inv))
print("txn->cases: txns with >1 case =",
      int((inv.groupby("to_txn_id").size() > 1).sum()))
