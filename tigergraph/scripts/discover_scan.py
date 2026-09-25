"""Phase 2A Step 6 — full-file schema scan of all graph-ready CSVs (read-only).

For each file: rows, column names, inferred type set, null counts, distinct count
for identifier columns, duplicate PK detection, FK orphan detection vs target files.
Emits JSON evidence to stdout.
"""
import csv, json, os, sys, collections

csv.field_size_limit(10 ** 7)

def infer(v):
    if v == "":
        return "empty"
    try:
        int(v)
        return "int"
    except ValueError:
        pass
    try:
        float(v)
        return "float"
    except ValueError:
        pass
    return "str"

def scan(path, id_cols, scan_all_cols=False):
    types = collections.defaultdict(collections.Counter)
    nulls = collections.Counter()
    distinct = {}
    rows = 0
    seen = {c: set() for c in id_cols}
    dup = collections.Counter()
    samples = {}
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        header = r.fieldnames
        for row in r:
            rows += 1
            for k, v in row.items():
                t = infer(v)
                if t == "empty":
                    nulls[k] += 1
                elif len(types[k]) < 6:
                    types[k][t] += 1
                if scan_all_cols and len(samples.get(k, "")) == 0 and v:
                    samples[k] = v
            for c in id_cols:
                v = row.get(c, "")
                s = seen[c]
                if len(s) > 500000:
                    pass
                if v in s:
                    dup[c] += 1
                else:
                    s.add(v)
    for c in id_cols:
        distinct[c] = len(seen[c])
    return {
        "path": path.replace("\\", "/"),
        "rows": rows,
        "columns": header,
        "types": {k: dict(v) for k, v in types.items()},
        "null_counts": dict(nulls),
        "id_distinct": distinct,
        "id_duplicates": dict(dup),
    }

VERT_PK = {
    "benchmark_case.csv": ["case_id"],
    "billing_region.csv": ["region_code"],
    "card.csv": ["card_id"],
    "card_mapping.csv": ["card_id"],
    "closed_case.csv": ["case_id"],
    "customer.csv": ["customer_id"],
    "device_profile.csv": ["device_profile_id"],
    "email_domain.csv": ["domain"],
    "transaction.csv": ["txn_id"],
}
EDGE_IDS = {
    "billed_in.csv": ["from_txn_id", "to_region_code"],
    "connected_to.csv": ["from_case_id", "to_card_id"],
    "from_device.csv": ["from_txn_id", "to_device_profile_id"],
    "involves.csv": ["from_case_id", "to_txn_id"],
    "made.csv": ["from_card_id", "to_txn_id"],
    "next.csv": ["from_txn_id", "to_txn_id"],
    "on_card.csv": ["from_case_id", "to_card_id"],
    "owns.csv": ["from_customer_id", "to_card_id"],
    "purchaser_email.csv": ["from_txn_id", "to_domain"],
    "recipient_email.csv": ["from_txn_id", "to_domain"],
    "triggers.csv": ["from_case_id", "to_txn_id"],
}

out = {"vertices": [], "edges": []}
for fn, ids in sorted(VERT_PK.items()):
    out["vertices"].append(scan(os.path.join("data/vertices", fn), ids))
for fn, ids in sorted(EDGE_IDS.items()):
    out["edges"].append(scan(os.path.join("data/edges", fn), ids))

# ---- FK orphan checks: every edge endpoint must exist in its target vertex ----
def load_col(path, col):
    s = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            s.add(row[col])
    return s

V = {fn: load_col(os.path.join("data/vertices", fn), col) for fn, col in [
    ("transaction.csv", "txn_id"), ("card.csv", "card_id"), ("customer.csv", "customer_id"),
    ("closed_case.csv", "case_id"), ("benchmark_case.csv", "case_id"),
    ("device_profile.csv", "device_profile_id"), ("email_domain.csv", "domain"),
    ("billing_region.csv", "region_code"),
]}
FK_MAP = {
    "billed_in.csv": [("from_txn_id", "transaction.csv"), ("to_region_code", "billing_region.csv")],
    "connected_to.csv": [("from_case_id", "closed_case.csv"), ("to_card_id", "card.csv")],
    "from_device.csv": [("from_txn_id", "transaction.csv"), ("to_device_profile_id", "device_profile.csv")],
    "involves.csv": [("from_case_id", "closed_case.csv"), ("to_txn_id", "transaction.csv")],
    "made.csv": [("from_card_id", "card.csv"), ("to_txn_id", "transaction.csv")],
    "next.csv": [("from_txn_id", "transaction.csv"), ("to_txn_id", "transaction.csv")],
    "on_card.csv": [("from_case_id", "closed_case.csv"), ("to_card_id", "card.csv")],
    "owns.csv": [("from_customer_id", "customer.csv"), ("to_card_id", "card.csv")],
    "purchaser_email.csv": [("from_txn_id", "transaction.csv"), ("to_domain", "email_domain.csv")],
    "recipient_email.csv": [("from_txn_id", "transaction.csv"), ("to_domain", "email_domain.csv")],
    "triggers.csv": [("from_case_id", "benchmark_case.csv"), ("to_txn_id", "transaction.csv")],
}
orphans = {}
for fn, checks in FK_MAP.items():
    p = os.path.join("data/edges", fn)
    miss = {col: 0 for col, _ in checks}
    with open(p, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for col, target in checks:
                if row[col] not in V[target]:
                    miss[col] += 1
    orphans[fn] = miss
out["fk_orphans"] = orphans

json.dump(out, sys.stdout, indent=1)
print()
