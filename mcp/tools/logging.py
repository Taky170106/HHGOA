"""
mcp.tools.logging — lightweight structured logger for Phase 2 investigation tools.

Required fields per spec: timestamp, tool, request_id, case_id, status, latency.
Usage:
  from mcp.tools.logging import log_tool_call
  log_tool_call(tool="get_transaction", request_id="...", case_id="HHG-001", status="success", latency_ms=12.3, truncated=False, source_kind="file_fallback")
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def log_tool_call(
    *,
    tool: str,
    request_id: Optional[str] = None,
    case_id: Optional[str] = None,
    status: str,
    latency_ms: Optional[float] = None,
    truncated: Optional[bool] = None,
    source_kind: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    payload: dict[str, Any] = {
        "timestamp": _now_iso(),
        "tool": tool,
        "request_id": request_id or new_request_id(),
        "case_id": case_id,
        "status": status,
        "latency_ms": round(latency_ms, 2) if isinstance(latency_ms, (int, float)) else None,
        "truncated": truncated,
        "source_kind": source_kind,
    }
    if extra:
        payload.update(extra)
    # compact single-line JSON to stderr (so stdout remains MCP-clean)
    try:
        sys.stderr.write(json.dumps(payload, separators=(",", ":")) + "\n")
        sys.stderr.flush()
    except Exception:
        pass


class Timer:
    def __init__(self) -> None:
        self._t0 = time.perf_counter()

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0
