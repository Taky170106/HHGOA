"""Pydantic response models for the FastAPI backend (Phase 4).

Kept separate from route code so the contract is readable in one place.
Every field is optional unless the data is guaranteed by construction — a
missing metric shows up as ``None``, never as a placeholder value.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TigerGraphProbe(BaseModel):
    reachable: bool = False
    mode: str = "untested"          # tigergraph_live | file_fallback | error
    detail: str = ""
    latency_ms: Optional[float] = None


class LlmInfo(BaseModel):
    available: bool = False
    provider: Optional[str] = None
    model: Optional[str] = None
    reason: str = ""


class Health(BaseModel):
    status: str
    uptime_s: float
    time: str
    tigergraph: TigerGraphProbe
    llm: LlmInfo
    cases_total: int
    agent_runs: int
    version: str


class CaseIndexEntry(BaseModel):
    case_id: str
    verdict: Optional[str] = None
    status: Optional[str] = None
    fraud_probability: Optional[float] = None
    pattern: Optional[str] = None
    trigger_type: Optional[str] = None
    sar_status: Optional[bool] = None   # True = report filed
    tokens: Optional[int] = None
    graph_write: bool = False


class CaseSummary(BaseModel):
    """One line of the /summary aggregate."""
    case_id: str
    verdict: str
    fraud_probability: float


class ModelInfo(BaseModel):
    loaded: bool = False
    kind: Optional[str] = None
    n_features: Optional[int] = None
    features: Optional[List[str]] = None
    metrics: Optional[Dict[str, Any]] = None
    source: Optional[str] = None


class AgentRunIndex(BaseModel):
    case_id: str
    status: str
    uncertainty: str
    verdict: Optional[str] = None
    p0: Optional[float] = None
    p1: Optional[float] = None
    next_best_action: Optional[str] = None
    tool_calls: int = 0
    tokens: int = 0
    trace_len: int = 0
    errors: List[str] = []
    latency_s: Optional[float] = None


class GraphEcho(BaseModel):
    live: bool
    txn_id: str
    tool: Optional[str] = None
    status: Optional[str] = None
    source_kind: Optional[str] = None
    results: Optional[Any] = None
    returned_count: Optional[int] = None
    total_count: Optional[int] = None
    latency_ms: float
    read_only: bool = True
    error: Optional[str] = None
