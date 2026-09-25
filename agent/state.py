"""Agent state for the LangGraph investigation workflow (Phase 4).

The state is the single source of truth for one case run. Every node records
its own provenance (tool, HTTP status, latency) so the whole investigation is
auditable end to end.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class NodeTrace(TypedDict, total=False):
    node: str
    tool: Optional[str]
    http_status: Optional[int]
    latency_ms: Optional[float]
    ok: bool
    detail: str


class InvestigationState(TypedDict, total=False):
    # --- input ---
    case_id: str

    # --- node outputs ---
    case: Dict[str, Any]                 # triage: benchmark case record
    graph_evidence: Dict[str, Any]        # graph_evidence: live TigerGraph context
    relationships: Dict[str, Any]         # relationships: device/case/txn links
    risk: Dict[str, Any]                  # risk_score: model probability + metrics
    xai: Dict[str, Any]                   # xai: MODEL EXPLANATION vs GRAPH EVIDENCE
    summary: Dict[str, Any]               # summary: narrative + evidence trail
    decision: Dict[str, Any]              # next_action: policy-validated action

    # --- control ---
    status: str                           # OK | UNKNOWN_CASE | NO_EVIDENCE | COMPLETE
    uncertainty: str                      # SUFFICIENT | INSUFFICIENT | UNCERTAIN
    errors: List[str]
    trace: List[NodeTrace]
    timings_ms: Dict[str, float]


EMPTY_STATE = lambda case_id: InvestigationState(  # noqa: E731
    case_id=case_id,
    status="OK",
    uncertainty="UNCERTAIN",
    errors=[],
    trace=[],
    timings_ms={},
)


def trace_add(state: InvestigationState, node: str, tool: str = None,
              http_status: int = None, latency_ms: float = None,
              ok: bool = True, detail: str = "") -> None:
    state.setdefault("trace", []).append({
        "node": node, "tool": tool, "http_status": http_status,
        "latency_ms": None if latency_ms is None else round(latency_ms, 1),
        "ok": ok, "detail": detail[:400],
    })


def add_timing(state: InvestigationState, node: str, ms: float) -> None:
    state.setdefault("timings_ms", {})[node] = round(ms, 1)
