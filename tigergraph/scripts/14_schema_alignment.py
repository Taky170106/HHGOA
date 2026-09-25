import re, csv, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---- parse schema: attribute names + types in declared order ----
schema = open("tigergraph/schema/schema.gsql", encoding="utf-8").read()
schema = re.sub(r"//.*", "", schema)
schema = re.sub(r"/\*.*?\*/", "", schema, flags=re.S)

vert_attrs, edge_attrs = {}, {}
for m in re.finditer(r"CREATE VERTEX\s+(\w+)\s*\((.*?)\)\s*WITH", schema, re.S):
    body = m.group(2)
    names = []
    for piece in body.split(","):
        piece = piece.strip()
        mm = re.match(r"(?:PRIMARY_ID\s+)?(\w+)\s+(STRING|UINT|INT|DOUBLE|BOOL|DATETIME)", piece)
        if mm:
            names.append(mm.group(1))
    vert_attrs[m.group(1)] = names

for m in re.finditer(r"CREATE DIRECTED EDGE\s+(\w+)\s*\((.*?)\)\s*(?=CREATE|/\n|$)", schema, re.S):
    name, body = m.group(1), m.group(2)
    names = []
    if "FROM" not in body:
        continue
    after = body.split(",", 1)
    rest = after[1] if len(after) > 1 else ""
    for piece in rest.split(","):
        piece = piece.strip()
        mm = re.match(r"(\w+)\s+(STRING|UINT|INT|DOUBLE|BOOL|DATETIME)", piece)
        if mm:
            names.append(mm.group(1))
    edge_attrs[name] = names

# ---- parse loading jobs ----
def parse(path):
    txt = open(path, encoding="utf-8").read()
    txt = re.sub(r"#[^\n]*", "", txt)
    out = {}
    for m in re.finditer(r"CREATE LOADING JOB\s+(\w+).*?\{(.*?)\}", txt, re.S):
        body = m.group(2)
        fn = re.search(r'DEFINE FILENAME\s+\w+\s*=\s*"([^"]+)"', body)
        lm = re.search(r"LOAD\s+\w+\s+TO\s+(VERTEX|EDGE)\s+(\w+)\s+VALUES\s*\((.*?)\)\s*USING", body, re.S)
        if not (fn and lm):
            continue
        cols = re.findall(r'\$"(.*?)"', lm.group(3))
        using = lm.string[lm.end():]
        hdr = 'header="true"' in using or "header='true'" in using
        out[m.group(1)] = dict(kind=lm.group(1), target=lm.group(2),
                               fn=fn.group(1), cols=cols, header=hdr)
    return out

jobs = {}
jobs.update(parse("tigergraph/loading/load_vertices.gsql"))
jobs.update(parse("tigergraph/loading/load_edges.gsql"))

CSVDIR = {"VERTEX": "data/vertices", "EDGE": "data/edges"}
problems, rows = [], []

for jn, j in sorted(jobs.items()):
    p = os.path.join(CSVDIR[j["kind"]], os.path.basename(j["fn"]))
    if not os.path.exists(p):
        problems.append("missing csv: " + p)
        continue
    with open(p, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        header = next(rd)
        n = sum(1 for _ in rd)
    attr = vert_attrs[j["target"]] if j["kind"] == "VERTEX" else edge_attrs[j["target"]]
    unknown = [c for c in j["cols"] if c not in header]
    nval = len(j["cols"])
    nattr = len(attr) + (0 if j["kind"] == "VERTEX" else 0)
    ok_hdr = j["header"]
    ok = (not unknown) and ok_hdr and nval == len(attr)
    if not ok:
        problems.append("%s: unknown_cols=%s header_flag=%s n_values=%d n_schema_attrs=%d"
                        % (jn, unknown, ok_hdr, nval, len(attr)))
    rows.append((jn, j["target"], p, n, nval, len(attr), not unknown, ok))

print("%-26s %-20s %-36s %8s %5s %5s %6s %5s" % (
    "job", "target", "csv", "rows", "vals", "attrs", "hdr_ok", "OK"))
for r in rows:
    print("%-26s %-20s %-36s %8d %5d %5d %6s %5s" % r)

print()
print("PROBLEMS:", problems if problems else "NONE - all 19 jobs map 1:1 to schema + CSV headers")
