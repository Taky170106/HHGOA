"""Final Phase 2 deliverable self-check (read-only, no invented values).

Confirms docs/PHASE2_VALIDATION_REPORT.md, docs/PHASE2_TIGERGRAPH_LOAD.md,
docs/PHASE2_REPOSITORY_MAP.md and docs/phase2_validation.json exist, parse, and that
every number in the JSON agrees with the recorded live + file-level evidence.
"""
import io, json, os, re, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DELIVERABLES = [
    "docs/PHASE2_REPOSITORY_MAP.md",
    "docs/PHASE2_TIGERGRAPH_LOAD.md",
    "docs/PHASE2_VALIDATION_REPORT.md",
    "docs/phase2_validation.json",
]

fail = []

print("=" * 74)
print("1. deliverables present")
for p in DELIVERABLES:
    ok = os.path.exists(p) and os.path.getsize(p) > 0
    print("   %-42s %s (%d bytes)" % (p, "OK" if ok else "MISSING", os.path.getsize(p) if os.path.exists(p) else 0))
    if not ok:
        fail.append("missing " + p)

rep = json.load(open("docs/phase2_validation.json", encoding="utf-8"))
fi = json.load(open("docs/phase2_file_integrity.json", encoding="utf-8"))
cnt = json.load(open("tigergraph/validation/phase2_counts.json", encoding="utf-8"))
val = json.load(open("tigergraph/validation/phase2_validate_result.json", encoding="utf-8"))

live = {}
for b in cnt["results"]:
    live.update(b)
vlive = {}
for b in val["results"]:
    vlive.update(b)

VKEY = {"@@c_customer": "Customer", "@@c_card": "Card", "@@c_txn": "Transaction",
        "@@c_device": "DeviceProfile", "@@c_email": "EmailDomain", "@@c_region": "BillingRegion",
        "@@c_closed": "ClosedCase", "@@c_bench": "BenchmarkCase"}
EKEY = {"@@e_owns": "OWNS", "@@e_made": "MADE", "@@e_next": "NEXT", "@@e_billed": "BILLED_IN",
        "@@e_purch": "PURCHASER_EMAIL", "@@e_recip": "RECIPIENT_EMAIL", "@@e_dev": "FROM_DEVICE",
        "@@e_inv": "INVOLVES", "@@e_oncard": "ON_CARD", "@@e_conn": "CONNECTED_TO", "@@e_trig": "TRIGGERS"}

print()
print("2. JSON status")
print("   phase2_validation.json status =", rep["status"])
print("   file_level_status            =", rep["file_level_status"])
print("   validation_layers.file_level      =",
      rep.get("validation_layers", {}).get("file_level", {}).get("status", "ABSENT"))
print("   validation_layers.live_tigergraph =",
      rep.get("validation_layers", {}).get("live_tigergraph", {}).get("status", "ABSENT"))
if rep["status"] != "PASS":
    fail.append("json status != PASS")

print()
print("3. vertices: JSON vs live count_all vs file scan")
for acc, name in VKEY.items():
    j = rep["vertices"][name]
    l = live[acc]
    f = fi["vertices"][name]["actual"]
    ok = j["actual"] == l == f and j["expected"] == l and j["status"] == "PASS"
    print("   %-16s expected=%-7d json=%-7d live=%-7d file=%-7d %s"
          % (name, j["expected"], j["actual"], l, f, "PASS" if ok else "FAIL"))
    if not ok:
        fail.append("vertex " + name)

print()
print("4. edges: JSON vs live count_all vs file scan")
for acc, name in EKEY.items():
    j = rep["edges"][name]
    l = live[acc]
    f = fi["edges"][name]["actual"]
    ok = j["actual"] == l == f and j["expected"] == l and j["status"] == "PASS"
    print("   %-18s expected=%-7d json=%-7d live=%-7d file=%-7d %s"
          % (name, j["expected"], j["actual"], l, f, "PASS" if ok else "FAIL"))
    if not ok:
        fail.append("edge " + name)

et = sum(rep["edges"][n]["actual"] for n in rep["edges"])
print()
print("   edge total = %d (expected 2505266) %s" % (et, "PASS" if et == 2505266 else "FAIL"))
if et != 2505266:
    fail.append("edge total")

print()
print("5. integrity")
checks = [
    ("rejected_rows", rep["rejected_rows"], 0),
    ("orphan_edges", rep["orphan_edges"], 0),
    ("duplicate_ids", rep["duplicate_ids"], 0),
    ("empty_identifiers", rep["empty_identifiers"], 0),
    ("benchmark_case_connectivity", rep["benchmark_case_connectivity"], "20/20"),
    ("count_mismatches", rep["integrity"]["count_mismatches"], []),
    ("loader total errors", rep["loader_totals"]["total_errors"], 0),
    ("loader lines == objects", rep["loader_totals"]["total_lines"] == rep["loader_totals"]["total_objects"], True),
    ("loader total == file total", rep["loader_totals"]["loader_total_equals_file_total"], True),
]
for label, got, want in checks:
    ok = got == want
    print("   %-32s = %-14s (want %-8s) %s" % (label, got, want, "PASS" if ok else "FAIL"))
    if not ok:
        fail.append(label)

print()
print("6. benchmark connectivity (live)")
print("   @@bench_total      =", vlive.get("@@bench_total"))
print("   @@bench_matched    =", vlive.get("@@bench_matched"))
print("   @@bench_unmatched  =", vlive.get("@@bench_unmatched"))
print("   cases in JSON      =", len(rep["benchmark_cases"]["cases"]))
if not (vlive.get("@@bench_matched") == 20 and vlive.get("@@bench_unmatched") == 0
        and len(rep["benchmark_cases"]["cases"]) == 20):
    fail.append("benchmark connectivity")

print()
print("7. resolved blockers recorded")
ids = [b["id"] for b in rep.get("resolved_blockers", [])]
print("   ", ids)
for need in ("B1", "B2", "B3", "D5"):
    if need not in ids:
        fail.append("blocker " + need)

print()
print("8. validation report contains required sections")
txt = open("docs/PHASE2_VALIDATION_REPORT.md", encoding="utf-8").read()
required = {
    "file-level layer distinction": "File-level",
    "live layer distinction": "Live TigerGraph layer",
    "actual vertex counts": "Actual (live)",
    "expected vs actual": "Expected |",
    "rejected rows": "Total rejected rows",
    "orphan counts": "Total orphan edges",
    "duplicate IDs": "Duplicate primary identifiers",
    "benchmark connectivity": "20 / 20 connected in the live graph",
    "integrity results": "## 7. Integrity results",
    "resolved blockers": "### 8.1 Resolved in Phase 2",
    "final status": "PHASE_2_STATUS = PASS",
    "edge total 2505266": "2,505,266",
}
for label, needle in required.items():
    ok = needle in txt
    print("   %-32s %s" % (label, "OK" if ok else "MISSING -> " + needle))
    if not ok:
        fail.append("report section: " + label)

print()
print("9. raw dataset untouched")
raw = sorted(os.listdir("DATASET"))
print("   DATASET/ files:", raw)
if len(raw) != 5:
    fail.append("DATASET file count changed")

print()
print("=" * 74)
if fail:
    print("SELF-CHECK FAIL:", fail)
    sys.exit(1)
print("SELF-CHECK PASS: all 4 deliverables present and consistent with recorded evidence")
