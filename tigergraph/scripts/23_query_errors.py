"""Extract the exact GSQL error locations reported by TigerGraph 4.2.5 for the
5 query files that failed to compile during Phase 2 deployment (read-only)."""
import io, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TARGETS = [
    ("benchmark_case_context", "tigergraph/queries/benchmark_case_context.gsql", 12, 42, "Syntax Error"),
    ("find_device_connections", "tigergraph/queries/find_device_connections.gsql", 24, 29, "Type Check Error TYP-152"),
    ("find_related_cases", "tigergraph/queries/find_related_cases.gsql", 17, 23, "Type Check Error TYP-111"),
    ("find_related_transactions", "tigergraph/queries/find_related_transactions.gsql", 31, 27, "Syntax Error"),
    ("get_transaction", "tigergraph/queries/get_transaction.gsql", 32, 43, "Syntax Error"),
]

for name, path, ln, col, kind in TARGETS:
    lines = open(path, encoding="utf-8").read().split("\n")
    print("=" * 76)
    print("%s  (%s)" % (name, kind))
    print("  file: %s  line %d col %d" % (path, ln, col))
    start = max(0, ln - 3)
    for i in range(start, min(len(lines), ln + 2)):
        mark = ">>" if i == ln - 1 else "  "
        print("  %s %3d: %s" % (mark, i + 1, lines[i]))
        if i == ln - 1:
            print("       %s^ col %d" % (" " * (len(str(i + 1)) + 5), col))
