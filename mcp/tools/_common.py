"""
_mcp.tools._common — shared helpers for Phase 2 investigation tools.

- Resolves project root (D:\HHG) and data dirs via DATA_DIR env or repo-relative fallback.
- Loads tool_policy.yaml allowlist + resource limits.
- Live-creds detection (TG_HOST / TIGERGRAPH_HOST).
- CSV loading with pandas + caching (file_fallback).
- Envelope helpers and error factories.
- Does NOT duplicate fraud logic — only exposes TigerGraph-equivalent traversals via minimal pandas joins.

Official MCP ref: tigergraph-mcp 0.1.0+, Python 3.10-3.14, TigerGraph 4.1+, stdio & streamable-http.
"""

from __future__ import annotations

import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml  # pyyaml

# ---------------------------------------------------------------------------
# Project root & data dirs
# ---------------------------------------------------------------------------

def _find_project_root(start: Path) -> Path:
    # Walk up until we find data/vertices/benchmark_case.csv or tigergraph/schema/schema.gsql
    cur = start.resolve()
    for _ in range(8):
        if (cur / "data" / "vertices" / "benchmark_case.csv").exists():
            return cur
        if (cur / "tigergraph" / "schema" / "schema.gsql").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    # Fallback: env override or cwd
    env = os.getenv("HHG_ROOT") or os.getenv("PROJECT_ROOT")
    if env and Path(env).exists():
        return Path(env).resolve()
    return Path.cwd().resolve()


PROJECT_ROOT: Path = _find_project_root(Path(__file__))
DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
VERTICES_DIR: Path = Path(os.getenv("VERTICES_DIR", str(DATA_DIR / "vertices")))
EDGES_DIR: Path = Path(os.getenv("EDGES_DIR", str(DATA_DIR / "edges")))
POLICY_PATH: Path = PROJECT_ROOT / "mcp" / "config" / "tool_policy.yaml"

GRAPH_NAME = os.getenv("TIGERGRAPH_GRAPH_NAME", os.getenv("TG_GRAPHNAME", "hhg_fraud_graph"))

