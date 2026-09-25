"""Phase 3 - live MCP validation.

Asserts every investigation tool executes an INSTALLED GSQL query on the live
TigerGraph CE 4.2.5 instance (source.kind == tigergraph_live) and returns real
graph data. Read-only: only GET /query/<graph>/<query> is issued.
"""
import os, sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

os.environ.update({
    "TG_HOST": "http://localhost", "TG_RESTPP_PORT": "9000",
    "TG_USERNAME": "tigergraph", "TG_PASSWORD": "tigergraph",
    "TG_GRAPHNAME": "hhg_fraud_graph",
})
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.tools import transaction_tools as tt
from mcp.tools import relationship_tools as rt
from mcp.tools import case_tools as ct
from mcp.tools import history_tools as ht
from mcp.tools._common import is_allowed

CASES = [
    ("get_transaction", lambda: tt.get_transaction("3000120")),
    ("find_related_transactions", lambda: rt.find_related_transactions(
        txn_id="3000120", max_hops=2, limit=50)),
    ("find_device_connections", lambda: rt.find_device_connections(txn_id="3000001")),
    ("find_related_cases", lambda: ht.find_related_cases(card_id="C00259-K1")),
    ("benchmark_case_context", lambda: ct.benchmark_case_context("HHG-001")),
    ("get_card_history", lambda: tt.get_card_history("C00259-K1")),
    ("get_customer_history", lambda: tt.get_customer_history("C00259")),
]


def blocks(env):
    data = env.get("data") or {}
    return len(data.get("results", [])) if isinstance(data, dict) else 0


print("=" * 74)
print("MCP LIVE VALIDATION (installed GSQL over RESTPP)")
print("=" * 74)
results, live = [], 0
for name, fn in CASES:
    t0 = time.time()
    try:
        env = fn()
    except Exception as e:
        results.append({"tool": name, "ok": False, "error": f"{type(e).__name__}: {e}"})
        print(f"  [FAIL] {name:26s} EXCEPTION {e}")
        continue
    ms = round((time.time() - t0) * 1000, 1)
    status = env.get("status")
    kind = (env.get("source") or {}).get("kind")
    n = blocks(env)
    ok = status == "success"
    is_live = kind == "tigergraph_live" and ok
    live += 1 if is_live else 0
    results.append({"tool": name, "status": status, "source_kind": kind,
                    "latency_ms": ms, "result_blocks": n, "live": is_live,
                    "error": env.get("message") if not ok else ""})
    print(f"  [{'LIVE' if is_live else '----'}] {name:26s} {status} kind={kind} "
          f"blocks={n} {ms}ms")

print(f"\n  LIVE={live}/{len(CASES)}")

print("\n" + "=" * 74)
print("INVALID / NOT-FOUND INPUT")
print("=" * 74)
inv = []
for label, fn in [("bogus txn_id", lambda: tt.get_transaction("999999999")),
                  ("bogus case_id", lambda: ct.benchmark_case_context("HHG-999")),
                  ("empty card_id", lambda: tt.get_card_history("")),
                  ("empty seeds", lambda: rt.find_related_transactions())]:
    try:
        env = fn()
        code = env.get("error_code")
        handled = env.get("status") == "error" and code in ("NOT_FOUND", "INVALID_INPUT")
        inv.append({"case": label, "handled": handled, "error_code": code,
                    "source_kind": (env.get("source") or {}).get("kind"),
                    "message": env.get("message")})
        print(f"  {'OK  ' if handled else 'FAIL'} {label:16s} code={code} "
              f"kind={(env.get('source') or {}).get('kind')}")
    except Exception as e:
        inv.append({"case": label, "handled": False, "error": str(e)})
        print(f"  FAIL {label:16s} {e}")

print("\n" + "=" * 74)
print("POLICY ALLOWLIST / READ-ONLY")
print("=" * 74)
allowed, denied = [], []
# The 9 tool names enforced by mcp/config/tool_policy.yaml (calculate_exposure_list
# is a GSQL query, not a separate MCP tool).
for t in ["get_transaction", "find_related_transactions", "find_device_connections",
          "find_related_cases", "benchmark_case_context", "get_card_history",
          "get_customer_history", "temporal_chain", "calculate_exposure"]:
    (allowed if is_allowed(t) else denied).append(t)
DANGEROUS = ["drop_graph", "run_gsql", "insert_vertex", "delete_edge", "load_csv"]
blocked = [t for t in DANGEROUS if not is_allowed(t)]
for t in DANGEROUS:
    (denied if t in blocked else allowed).append(t)
print(f"  allowed investigation tools: {len(allowed)}/9")
print(f"  refused dangerous tools      : {blocked} ({len(blocked)}/{len(DANGEROUS)})")

out = {"live_total": len(CASES), "live_pass": live, "cases": results, "invalid": inv,
       "policy_allowed": sorted(set(allowed)), "policy_denied": sorted(set(denied)),
       "dangerous_blocked": blocked,
       "status": "PASS" if (live == len(CASES)
                            and all(i.get("handled") for i in inv)
                            and len(blocked) == len(DANGEROUS)) else "FAIL"}
p = r"D:\HHG\mcp\validation\phase3_mcp_live.json"
with open(p, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print(f"\n  MCP_STATUS = {out['status']}")
print(f"  WROTE {p}")
