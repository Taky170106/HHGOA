"""Phase 2A diagnosis: why TigerGraph rejected rows for card.csv and benchmark_case.csv.

Read-only. Evidence gathered:
  1. card.csv      - rows whose card2/card3/card5 are float-like (e.g. "189.0")
                     while schema declares UINT  -> type mismatch.
  2. quoted/comma  - rows containing '"' and rows containing ',' in values,
                     vs loader's Invalid-Attributes count (quote-handling theory).
"""
import csv, re, collections, os

csv.field_size_limit(10 ** 7)
FLOATLIKE = re.compile(r"^-?\d+\.\d+$")


def rows_with_quotes_and_commas(path, cols=None):
    tot = q = c = 0
    per_col = collections.Counter()
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            tot += 1
            vals = list(r.values())
            if any('"' in (v or "") for v in vals):
                q += 1
            if any("," in (v or "") for v in vals):
                c += 1
                for k, v in r.items():
                    if v and "," in v:
                        per_col[k] += 1
    return tot, q, c, dict(per_col)


def floatlike_report(path, ucols):
    n = anyf = 0
    per = collections.Counter()
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            n += 1
            hit = False
            for c in ucols:
                v = r.get(c, "")
                if v and FLOATLIKE.match(v):
                    per[c] += 1
                    hit = True
            if hit:
                anyf += 1
    return n, anyf, dict(per)


print("=" * 72)
print("CARD.CSV (schema: card2/card3/card5 = UINT)")
n, anyf, per = floatlike_report("data/vertices/card.csv", ["card2", "card3", "card5"])
print("  rows                        :", n)
print("  rows w/ ANY float-like UINT :", anyf)
print("  per-column float-like       :", per)
print("  loader said: Invalid=13543, Valid=10")
print("  => MATCH" if anyf == 13543 else "  => MISMATCH")

print("=" * 72)
print("BENCHMARK_CASE.CSV")
tot, q, c, per = rows_with_quotes_and_commas("data/vertices/benchmark_case.csv")
print("  rows                :", tot)
print("  rows containing '\"' :", q, " cols:", per)
print("  rows containing ',' :", c)
print("  loader said: Invalid=11, Valid=9")
print("  => MATCH" if q == 11 else "  => MISMATCH")

print("=" * 72)
print("QUOTE/COMMA THEORY CHECK ON FULLY-LOADED VERTICES")
for p, expect in [
    ("data/vertices/closed_case.csv", 5565),
    ("data/vertices/customer.csv", 13553),
    ("data/vertices/transaction.csv", 590742),
    ("data/vertices/device_profile.csv", 9706),
]:
    tot, q, c, per = rows_with_quotes_and_commas(p)
    print("  %-40s rows=%-7d quoted=%-5d comma=%-5d (loaded %d/%d OK)"
          % (os.path.basename(p), tot, q, c, expect, tot))

print("=" * 72)
print("FLOAT-LIKE VALUES IN EVERY DECLARED-UINT / DECLARED-INT COLUMN")
CHECKS = {
    "customer.csv": ["total_txns", "online_txns", "in_person_txns", "region_count"],
    "card.csv": ["card1_num", "card2", "card3", "card5"],
    "transaction.csv": ["txn_num", "dt_seconds"],
    "device_profile.csv": ["customer_count", "card_count", "txn_count"],
    "email_domain.csv": ["customer_count", "card_count", "txn_count"],
    "billing_region.csv": ["customer_count", "card_count", "txn_count"],
    "closed_case.csv": ["n_txns"],
}
for fn, cols in CHECKS.items():
    p = os.path.join("data/vertices", fn)
    if not os.path.exists(p):
        continue
    n, anyf, per = floatlike_report(p, cols)
    flag = "PROBLEM" if anyf else "clean"
    print("  %-24s rows=%-7d float-in-uint=%-7d %s %s" % (fn, n, anyf, flag, per))

# ---- edge files: declared numeric columns
print("=" * 72)
print("EDGE FILES: FLOAT-LIKE IN DECLARED-UINT COLUMNS")
EDGE_U = {
    "next.csv": ["time_delta_hours", "amount_ratio"],          # both DOUBLE -> float ok
    "made.csv": ["sequence_num"],                               # UINT
    "on_card.csv": [],
    "involves.csv": ["sequence_in_case"],                       # UINT
    "billed_in.csv": [],
    "from_device.csv": ["distance"],                            # UINT?
}
# only report files/columns that actually exist
for fn in sorted(os.listdir("data/edges")):
    if not fn.endswith(".csv"):
        continue
    p = os.path.join("data/edges", fn)
    with open(p, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        hdr = r.fieldnames
    # find columns declared UINT in the edge loading jobs
    cols = [c for c in hdr if c in ("sequence_num", "sequence_in_case", "distance",
                                    "duration_seconds", "first_seen", "last_seen")]
    if not cols:
        continue
    n, anyf, per = floatlike_report(p, cols)
    print("  %-22s rows=%-7d float-in-uint=%-7d %s %s"
          % (fn, n, anyf, "PROBLEM" if anyf else "clean", per))
print("done")
