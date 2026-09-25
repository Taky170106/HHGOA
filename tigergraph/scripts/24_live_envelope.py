"""Show the live envelope returned by an INSTALLED query (get_card_history),
so the MCP live/fallback response-contract difference can be reported precisely."""
import os, sys, io, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)

for k, v in [("TG_HOST", "http://localhost"), ("TG_USERNAME", "tigergraph"),
             ("TG_PASSWORD", "tigergraph"), ("TG_GRAPHNAME", "hhg_fraud_graph"),
             ("TG_RESTPP_PORT", "9000"), ("TG_GS_PORT", "14240")]:
    os.environ[k] = v

from mcp.tools.transaction_tools import get_card_history  # noqa: E402

env = get_card_history("C12382-K1")
print(json.dumps(env, indent=2, default=str)[:2500])
