"""Phase 2 file-level integrity scan of the graph-ready dataset.

Independent of tigergraph/scripts/build_graph_data.py (whose check_orphans()
omits ON_CARD - discrepancy D5 in docs/DATASET_DISCOVERY.md).

Checks, for data/vertices/*.csv + data/edges/*.csv:
  * row counts, column counts, headers
  * duplicate / missing / empty primary identifiers (8 vertex types)
  * orphan endpoints on all 11 edge types (both source and target)
  * duplicate relationships (same from/to pair twice in one edge type)
  * benchmark case connectivity: HHG-001..HHG-020 -> flagged txn -> TRIGGERS edge
  * expected vs actual edge totals

Writes docs/phase2_file_integrity.json (machine-readable).
"""
import csv, io, json, os, sys, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
csv.field_size_limit(10 ** 7)

VERT = "data/edges"  # placeholder, corrected below
VDIR, EDIR = "data/vertices", "data/edges"
OUT = "docs/phase2_file_integrity.json"

VERTEX_PK = {
    "customer.csv": "customer_id",
    "card.csv": "card_id",
    "transaction.csv": "txn_id",
    "device_profile.csv": "device_profile_id",
    "email_domain.csv": "domain",
    "billing_region.csv": "region_code",
    "closed_case.csv": "case_id",
    "benchmark_case.csv": "case_id",
}
VERTEX_NAME = {
    "customer.csv": "Customer", "card.csv": "Card", "transaction.csv": "Transaction",
    "device_profile.csv": "DeviceProfile", "email_domain.csv": "EmailDomain",
    "billing_region.csv": "BillingRegion", "closed_case.csv": "ClosedCase",
    "benchmark_case.csv": "BenchmarkCase",
}
# edge file -> (edge type, source vertex, source col, target vertex, target col, from col, to col)
EDGES = {
    "owns.csv": ("OWNS", "Customer", "card.csv", "Card", "from_customer_id", "to_card_id"),
    "made.csv": ("MADE", "Card", None, "Transaction", "from_card_id", "to_txn_id"),
    "next.csv": ("NEXT", "Transaction", None, "Transaction", "from_txn_id", "to_txn_id"),
    "billed_in.csv": ("BILLED_IN", "Transaction", None, "BillingRegion", "from_txn_id", "to_region_code"),
    "purchaser_email.csv": ("PURCHASER_EMAIL", "Transaction", None, "EmailDomain", "from_txn_id", "to_domain"),
    "recipient_email.csv": ("RECIPIENT_EMAIL", "Transaction", None, "EmailDomain", "from_txn_id", "to_domain"),
    "from_device.csv": ("FROM_DEVICE", "Transaction", None, "DeviceProfile", "from_txn_id", "to_device_profile_id"),
    "involves.csv": ("INVOLVES", "ClosedCase", None, "Transaction", "from_case_id", "to_txn_id"),
    "on_card.csv": ("ON_CARD", "ClosedCase", None, "Card", "from_case_id", "to_card_id"),
    "connected_to.csv": ("CONNECTED_TO", "ClosedCase", None, "Card", "from_case_id", "to_card_id"),
    "triggers.csv": ("TRIGGERS", "BenchmarkCase", None, "Transaction", "from_case_id", "to_txn_id"),
}
EXPECTED_VERTICES = {
    "Customer": 13553, "Card": 13553, "Transaction": 590742, "DeviceProfile": 9706,
    "EmailDomain": 60, "BillingRegion": 332, "ClosedCase": 5565, "BenchmarkCase": 20,
}
# Phase 1 documented edge totals (actual sum of the 11 files, not the stale 2,499,760)
EXPECTED_EDGES = None  # filled from files; reported against Phase 1 recomputed total


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        header = next(rd)
        rows = list(rd)
    return header, rows


report = {"phase": "2", "scope": "file_level",
          "vertices": {}, "edges": {}, "integrity": {}, "benchmark_cases": {}}

print("=" * 78)
print("VERTICES")
pk_sets = {}
bad = []
for fn, pk in VERTEX_PK.items():
    p = os.path.join(VDIR, fn)
    header, rows = read_rows(p)
    i = header.index(pk)
    vals = [r[i] if i < len(r) else "" for r in rows]
    empties = sum(1 for v in vals if v == "")
    dupes = [v for v, c in collections.Counter(vals).items() if c > 1]
    short = sum(1 for r in rows if len(r) != len(header))
    name = VERTEX_NAME[fn]
    exp = EXPECTED_VERTICES[name]
    ok = len(rows) == exp and not dupes and empties == 0 and short == 0
    pk_sets[name] = set(vals)
    report["vertices"][name] = {
        "file": p, "expected": exp, "actual": len(rows), "diff": len(rows) - exp,
        "columns": len(header), "header": header, "duplicate_pk": len(dupes),
        "empty_pk": empties, "malformed_rows": short, "status": "PASS" if ok else "FAIL",
    }
    if not ok:
        bad.append(name)
    print("  %-16s exp=%-7d act=%-7d dup=%d empty=%d malformed=%d  %s"
          % (name, exp, len(rows), len(dupes), empties, short, "PASS" if ok else "FAIL"))
    if dupes:
        print("      duplicate PKs:", dupes[:5])