# ---------------------------------------------------------------------------
# Policy loading
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_policy() -> Dict[str, Any]:
    if POLICY_PATH.exists():
        with open(POLICY_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {
        "allowlist": {"tools": ["get_transaction","get_customer_history","get_card_history","find_device_connections","find_related_transactions","find_related_cases","get_temporal_chain","calculate_exposure","benchmark_case_context"]},
        "resource_limits": {"MAX_HOPS":5,"MAX_RESULTS":200,"MAX_TX_IDS":100,"MAX_TEMPORAL":200,"TIMEOUT_S":30},
    }

def is_allowed(tool_name: str) -> bool:
    policy = load_policy()
    allowed = set(policy.get("allowlist", {}).get("tools", []))
    # aliases resolve to canonical
    aliases: Dict[str, str] = policy.get("allowlist", {}).get("aliases", {}) or {}
    # if tool_name is alias, check canonical
    if tool_name in aliases:
        tool_name = aliases[tool_name]
    return tool_name in allowed

def resource_limits() -> Dict[str, int]:
    policy = load_policy()
    rl = policy.get("resource_limits", {}) or {}
    return {
        "MAX_HOPS": int(rl.get("MAX_HOPS", 5)),
        "MAX_RESULTS": int(rl.get("MAX_RESULTS", 200)),
        "MAX_TX_IDS": int(rl.get("MAX_TX_IDS", 100)),
        "MAX_TEMPORAL": int(rl.get("MAX_TEMPORAL", 200)),
        "TIMEOUT_S": int(rl.get("TIMEOUT_S", 30)),
    }

# ---------------------------------------------------------------------------
# Live credentials detection
# ---------------------------------------------------------------------------

def has_live_credentials() -> bool:
    # Official MCP envs: TG_HOST (preferred) + TIGERGRAPH_HOST legacy
    host = os.getenv("TG_HOST") or os.getenv("TIGERGRAPH_HOST") or os.getenv("TIGERGRAPH_HOSTNAME")
    token = os.getenv("TG_API_TOKEN") or os.getenv("TIGERGRAPH_TOKEN")
    user = os.getenv("TG_USERNAME") or os.getenv("TIGERGRAPH_USERNAME")
    pwd = os.getenv("TG_PASSWORD") or os.getenv("TIGERGRAPH_PASSWORD")
    # Any host + (token or user/pwd) counts as configured; bare host alone triggers attempt then LIVE_TIGERGRAPH_UNAVAILABLE on failure
    if host and str(host).strip():
        return True
    # also consider MCP_ENDPOINT for streamable-http transport
    if os.getenv("MCP_ENDPOINT"):
        return True
    return bool(token or (user and pwd))

def source_kind() -> str:
    return "tigergraph_live" if has_live_credentials() else "file_fallback"

# ---------------------------------------------------------------------------
# CSV loading (pandas, cached)
# ---------------------------------------------------------------------------
try:
    import pandas as pd  # type: ignore
except Exception as e:  # pragma: no cover
    pd = None  # will error at call site with structured envelope

@lru_cache(maxsize=32)
def _load_csv(path_str: str) -> "pd.DataFrame":
    if pd is None:
        raise RuntimeError("pandas not available — install pandas for file_fallback")
    p = Path(path_str)
    if not p.exists():
        # try relative to PROJECT_ROOT
        alt = PROJECT_ROOT / path_str
        if alt.exists():
            p = alt
        else:
            raise FileNotFoundError(f"CSV not found: {path_str} (resolved {p})")
    # low_memory=False to avoid mixed-type warnings; dtype=str for IDs to preserve leading zeros
    return pd.read_csv(p, low_memory=False, encoding="utf-8")

def load_vertices(name: str) -> "pd.DataFrame":
    # name without .csv, e.g. "transaction"
    return _load_csv(str(VERTICES_DIR / f"{name}.csv"))

def load_edges(name: str) -> "pd.DataFrame":
    return _load_csv(str(EDGES_DIR / f"{name}.csv"))

# Convenience: clear caches on demand (tests)
def clear_csv_cache() -> None:
    _load_csv.cache_clear()

# ---------------------------------------------------------------------------
# Small helpers for envelopes
# ---------------------------------------------------------------------------
from mcp.schemas.tool_schemas import ErrorCode, SourceKind, build_error_envelope, build_success_envelope  # noqa: E402

def policy_denied_envelope(tool: str, query: str) -> Dict[str, Any]:
    return build_error_envelope(
        tool=tool,
        query=query,
        entity_ids=[],
        error_code=ErrorCode.POLICY_DENIED,
        message=f"Tool '{tool}' is not in allowlist (see mcp/config/tool_policy.yaml)",
        kind=SourceKind.file_fallback,
    )

def limit_exceeded_envelope(tool: str, query: str, msg: str, entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    return build_error_envelope(
        tool=tool,
        query=query,
        entity_ids=entity_ids or [],
        error_code=ErrorCode.RESOURCE_LIMIT_EXCEEDED,
        message=msg,
        kind=SourceKind.file_fallback,
    )

def live_unavailable_envelope(tool: str, query: str, entity_ids: List[str], detail: str = "") -> Dict[str, Any]:
    msg = "LIVE_TIGERGRAPH_UNAVAILABLE: TG_HOST/TIGERGRAPH_HOST not configured or connection failed."
    if detail:
        msg += f" Detail: {detail}"
    msg += " Using file_fallback if available; set TG_HOST/TG_GRAPHNAME/TG_USERNAME/TG_PASSWORD to enable live TigerGraph."
    return build_error_envelope(
        tool=tool,
        query=query,
        entity_ids=entity_ids,
        error_code=ErrorCode.LIVE_TIGERGRAPH_UNAVAILABLE,
        message=msg,
        details={"hint": "Set TG_HOST and credentials in .env or environment, or rely on file_fallback (data/vertices/*.csv, data/edges/*.csv)"},
        kind=SourceKind.file_fallback,
    )

# ---------------------------------------------------------------------------
# Live call stub (tries pyTigerGraph if available, else returns LIVE_TIGERGRAPH_UNAVAILABLE)
# ---------------------------------------------------------------------------
def try_live_call(tool: str, query: str, entity_ids: List[str], payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Attempt to call the official TigerGraph MCP / pyTigerGraph live.
    Phase 2 is read-only; this stub never writes. If TG credentials absent, caller should use file_fallback path.
    Returns None if live not configured, else an envelope (success or LIVE_TIGERGRAPH_UNAVAILABLE error).
    """
    if not has_live_credentials():
        return None
    # Try to import official client; if missing, return LIVE_TIGERGRAPH_UNAVAILABLE (graceful)
    try:
        # Preferred: tigergraph-mcp official package exposes tools; pyTigerGraph for RESTPP/GSQL
        # We attempt a minimal connection check without side effects.
        import os as _os

        host = _os.getenv("TG_HOST") or _os.getenv("TIGERGRAPH_HOST") or ""
        graph = _os.getenv("TG_GRAPHNAME") or _os.getenv("TIGERGRAPH_GRAPH_NAME") or GRAPH_NAME
        # Lazy import — do not fail import at module load time
        try:
            import pyTigerGraph as tg  # type: ignore

            # Instantiate connection (no network yet)
            conn = tg.TigerGraphConnection(
                host=host,
                graphname=graph,
                username=_os.getenv("TG_USERNAME") or _os.getenv("TIGERGRAPH_USERNAME"),
                password=_os.getenv("TG_PASSWORD") or _os.getenv("TIGERGRAPH_PASSWORD"),
                apiToken=_os.getenv("TG_API_TOKEN") or _os.getenv("TIGERGRAPH_TOKEN"),
                restppPort=int(_os.getenv("TG_RESTPP_PORT", _os.getenv("TIGERGRAPH_PORT", "14240"))),
                gsPort=int(_os.getenv("TG_GS_PORT", "14240")),
            )
            # Try a lightweight echo / getVer; if it raises, we surface LIVE_TIGERGRAPH_UNAVAILABLE
            # Use timeout from policy
            rl = resource_limits()
            timeout = rl.get("TIMEOUT_S", 30)
            # pyTigerGraph may expose .getVer() or .gds; try getVer with timeout via simple call
            try:
                # Some versions require explicit getToken; we just call a safe read
                _ = conn.gsql("SHOW QUERY get_transaction", options=[])  # type: ignore[attr-defined]
            except Exception as e:
                # Connection failed — surface as LIVE_TIGERGRAPH_UNAVAILABLE so caller can fall back
                return live_unavailable_envelope(tool, query, entity_ids, detail=str(e))

            # If we got here, attempt the actual query run via runInstalledQuery
            # The 9 queries are installed as get_transaction etc.; we call with payload params.
            try:
                result = conn.runInstalledQuery(query, params=payload, timeout=timeout * 1000)  # type: ignore[attr-defined]
                # Wrap as success envelope with live kind
                return build_success_envelope(
                    tool=tool,
                    query=query,
                    entity_ids=entity_ids,
                    data={"live_result": result, "params": payload},
                    truncated=False,
                    graph=graph,
                    kind=SourceKind.tigergraph_live,
                )
            except Exception as e:
                return build_error_envelope(
                    tool=tool,
                    query=query,
                    entity_ids=entity_ids,
                    error_code=ErrorCode.INTERNAL_ERROR,
                    message=f"Live query '{query}' failed: {e}",
                    kind=SourceKind.tigergraph_live,
                )
        except ImportError as ie:
            # tigergraph-mcp or pyTigerGraph not installed — inform but keep file_fallback as success path
            return live_unavailable_envelope(tool, query, entity_ids, detail=f"pyTigerGraph not installed: {ie}. pip install tigergraph-mcp pyTigerGraph")
    except Exception as e:  # pragma: no cover
        return build_error_envelope(
            tool=tool,
            query=query,
            entity_ids=entity_ids,
            error_code=ErrorCode.INTERNAL_ERROR,
            message=f"Unexpected live-call error: {e}",
            kind=SourceKind.file_fallback,
        )
    return None


# ===========================================================================
# Phase 3 — live execution of the INSTALLED GSQL queries via RESTPP.
#
# This definition intentionally follows (and therefore supersedes) the
# pyTigerGraph-based stub above: it calls the exact RESTPP query endpoint that
# Phase 3 validated, so the MCP tool layer and the Phase 3 validation exercise
# the same code path on the same live graph.
#
# READ-ONLY: only  GET /query/<graph>/<query>  is used. There is no GSQL
# passthrough, no write endpoint and no schema mutation in this path.
# ===========================================================================

import json as _json
import urllib.error as _uerr
import urllib.parse as _uparse
import urllib.request as _ureq
import base64 as _b64

# Exact RESTPP parameter contract of every installed query (Phase 3 catalog).
# RESTPP rejects unknown/missing parameters (HTTP 400), so the tool-layer payload
# is normalised to the declared contract: legacy keys (`max_hops`, `limit`) are
# mapped where a bounded equivalent exists, keys outside the contract are dropped,
# and every declared parameter is always present ("" means "not supplied" to GSQL).
_QUERY_PARAMS: Dict[str, List[str]] = {
    "get_transaction":           ["txn_id"],
    "find_related_transactions": ["txn_id", "card_id", "customer_id",
                                  "max_depth", "max_results"],
    "find_device_connections":   ["txn_id", "device_profile_id"],
    "find_related_cases":        ["txn_id", "card_id", "customer_id",
                                  "device_profile_id", "region_code", "domain"],
    "benchmark_case_context":    ["case_id"],
    "get_card_history":          ["card_id"],
    "get_customer_history":      ["customer_id"],
    "temporal_chain":            ["card_id"],
    "calculate_exposure":        ["txn_ids_csv"],
    "calculate_exposure_list":   ["txn_ids"],
}
_QUERY_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "find_related_transactions": {"max_depth": 2, "max_results": 200},
}
_PARAM_ALIASES: Dict[str, str] = {"max_hops": "max_depth", "limit": "max_results"}


def restpp_endpoint(query: str) -> str:
    host = (os.getenv("TG_HOST") or os.getenv("TIGERGRAPH_HOST")
            or "http://localhost").rstrip("/")
    if not host.startswith("http"):
        host = "http://" + host
    port = os.getenv("TG_RESTPP_PORT") or os.getenv("TIGERGRAPH_PORT") or "9000"
    graph = os.getenv("TG_GRAPHNAME") or os.getenv("TIGERGRAPH_GRAPH_NAME") or GRAPH_NAME
    return f"{host}:{port}/query/{graph}/{query}"


def restpp_call(query: str, payload: Dict[str, Any], timeout_s: int = 30) -> Dict[str, Any]:
    declared = _QUERY_PARAMS.get(query)
    src = {_PARAM_ALIASES.get(k, k): v for k, v in (payload or {}).items()}
    if declared is None:
        # Unknown query: forward what we were given as-is (still read-only GET).
        params = {k: v for k, v in src.items() if v is not None}
    else:
        defaults = _QUERY_DEFAULTS.get(query, {})
        params = {}
        for key in declared:
            v = src.get(key, defaults.get(key, ""))
            if v is None:
                v = ""
            params[key] = v
    url = restpp_endpoint(query)
    if params:
        url += "?" + _uparse.urlencode({k: v for k, v in params.items()})
    user = os.getenv("TG_USERNAME") or os.getenv("TIGERGRAPH_USERNAME") or "tigergraph"
    pwd = os.getenv("TG_PASSWORD") or os.getenv("TIGERGRAPH_PASSWORD") or "tigergraph"
    token = os.getenv("TG_API_TOKEN") or os.getenv("TG_TOKEN") or ""
    headers = {"Authorization": ("Bearer " + token) if token else
               ("Basic " + _b64.b64encode(f"{user}:{pwd}".encode()).decode())}
    try:
        with _ureq.urlopen(_ureq.Request(url, headers=headers), timeout=timeout_s) as r:
            body = r.read().decode("utf-8", "replace")
            status = r.status
    except _uerr.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        status = e.code
    except Exception as e:
        return {"http_status": None, "results": [], "error": True, "message": str(e)}
    try:
        j = _json.loads(body)
    except Exception:
        return {"http_status": status, "results": [], "error": status != 200,
                "message": body[:400]}
    return {"http_status": status, "results": j.get("results", []),
            "error": bool(j.get("error", False)) or status != 200,
            "message": j.get("message", "")}


def try_live_call(tool: str, query: str, entity_ids: List[str],
                  payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Execute an installed GSQL query on the live graph (read-only RESTPP GET)."""
    if not has_live_credentials():
        return None
    rl = resource_limits()
    out = restpp_call(query, payload, timeout_s=rl.get("TIMEOUT_S", 30))
    graph = os.getenv("TG_GRAPHNAME") or os.getenv("TIGERGRAPH_GRAPH_NAME") or GRAPH_NAME

    if out["http_status"] is None or out["http_status"] == 404:
        return live_unavailable_envelope(
            tool, query, entity_ids,
            detail=f"RESTPP {out['http_status']}: {out['message']}")
    if out["error"]:
        code = ErrorCode.NOT_FOUND if out["http_status"] == 400 else ErrorCode.INTERNAL_ERROR
        return build_error_envelope(
            tool=tool, query=query, entity_ids=entity_ids, error_code=code,
            message=f"Live query '{query}' HTTP {out['http_status']}: {out['message']}",
            kind=SourceKind.tigergraph_live)
    # GSQL reports "nothing found" in two shapes: a marker block whose key is a
    # quoted literal (PRINT "NOT_FOUND" -> key '"NOT_FOUND"'), or simply a set of
    # result blocks that are all empty. Either way the investigation found nothing,
    # so surface NOT_FOUND instead of a success envelope with empty lists.
    markers = {"NOT_FOUND", "NO_SEED", "BENCHMARK_NOT_FOUND", "NO_DEVICE_FOUND"}
    keys, saw_block, all_empty = set(), False, True
    for blk in out["results"]:
        if not isinstance(blk, dict):
            continue
        saw_block = True
        for k, v in blk.items():
            keys.add(str(k).strip().strip('"'))
            if not (isinstance(v, list) and len(v) == 0):
                all_empty = False
    if saw_block and (keys.issubset(markers) or all_empty):
        hint = ", ".join(sorted(keys)) or "no entities"
        return build_error_envelope(
            tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.NOT_FOUND,
            message=f"Live query '{query}' matched no graph entities ({hint})",
            kind=SourceKind.tigergraph_live)
    return build_success_envelope(
        tool=tool, query=query, entity_ids=entity_ids,
        data={"results": out["results"], "params": payload,
              "endpoint": restpp_endpoint(query)},
        truncated=False, graph=graph, kind=SourceKind.tigergraph_live)
