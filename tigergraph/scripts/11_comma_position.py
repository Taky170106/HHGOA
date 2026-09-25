"""Phase 2A: comma-bearing columns and their positional index (quote-handling hazard).

If TigerGraph's loader ignores RFC4180 quoting, an embedded comma inside a
NON-LAST column shifts all following columns -> type-invalid attribute.
A comma in the LAST column only overflows past the mapped fields -> silently OK.
"""
import csv, os, collections

csv.field_size_limit(10 ** 7)

FILES = ["benchmark_case.csv", "closed_case.csv", "customer.csv", "transaction.csv",
         "device_profile.csv", "billing_region.csv", "email_domain.csv", "card.csv",
         "card_mapping.csv"]

print("=== VERTEX FILES: columns containing ',' ===")
for fn in FILES:
    p = os.path.join("data/vertices", fn)
    if not os.path.exists(p):
        continue
    per = collections.Counter()
    n = 0
    with open(p, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        hdr = r.fieldnames
        for row in r:
            n += 1
            for k, v in row.items():
                if v and "," in v:
                    per[k] += 1
    detail = [(k, hdr.index(k), len(hdr)) for k in per]
    hazard = [k for k, i, t in detail if i < t - 1]
    print("  %-22s rows=%-7d cols_with_comma=%s" % (fn, n, detail))
    print("      -> NON-LAST (hazard): %s" % (hazard if hazard else "none"))

print()
print("=== EDGE FILES: columns containing ',' ===")
for fn in sorted(os.listdir("data/edges")):
    if not fn.endswith(".csv"):
        continue
    p = os.path.join("data/edges", fn)
    per = collections.Counter()
    n = 0
    with open(p, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        hdr = r.fieldnames
        for row in r:
            n += 1
            for k, v in row.items():
                if v and "," in v:
                    per[k] += 1
    if per:
        detail = [(k, hdr.index(k), len(hdr)) for k in per]
        hazard = [k for k, i, t in detail if i < t - 1]
        print("  %-22s rows=%-7d cols_with_comma=%s -> NON-LAST: %s"
              % (fn, n, detail, hazard if hazard else "none"))
    else:
        print("  %-22s rows=%-7d no commas" % (fn, n))