print()
print("EDGES (file level: both endpoints must exist in vertex PK sets)")
total_e = 0
orph_summary = {}
for fn, (etype, sv, _sfile, tv, c_from, c_to) in EDGES.items():
    p = os.path.join(EDIR, fn)
    header, rows = read_rows(p)
    try:
        fi, ti = header.index(c_from), header.index(c_to)
    except ValueError:
        print("  %-18s MISSING COLUMN %s/%s" % (etype, c_from, c_to))
        continue
    srcs = [r[fi] for r in rows]
    tgts = [r[ti] for r in rows]
    o_src = sum(1 for v in srcs if v not in pk_sets[sv])
    o_tgt = sum(1 for v in tgts if v not in pk_sets[tv])
    pairs = collections.Counter(zip(srcs, tgts))
    dup_rel = sum(1 for k, c in pairs.items() if c > 1)
    short = sum(1 for r in rows if len(r) != len(header))
    orphans = o_src + o_tgt
    total_e += len(rows)
    ok = orphans == 0 and dup_rel == 0 and short == 0
    report["edges"][etype] = {
        "file": p, "actual": len(rows), "source_vertex": sv, "target_vertex": tv,
        "orphan_source": o_src, "orphan_target": o_tgt, "orphan_total": orphans,
        "duplicate_relationships": dup_rel, "malformed_rows": short,
        "columns": header, "status": "PASS" if ok else "FAIL",
    }
    orph_summary[etype] = orphans
    print("  %-18s rows=%-8d orphan_src=%-6d orphan_tgt=%-6d dup_rel=%d malformed=%d  %s"
          % (etype, len(rows), o_src, o_tgt, dup_rel, short, "PASS" if ok else "FAIL"))
    if orphans:
        distinct = sorted({v for v in (srcs + tgts) if v not in pk_sets[sv]} if o_src
                          else {v for v in tgts if v not in pk_sets[tv]})
        print("      missing target ids (%d distinct): %s" % (len(distinct), distinct[:8]))

report["edges_total"] = total_e
print()
print("  edge total (sum of 11 files) = %d" % total_e)
print("  stale published total        = 2499760  -> delta %+d" % (total_e - 2499760))

# ---- duplicate / missing ids summary
report["integrity"] = {
    "duplicate_ids": sum(report["vertices"][v]["duplicate_pk"] for v in report["vertices"]),
    "empty_ids": sum(report["vertices"][v]["empty_pk"] for v in report["vertices"]),
    "malformed_rows": sum(report["vertices"][v]["malformed_rows"] for v in report["vertices"])
                      + sum(report["edges"][e]["malformed_rows"] for e in report["edges"]),
    "orphan_edges": sum(orph_summary.values()),
    "orphan_edges_by_type": orph_summary,
    "duplicate_relationships": sum(report["edges"][e]["duplicate_relationships"] for e in report["edges"]),
}

# ---- benchmark connectivity
print()
print("BENCHMARK CASES HHG-001..HHG-020")
_, brows = read_rows(os.path.join(VDIR, "benchmark_case.csv"))
_, trows = read_rows(os.path.join(EDIR, "triggers.csv"))
_, vrows = read_rows(os.path.join(VDIR, "benchmark_case.csv"))
bheader, brows = read_rows(os.path.join(VDIR, "benchmark_case.csv"))
fi_tx = bheader.index("flagged_txn_id")
fi_id = bheader.index("case_id")
th = [r for r in trows]
trig = {(r[0], r[1]) for r in th}
bench_ok = 0
details = []
for i in range(1, 21):
    cid = "HHG-%03d" % i
    row = [r for r in brows if r[fi_id] == cid]
    if not row:
        details.append({"case_id": cid, "vertex": False, "status": "FAIL"})
        continue
    txn = row[0][fi_tx]
    vtx = txn in pk_sets["Transaction"]
    edge = (cid, txn) in trig
    st = "PASS" if (vtx and edge) else "FAIL"
    if st == "PASS":
        bench_ok += 1
    details.append({"case_id": cid, "vertex": True, "trigger_txn_id": txn,
                    "trigger_txn_exists": vtx, "triggers_edge": edge, "status": st})
    print("  %s vertex=Y txn=%-9s txn_exists=%s edge=%s  %s"
          % (cid, txn, vtx, edge, st))
report["benchmark_cases"] = {
    "expected": 20, "connected": bench_ok, "status": "PASS" if bench_ok == 20 else "FAIL",
    "cases": details,
}
print("  connected %d/20" % bench_ok)

# ---- overall
fails = [k for k in report["vertices"] if report["vertices"][k]["status"] == "FAIL"]
fails += [k for k in report["edges"] if report["edges"][k]["status"] == "FAIL"]
if report["benchmark_cases"]["status"] != "PASS":
    fails.append("BENCHMARK")
report["status"] = "PASS" if not fails else "FAIL"
report["failures"] = fails

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, sort_keys=False)
    f.write("\n")
print()
print("file-level status =", report["status"], "failures =", fails)
print("wrote", OUT)
