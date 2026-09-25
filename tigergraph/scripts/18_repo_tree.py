"""Emit a directory tree + file counts for docs/PHASE2_REPOSITORY_MAP.md."""
import os, io, sys, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EXCLUDE_DIRS = {
    ".git", "__pycache__", ".pytest_cache", "node_modules",
    "blobs", "tigergraph-4.2.5-community", "DockerDesktopWSL",
    "app",  # only under tigergraph container paths - handled below
}
MAX_DEPTH = 3

counts = collections.Counter()


def walk(path, prefix="", depth=0):
    if depth > MAX_DEPTH:
        return
    try:
        entries = sorted(os.listdir(path), key=lambda s: (s.lower()))
    except PermissionError:
        return
    dirs, files = [], []
    for e in entries:
        full = os.path.join(path, e)
        if os.path.isdir(full):
            if e in EXCLUDE_DIRS or e == "__pycache__":
                continue
            dirs.append(e)
        else:
            files.append(e)
    # combine, dirs first
    shown = dirs + files
    for i, e in enumerate(shown):
        last = i == len(shown) - 1
        branch = "`-- " if last else "|   "
        full = os.path.join(path, e)
        if os.path.isdir(full):
            print(prefix + branch + e + "/")
            walk(full, prefix + ("    " if last else "|   "), depth + 1)
        else:
            counts[os.path.splitext(e)[1] or "(none)"] += 1
            print(prefix + branch + e)


print("D:/HHG/")
walk(".")
print()
print("== file counts by extension (excl. excluded dirs) ==")
for ext, n in counts.most_common():
    print("  %-14s %d" % (ext, n))
