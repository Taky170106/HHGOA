"""Phase 2 pre-load diagnostics (read-only).

1. Per-row column counts for the two comma-bearing vertex CSVs (quoting intact?)
2. Raw bytes of a comma-bearing closed_case row (is the field quoted?)
3. Which graph CSV cells are quoted at all
4. GSQL schema attribute types vs loading-job columns vs actual CSV headers
"""
import csv, os, re, sys, io, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
csv.field_size_limit(10 ** 7)

print("=" * 72)
print("1. per-row column counts")
for p in ("data/vertices/closed_case.csv", "data/vertices/benchmark_case.csv"):
    c = collections.Counter()
    with open(p, newline="", encoding="utf-8") as f:
        for i, r in enumerate(csv.reader(f)):
            if i == 0:
                hdr = len(r)
                continue
            c[len(r)] += 1
    print("  %-40s header=%d row_distribution=%s" % (p, hdr, dict(c)))

print("=" * 72)
print("2. raw bytes of comma-bearing rows")
raw = open("data/vertices/closed_case.csv", "rb").read()
for ln in raw.split(b"\r\n"):
    if ln.startswith(b"CC-0002,"):
        i = ln.rfind(b",")
        print("  CC-0002 tail bytes:", ln[-120:])
        print("  notes field starts with quote:", b',"Case ' in ln)
        break
raw2 = open("data/vertices/benchmark_case.csv", "rb").read()
for ln in raw2.split(b"\r\n"):
    if ln.startswith(b"HHG-001,"):
        print("  HHG-001 bytes:", ln[:140])
        break

print("=" * 72)
print("3. quoted cells per graph CSV")
for sub in ("vertices", "edges"):
    for fn in sorted(os.listdir("data/" + sub)):
        if not fn.endswith(".csv"):
            continue
        p = "data/%s/%s" % (sub, fn)
        n = q = 0
        with open(p, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                n += 1
                if n == 1:
                    continue
                if any(cell.startswith('"') for cell in row):
                    q += 1
        if q:
            print("  %-45s rows_with_quoted_cell=%d" % (p, q))
print("  (files not listed have zero quoted cells)")

print("=" * 72)
print("4. schema vs loading job vs CSV header")

# --- parse schema.gsql
schema = open("tigergraph/schema/schema.gsql", encoding="utf-8").read()
schema = re.sub(r"//[^\n]*", "", schema)
schema = re.sub(r"/\*.*?\*/", "", schema, flags=re.S)

def parse_block(kind, text):
    out = {}
    for m in re.finditer(r"CREATE %s\s+(\w+)\s*\((.*?)\)" % kind, text, re.S):
        name, body = m.group(1), m.group(2)
        attrs = []
        for line in body.split(","):
            line = line.strip()
            if not line:
                continue
            mm = re.match(r"(PRIMARY_ID\s+)?(\w+)\s+(STRING|UINT|INT|DOUBLE|BOOL|DATETIME|FLOAT)", line)
            if mm:
                attrs.append((mm.group(2), mm.group(3), bool(mm.group(1))))
        out[name] = attrs
    return out

verts = parse_block("VERTEX", schema)
edges = {}
for m in re.finditer(r"CREATE DIRECTED EDGE\s+(\w+)\s*\((.*?)\)", schema, re.S):
    name, body = m.group(1), m.group(2)
    attrs = []
    for line in body.split(","):
        line = line.strip()
        mm = re.match(r"(FROM|TO)\s+(\w+)", line)
        if not mm:
            mm2 = re.match(r"(\w+)\s+(STRING|UINT|INT|DOUBLE|BOOL|DATETIME|FLOAT)", line)
            if mm2:
                attrs.append((mm2.group(1), mm2.group(2)))
    edges[name] = attrs
print("  schema vertices:", len(verts), sorted(verts))
print("  schema edges   :", len(edges), sorted(edges))

# --- parse loading jobs
def parse_jobs(path):
    txt = open(path, encoding="utf-8").read()
    txt = re.sub(r"#[^\n]*", "", txt)
    jobs = {}
    for m in re.finditer(r"CREATE LOADING JOB\s+(\w+).*?\{(.*?)\}", txt, re.S):
        jname, body = m.group(1), m.group(2)
        fm = re.search(r'DEFINE FILENAME\s+\w+\s*=\s*"([^"]+)"', body)
        lm = re.search(r"LOAD\s+\w+\s+TO\s+(VERTEX|EDGE)\s+(\w+)\s+VALUES\s*\((.*?)\)\s*USING", body, re.S)
        if fm and lm:
            cols = re.findall(r'\$"(.*?)"', lm.group(3))
            jobs[jname] = (lm.group(1), lm.group(2), fm.group(1), cols)
    return jobs

jobs = {}
jobs.update(parse_jobs("tigergraph/loading/load_vertices.gsql"))
jobs.update(parse_jobs("tigergraph/loading/load_edges.gsql"))
print("  loading jobs:", len(jobs))

VLOAD = {  # job -> vertex csv
    "load_customer": "customer.csv", "load_card": "card.csv",
    "load_transaction": "transaction.csv", "load_device_profile": "device_profile.csv",
    "load_email_domain": "email_domain.csv", "load_billing_region": "billing_region.csv",
    "load_closed_case": "closed_case.csv", "load_benchmark_case": "benchmark_case.csv",
}
ELOAD = {
    "load_owns": "owns.csv", "load_made": "made.csv", "load_next": "next.csv",
    "load_billed_in": "billed_in.csv", "load_purchaser_email": "purchaser_email.csv",
    "load_recipient_email": "recipient_email.csv", "load_from_device": "from_device.csv",
    "load_involves": "involves.csv", "load_on_card": "on_card.csv",
    "load_connected_to": "connected_to.csv", "load_triggers": "triggers.csv",
}

problems = []
for jn, csvf in list(VLOAD.items()) + list(ELOAD.items()):
    if jn not in jobs:
        problems.append("MISSING JOB: " + jn)
        continue
    kind, target, path, cols = jobs[jn]
    sub = "vertices" if kind == "VERTEX" else "edges"
    p = "data/%s/%s" % (sub, csvf)
    with open(p, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    # schema attribute names (primary id included for vertices)
    if kind == "VERTEX":
        sch = [a[0] for a in verts[target]]
        types = {a[0]: a[1] for a in verts[target]}
    else:
        sch = [a[0] for a in edges[target]]
        types = {a[0]: a[1] for a in edges[target]}
    ok_cols = cols == header
    ok_sch = (cols == sch) if kind == "VERTEX" else (cols[2:] == sch if len(cols) > 2 else sch == [])
    # vertices: loading cols must equal schema attr order
    status = "OK" if (ok_cols and (kind == "VERTEX" and cols == sch or kind == "EDGE")) else "CHECK"
    print("  %-24s -> %-22s %-18s cols_match_header=%s schema_match=%s"
          % (jn, target, csvf, ok_cols, ok_sch if kind == "VERTEX" else "n/a"))
    if not ok_cols:
        problems.append("%s: job cols != header" % jn)
    if kind == "VERTEX" and cols != sch:
        problems.append("%s: job cols != schema attrs (%s vs %s)" % (jn, cols, sch))
    if not os.path.exists(p):
        problems.append("MISSING CSV: " + p)

print("=" * 72)
print("PROBLEMS:", problems if problems else "none - all 19 CSVs map to 8 vertices + 11 edges")
