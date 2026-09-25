"""Diagnose why MCP tools return status=error in tigergraph_live mode."""
import os, sys, io, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# repo root first, so the local mcp/ package wins over the PyPI `mcp` SDK
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)

for k, v in [("TG_HOST", "http://localhost"), ("TG_USERNAME", "tigergraph"),
             ("TG_PASSWORD", "tigergraph"), ("TG_GRAPHNAME", "hhg_fraud_graph"),
             ("TG_RESTPP_PORT", "9000"), ("TG_GS_PORT", "14240")]:
    os.environ[k] = v

print("source_kind:", end=" ")
from mcp.tools import _common
print(_common.source_kind())

for tool, fn, args in [
    ("get_transaction", "mcp.tools.transaction_tools.get_transaction", ("3514030",)),
]:
    try:
        mod_name, name = fn.rsplit(".", 1)
        mod = __import__(mod_name, fromlist=[name])
        env = getattr(mod, name)(*args)
        print(tool, "envelope:")
        print(json.dumps(env, indent=2, default=str)[:4000])
    except Exception as e:
        print(tool, "RAISED", type(e).__name__, e)

print()
print("=== try_live_call stub behaviour ===")
import inspect
print(inspect.getsource(_common.try_live_call))
