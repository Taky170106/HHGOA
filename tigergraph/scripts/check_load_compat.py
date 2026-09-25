"""Pre-load compatibility check: CSV headers/dtypes vs schema.gsql expectations.
Read-only. Reports: headers, empty cells per column, datetime samples, bool value sets.
"""
import csv, os, sys, collections

V = "data/vertices"
E = "data/edges"

def profile(path, max_rows=None):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r)
        empties = collections.Counter()
        bools = collections.defaultdict(set)
        dt_samples = collections.defaultdict(list)
        n = 0
        for row in r:
            n += 1
            for i, v in enumerate(row):
                if v == "":
                    empties[header[i]] += 1
                elif header[i] in ("ts", "opened_at", "closed_at", "first_ts", "last_ts") and len(dt_samples[header[i]]) < 3:
                    dt_samples[header[i]].append(v)
                elif header[i] in ("is_home_region", "report_filed", "is_home_country", "channel_change",
                                   "is_first_fraud", "is_home", "flagged"):
                    bools[header[i]].add(v)
            if max_rows and n >= max_rows:
                break
    return header, n, empties, bools, dt_samples

print("==== VERTICES ====")
for fn in sorted(os.listdir(V)):
    if not fn.endswith(".csv"):
        continue
    h, n, empties, bools, dts = profile(os.path.join(V, fn))
    print(f"\n-- {fn}: rows={n}")
    print(f"   header={h}")
    if empties:
        print(f"   EMPTY cells: {dict(empties)}")
    for k, v in bools.items():
        print(f"   bool {k}: {sorted(v)}")
    for k, v in dts.items():
        print(f"   dt {k}: {v}")

print("\n==== EDGES ====")
for fn in sorted(os.listdir(E)):
    if not fn.endswith(".csv"):
        continue
    h, n, empties, bools, dts = profile(os.path.join(E, fn), max_rows=200000)
    print(f"\n-- {fn}: rows(sampled)={n} header={h}")
    if empties:
        print(f"   EMPTY cells(sample): {dict(empties)}")
    for k, v in bools.items():
        print(f"   bool {k}: {sorted(v)}")
