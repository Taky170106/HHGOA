"""Agent state for the LangGraph investigation workflow (Phase 4).

The state is the single source of truth for one case run. Every node records
its own provenance (tool, HTTP status, latency) so the whole investigation is
auditable end to end.

LangGraph creates a channel only for keys declared here, so every value a node
writes must appear in ``InvestigationState``.
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

    # --- shared working memory (written by several nodes) ---
    facts: Dict[str, Any]                 # build_cases.gather() bundle (graph facts)
    analysis: Dict[str, Any]              # build_cases.analyse() signal set
    evidence: List[Dict[str, Any]]        # build_cases.build_evidence() items
    counterfactual: Dict[str, Any]        # counterfactual.engine.model_analysis()
    policy: Dict[str, Any]                # policies.rules.select() result
    llm: Dict[str, Any]                   # agent.llm.client envelope (real or absent)
    round: int                            # reinvestigation rounds taken (bounded)
    tool_calls: int                       # live tool calls actually issued
    tokens: int                           # real LLM tokens used (0 = none)

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
    round=0,
    tool_calls=0,
    tokens=0,
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


def trace_from(state: InvestigationState, node: str, tool: str = None,
               http_status: int = None, latency_ms: float = None,
               ok: bool = True, detail: str = "") -> List[Dict[str, Any]]:
    """Non-mutating variant: returns a NEW trace list for the node's return dict.

    LangGraph replaces a channel's value with whatever the node returns, so a
    node must hand back the whole list rather than rely on in-place mutation.
    """
    tr = list(state.get("trace") or [])
    tr.append({
        "node": node, "tool": tool, "http_status": http_status,
        "latency_ms": None if latency_ms is None else round(latency_ms, 1),
        "ok": ok, "detail": detail[:400],
    })
    return tr


def timings_from(state: InvestigationState, node: str, ms: float) -> Dict[str, float]:
    """Non-mutating twin of add_timing (same reason as trace_from)."""
    t = dict(state.get("timings_ms") or {})
    t[node] = round(ms, 1)
    return t
