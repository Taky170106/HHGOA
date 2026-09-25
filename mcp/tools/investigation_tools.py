"""
mcp.tools.investigation_tools — facade that re-exports all 9 investigation tools.

Phase 2 is READ-ONLY controlled investigation layer on top of official TigerGraph MCP
(tigergraph-mcp 0.1.0+, Python 3.10-3.14, TigerGraph 4.1+, stdio & streamable-http).
Do not add agent / GraphRAG / business logic here.

Usage:
  from mcp.tools.investigation_tools import registry, discover_tools, get_tool
  discover_tools() -> list[str]
  get_tool("get_transaction") -> callable
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

# Re-export from submodules (keeps registry flat, policy check stays in leaf handlers)
from mcp.tools.case_tools import benchmark_case_context, get_benchmark_case, list_benchmark_cases
from mcp.tools.history_tools import find_related_cases, get_temporal_chain
from mcp.tools.relationship_tools import find_device_connections, find_related_transactions
from mcp.tools.transaction_tools import calculate_exposure, get_card_history, get_customer_history, get_transaction

# ---------------------------------------------------------------------------
# Registry — canonical tool name -> callable
# ---------------------------------------------------------------------------
registry: Dict[str, Callable[..., Dict[str, Any]]] = {
    "get_transaction": get_transaction,
    "get_customer_history": get_customer_history,
    "get_card_history": get_card_history,
    "find_device_connections": find_device_connections,
    "find_related_transactions": find_related_transactions,
    "find_related_cases": find_related_cases,
    "get_temporal_chain": get_temporal_chain,
    # alias for GSQL file name
    "temporal_chain": get_temporal_chain,
    "calculate_exposure": calculate_exposure,
    "benchmark_case_context": benchmark_case_context,
    # aliases
    "get_benchmark_case": get_benchmark_case,
    "list_benchmark_cases": list_benchmark_cases,
}

# Canonical 9 (without aliases) as enforced by tool_policy.yaml
CANONICAL_TOOLS: List[str] = [
    "get_transaction",
    "get_customer_history",
    "get_card_history",
    "find_device_connections",
    "find_related_transactions",
    "find_related_cases",
    "get_temporal_chain",
    "calculate_exposure",
    "benchmark_case_context",
]


def discover_tools(canonical_only: bool = False) -> List[str]:
    """Return sorted list of available tool names."""
    if canonical_only:
        return sorted(CANONICAL_TOOLS)
    return sorted(registry.keys())


def get_tool(name: str) -> Callable[..., Dict[str, Any]]:
    """
    Retrieve a tool by name (canonical or alias). Raises KeyError if not in allowlist/registry.
    Policy check is still performed inside the leaf handler; this is a convenience lookup.
    """
    if name in registry:
        return registry[name]
    # also try canonical fallback (e.g. caller passes GSQL filename)
    alias_map = {"temporal_chain": "get_temporal_chain", "get_benchmark_case": "benchmark_case_context"}
    canonical = alias_map.get(name)
    if canonical and canonical in registry:
        return registry[canonical]
    raise KeyError(f"Unknown investigation tool '{name}'. Available: {discover_tools(canonical_only=True)}")


def tool_metadata() -> Dict[str, Dict[str, str]]:
    """Static metadata for UI / MCP manifest generation (no live calls)."""
    return {
        "get_transaction": {"gsql": "get_transaction.gsql", "graph": "hhg_fraud_graph", "mode": "read-only"},
        "get_customer_history": {"gsql": "get_customer_history.gsql", "graph": "hhg_fraud_graph", "mode": "read-only"},
        "get_card_history": {"gsql": "get_card_history.gsql", "graph": "hhg_fraud_graph", "mode": "read-only"},
        "find_device_connections": {"gsql": "find_device_connections.gsql", "graph": "hhg_fraud_graph", "mode": "read-only"},
        "find_related_transactions": {"gsql": "find_related_transactions.gsql", "graph": "hhg_fraud_graph", "mode": "read-only"},
        "find_related_cases": {"gsql": "find_related_cases.gsql", "graph": "hhg_fraud_graph", "mode": "read-only"},
        "get_temporal_chain": {"gsql": "temporal_chain.gsql", "graph": "hhg_fraud_graph", "mode": "read-only"},
        "calculate_exposure": {"gsql": "calculate_exposure.gsql (calculate_exposure_list)", "graph": "hhg_fraud_graph", "mode": "read-only"},
        "benchmark_case_context": {"gsql": "benchmark_case_context.gsql", "graph": "hhg_fraud_graph", "mode": "read-only"},
    }


__all__ = [
    "registry",
    "CANONICAL_TOOLS",
    "discover_tools",
    "get_tool",
    "tool_metadata",
    # re-exported callables for direct import
    "get_transaction",
    "get_customer_history",
    "get_card_history",
    "find_device_connections",
    "find_related_transactions",
    "find_related_cases",
    "get_temporal_chain",
    "calculate_exposure",
    "get_benchmark_case",
    "benchmark_case_context",
    "list_benchmark_cases",
]
