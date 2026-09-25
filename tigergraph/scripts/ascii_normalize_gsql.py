"""Normalize GSQL files to ASCII-only text.

Why: TigerGraph CE 4.2.5 gsql file-mode silently executes NOTHING (exit 0, no error)
when a non-ASCII byte (e.g. em-dash U+2014) appears anywhere in the file, including
inside // comments. Verified 2026-09-25 against hhg-tigergraph.

This only rewrites comment text (em-dash -> '-'); GSQL statements/semantics unchanged.
Idempotent: running twice produces identical output.
"""
import os, sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tigergraph")
if not os.path.isdir(ROOT):
    ROOT = "tigergraph"

MAPPING = {
    "\u2014": "-",   # em dash
    "\u2013": "-",   # en dash
    "\u2192": "->",  # right arrow
    "\u2190": "<-",  # left arrow
    "\u2018": "'", "\u2019": "'",   # smart quotes
    "\u201c": '"', "\u201d": '"',
    "\u00a0": " ",   # nbsp
}

def normalize(text: str) -> str:
    for k, v in MAPPING.items():
        text = text.replace(k, v)
    # any remaining non-ASCII -> '?' (should not happen; reported for safety)
    return text

changed = []
for root, dirs, files in os.walk(ROOT):
    for fn in sorted(files):
        if not fn.endswith(".gsql"):
            continue
        p = os.path.join(root, fn)
        raw = open(p, "rb").read()
        txt = raw.decode("utf-8")
        new = normalize(txt)
        new_bytes = new.encode("utf-8")
        if new_bytes != raw:
            open(p, "wb").write(new_bytes)
            non_ascii_before = sum(1 for c in raw if c > 127)
            changed.append((p, non_ascii_before))

if changed:
    print("NORMALIZED (comment text only, GSQL semantics unchanged):")
    for p, n in changed:
        print(f"  {p}: {n} non-ascii bytes -> ascii")
else:
    print("No changes needed (already ASCII).")

# report any remaining non-ascii
bad = []
for root, dirs, files in os.walk(ROOT):
    for fn in sorted(files):
        if fn.endswith(".gsql"):
            p = os.path.join(root, fn)
            n = sum(1 for c in open(p, "rb").read() if c > 127)
            if n:
                bad.append((p, n))
print("REMAINING NON-ASCII:", bad if bad else "none")
sys.exit(0)
