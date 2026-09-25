"""Phase 2 blocker evidence (read-only).

B1: are card2/card3/card5 integral in the RAW source, and in the derived card.csv?
B2/B3: which graph CSVs contain double-quote characters at all?
"""
import csv, io, re, sys, os, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
csv.field_size_limit(10 ** 7)

INTEGRAL = re.compile(r"^\d+\.0*$")
FLOATLIKE = re.compile(r"^-?\d+\.\d+$")


def scan(path, cols):
    stat = {c: collections.Counter() for c in cols}
    n = 0
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        rd = csv.DictReader(f)
        for row in rd:
            n += 1
            for c in cols:
                v = (row.get(c) or "").strip()
                if v == "":
                    stat[c]["empty"] += 1
                elif INTEGRAL.match(v):
                    stat[c]["integral_like_189.0"] += 1
                elif FLOATLIKE.match(v):
                    stat[c]["NON_INTEGRAL:" + v] += 1
                else:
                    stat[c]["other:" + v] += 1
    return n, stat


print("=" * 74)
print("B1 - card2/card3/card5 value shapes")
for label, path in (("RAW DATASET/transactions.csv", "DATASET/transactions.csv"),
                    ("DERIVED data/vertices/card.csv", "data/vertices/card.csv")):
    if not os.path.exists(path):
        print("  MISSING", path)
        continue
    cols = [c for c in ("card2", "card3", "card5")
            if c in next(csv.reader(open(path, newline="", encoding="utf-8")))]
    n, stat = scan(path, cols)
    print("  %-32s rows=%d" % (label, n))
    for c in cols:
        print("     %-7s %s" % (c, dict(stat[c])))

print()
print("=" * 74)
print("B2/B3 - double-quote characters per graph CSV")
for sub in ("vertices", "edges"):
    for fn in sorted(os.listdir("data/" + sub)):
        if not fn.endswith(".csv"):
            continue
        p = "data/%s/%s" % (sub, fn)
        raw = open(p, "rb").read()
        dq = raw.count(b'"')
        # rows where a quote appears anywhere
        rows_q = sum(1 for ln in raw.split(b"\n") if b'"' in ln)
        if dq:
            print("  %-40s double_quotes=%6d rows_with_quote=%d" % (p, dq, rows_q))
print("  (files not listed contain no double-quote bytes at all)")

print()
print("=" * 74)
print("raw source files quote scan")
for p in ("DATASET/closed_cases_history.csv", "DATASET/case_pack.csv"):
    if os.path.exists(p):
        raw = open(p, "rb").read()
        print("  %-40s double_quotes=%d rows_with_quote=%d"
              % (p, raw.count(b'"'), sum(1 for ln in raw.split(b"\n") if b'"' in ln)))
