"""One-shot live TigerGraph probe for the MCP layer (read-only).

Reports whether MCP can run in tigergraph_live mode instead of file_fallback.
Does not write anything and does not retry on failure.
"""
import os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

host = os.environ.get("TG_HOST") or os.environ.get("TIGERGRAPH_HOST") or "http://localhost"
user = os.environ.get("TG_USERNAME") or os.environ.get("TIGERGRAPH_USERNAME") or "tigergraph"
pwd = os.environ.get("TG_PASSWORD") or os.environ.get("TIGERGRAPH_PASSWORD") or "tigergraph"
graph = os.environ.get("TG_GRAPHNAME") or "hhg_fraud_graph"
port = int(os.environ.get("TG_RESTPP_PORT", "9000"))
gs = int(os.environ.get("TG_GS_PORT", "14240"))

print("target: %s restpp=%d gsql=%d user=%s graph=%s" % (host, port, gs, user, graph))

try:
    from pyTigerGraph import TigerGraphConnection
except Exception as e:
    print("RESULT: LIVE_TIGERGRAPH_UNAVAILABLE - pyTigerGraph import failed: %s" % e)
    raise SystemExit(0)

try:
    try:
        conn = TigerGraphConnection(
            host=host, restppPort=port, gsPort=gs, graphname=graph,
            username=user, password=pwd, apiToken="", jwtToken="",
        )
    except TypeError:
        conn = TigerGraphConnection(
            host=host, restppPort=port, gsPort=gs, graphname=graph,
            username=user, password=pwd,
        )
    ver = conn.getVer()
    print("getVer:", ver)
    print("whoami:", getattr(conn, "whoami", lambda: "n/a")())
    n = conn.getVertexCount("Customer")
    print("Customer vertex count:", n)
    ok = conn.runInstalledQuery("count_all")
    print("count_all via RESTPP:", ok)
    print("RESULT: tigergraph_live CONNECTED")
except Exception as e:
    print("RESULT: LIVE_TIGERGRAPH_UNAVAILABLE - %s: %s" % (type(e).__name__, e))
