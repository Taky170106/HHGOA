#!/usr/bin/env python3
"""Offline graph validation — simulates TigerGraph validation without a live instance.
Checks vertex/edge counts, PK uniqueness, orphan edges, and sample traversals."""
from pathlib import Path
import pandas as pd
import time

ROOT = Path(__file__).resolve().parents[2]
V = ROOT / "data/vertices"
E = ROOT / "data/edges"

def load(name):
    p = V / name if (V / name).exists() else E / name
    return pd.read_csv(p, low_memory=False)

def check_pk(df, col):
    dups = df[col].duplicated().sum()
    nulls = df[col].isna().sum()
    return dups, nulls

start = time.time()
print("=== Graph Validation (offline) ===")

# vertex counts
verts = {}
for f in sorted(V.glob("*.csv")):
    if f.name == "card_mapping.csv":
        continue
    df = pd.read_csv(f, low_memory=False)
    verts[f.stem] = len(df)
    print(f"Vertex {f.stem:20} {len(df):,}")

print("--- edges ---")
edges = {}
for f in sorted(E.glob("*.csv")):
    df = pd.read_csv(f, low_memory=False)
    edges[f.stem] = len(df)
    print(f"Edge {f.stem:20} {len(df):,}")

# PK uniqueness
print("\n--- PK uniqueness ---")
checks = [
    ("customer.csv", "customer_id"),
    ("card.csv", "card_id"),
    ("transaction.csv", "txn_id"),
    ("device_profile.csv", "device_profile_id"),
    ("email_domain.csv", "domain"),
    ("billing_region.csv", "region_code"),
    ("closed_case.csv", "case_id"),
    ("benchmark_case.csv", "case_id"),
]
for fname, pk in checks:
    df = pd.read_csv(V / fname, low_memory=False, dtype={pk: str})
    dups, nulls = check_pk(df, pk)
    print(f"{fname:25} pk={pk:25} dups={dups} nulls={nulls} {'PASS' if dups==0 and nulls==0 else 'FAIL'}")

# orphan checks
print("\n--- orphan edges ---")
txn_ids = set(pd.read_csv(V / "transaction.csv", usecols=["txn_id"], dtype=str)["txn_id"])
card_ids = set(pd.read_csv(V / "card.csv", usecols=["card_id"], dtype=str)["card_id"])
cust_ids = set(pd.read_csv(V / "customer.csv", usecols=["customer_id"], dtype=str)["customer_id"])
dp_ids = set(pd.read_csv(V / "device_profile.csv", usecols=["device_profile_id"], dtype=str)["device_profile_id"])
# check
for edge, cols in [
    ("made.csv", ("from_card_id", "to_txn_id", card_ids, txn_ids)),
    ("owns.csv", ("from_customer_id","to_card_id", cust_ids, card_ids)),
    ("involves.csv", ("from_case_id","to_txn_id", None, txn_ids)),
    ("connected_to.csv", ("from_case_id","to_card_id", None, card_ids)),
    ("from_device.csv", ("from_txn_id","to_device_profile_id", txn_ids, dp_ids)),
    ("triggers.csv", ("from_case_id","to_txn_id", None, txn_ids)),
    ("billed_in.csv", ("from_txn_id","to_region_code", txn_ids, None)),
]:
    df = pd.read_csv(E / edge, dtype=str, low_memory=False)
    if len(df)==0:
        print(f"{edge:20} empty — skip")
        continue
    # if we have target set, check
    from_col, to_col, from_set, to_set = cols
    if from_set is not None:
        o = (~df[from_col].isin(from_set)).sum()
        print(f"{edge:20} from orphan {o}")
    if to_set is not None:
        o = (~df[to_col].isin(to_set)).sum()
        print(f"{edge:20} to orphan {o} {'PASS' if o==0 else 'FAIL'}")

# sample traversals
print("\n--- sample traversals ---")
import random
tx = pd.read_csv(V / "transaction.csv", dtype=str, low_memory=False)
made = pd.read_csv(E / "made.csv", dtype=str, low_memory=False)
owns = pd.read_csv(E / "owns.csv", dtype=str, low_memory=False)
fd = pd.read_csv(E / "from_device.csv", dtype=str, low_memory=False)
inv = pd.read_csv(E / "involves.csv", dtype=str, low_memory=False)
trig = pd.read_csv(E / "triggers.csv", dtype=str, low_memory=False)
closed = pd.read_csv(V / "closed_case.csv", dtype=str, low_memory=False)

# sample transaction
sample_txn = "3514030"  # HHG-001 flagged
print(f"get_transaction({sample_txn}):", sample_txn in txn_ids)
# customer history
print(f"customer C12382 cards:", owns[owns["from_customer_id"]=="C12382"]["to_card_id"].tolist()[:2])
print(f"card C12382-K1 txns:", made[made["from_card_id"]=="C12382-K1"].shape[0])
# device
# find a device shared by >1
dp = pd.read_csv(V / "device_profile.csv", low_memory=False)
shared = dp[dp["customer_count"]>1].iloc[0]
print(f"sample shared device {shared['device_profile_id']} customers={shared['customer_count']} cards={shared['card_count']}")
dev_txns = fd[fd["to_device_profile_id"]==shared["device_profile_id"]]
print(f"  linked txns {len(dev_txns)} sample {dev_txns['from_txn_id'].head(2).tolist()}")
# benchmark cases
print("\n--- benchmark connectivity ---")
pack = pd.read_csv(V / "benchmark_case.csv", dtype=str, low_memory=False)
for _, r in pack.iterrows():
    cid, txn, card, cust = r["case_id"], r["flagged_txn_id"], r["card_id"], r["customer_id"]
    has_txn = txn in txn_ids
    has_card = card in card_ids
    has_cust = cust in cust_ids
    has_trig = ((trig["from_case_id"]==cid) & (trig["to_txn_id"]==txn)).any()
    print(f"{cid} txn={txn} card={card} cust={cust} txn:{has_txn} card:{has_card} cust:{has_cust} triggers:{has_trig} -> {'OK' if all([has_txn,has_card,has_cust,has_trig]) else 'MISSING'}")

elapsed = time.time()-start
print(f"\nElapsed {elapsed:.1f}s")
