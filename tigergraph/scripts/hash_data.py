"""Hash all graph data files (data/vertices, data/edges) -> deterministic baseline/scope check.
Usage: python tigergraph/scripts/hash_data.py [outfile]
"""
import hashlib, os, sys, json

OUT = sys.argv[1] if len(sys.argv) > 1 else "tigergraph/validation/data_hashes.json"

def h(p):
    d = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()

res = {}
for sub in ("vertices", "edges"):
    base = os.path.join("data", sub)
    for fn in sorted(os.listdir(base)):
        if fn.endswith(".csv"):
            res[f"{sub}/{fn}"] = h(os.path.join(base, fn))

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(res, f, indent=2, sort_keys=True)
print(f"wrote {OUT}: {len(res)} files")
