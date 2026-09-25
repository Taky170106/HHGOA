import re, csv, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

txt = open("tigergraph/loading/load_vertices.gsql", encoding="utf-8").read()
txt = re.sub(r"#[^\n]*", "", txt)
jobs = re.findall(r"CREATE LOADING JOB\s+(\w+).*?\{(.*?)\}", txt, re.S)

FILES = {
    "load_device_profile": "data/vertices/device_profile.csv",
    "load_closed_case": "data/vertices/closed_case.csv",
    "load_card": "data/vertices/card.csv",
}

for name, body in jobs:
    if name not in FILES:
        continue
    vals = re.search(r"VALUES\s*\((.*?)\)\s*USING", body, re.S).group(1)
    cols = re.findall(r'\$"(.*?)"', vals)
    header = next(csv.reader(open(FILES[name], newline="", encoding="utf-8")))
    print(name)
    print("  job cols :", cols)
    print("  csv header:", header)
    print("  same order:", cols == header)
    print()
