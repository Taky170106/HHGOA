"""Verify aggregate loader totals quoted in docs/PHASE2_VALIDATION_REPORT.md.

Reads tigergraph/validation/phase2_load.log (real RUN LOADING JOB output) and
docs/phase2_file_integrity.json (real file scan) and prints the sums.
"""
import io, json, os, re, sys, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

LOADLOG = "tigergraph/validation/phase2_load.log"
FI = "docs/phase2_file_integrity.json"

pat = re.compile(r"\|\s*(?:\S*/)?(vertices|edges)/(\S+\.csv)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|")

rows = {}
for line in open(LOADLOG, encoding="utf-8", errors="replace"):
    m = pat.search(line)
    if not m:
        continue
    key = "%s/%s" % (m.group(1), m.group(2))
    lines, objs, errs = int(m.group(3)), int(m.group(4)), int(m.group(5))
    cur = rows.get(key)
    if cur is None or lines > cur[0]:
        rows[key] = (lines, objs, errs)

print("loader jobs parsed from log: %d" % len(rows))
tot_lines = sum(v[0] for v in rows.values())
tot_objs = sum(v[1] for v in rows.values())
tot_errs = sum(v[2] for v in rows.values())
print("  TOTAL LINES    = %d" % tot_lines)
print("  TOTAL OBJECTS  = %d" % tot_objs)
print("  TOTAL ERRORS   = %d" % tot_errs)
bad = [k for k, v in rows.items() if v[0] != v[1] or v[2] != 0]
print("  files with LINES != OBJECTS or ERRORS > 0:", bad if bad else "NONE")
print()
for k in sorted(rows):
    v = rows[k]
    print("  %-40s lines=%-8d objects=%-8d errors=%d" % (k, v[0], v[1], v[2]))

fi = json.load(open(FI, encoding="utf-8"))
v_rows = sum(fi["vertices"][n]["actual"] for n in fi["vertices"])
e_rows = sum(fi["edges"][n]["actual"] for n in fi["edges"])
print()
print("file-level vertex rows total = %d" % v_rows)
print("file-level edge rows total   = %d" % e_rows)
print("file-level grand total       = %d" % (v_rows + e_rows))
print("match loader total           =", (v_rows + e_rows) == tot_lines)
