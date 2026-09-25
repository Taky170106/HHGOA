"""
Pydantic v2 schemas for HHGoa 2026 TigerGraph Investigation Tools — Phase 2.

- Strict validation (regex for IDs, limits, enums, explicit error codes)
- Structured output envelope (success/error with tool, status, data, source, provenance, truncated)
- Reference: tigergraph-mcp 0.1.0+ (official repo version if unknown; repo declares Python 3.10-3.14, TigerGraph 4.1+)
  Official MCP: https://github.com/tigergraph/tigergraph-mcp — 69 tools total (37 read-only), transports stdio & streamable-http,
  config via TG_HOST/TG_GRAPHNAME/TG_USERNAME/TG_PASSWORD/TG_API_TOKEN/TG_RESTPP_PORT/TG_GS_PORT/TG_TGCLOUD etc,
  supports --allowed-tools/--blocked-tools, logging via TG_LOG_TOOL_CALLS.
  Phase 2 is a READ-ONLY controlled investigation layer on top of the official MCP — no agent, no GraphRAG, no business logic duplication.
- Graph: hhg_fraud_graph (8 vertices, 11 edges); 9 GSQL queries listed in Phase 1 report.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Constants / regex
# ---------------------------------------------------------------------------
RE_HHG = r"^HHG-\d{3}$"  # benchmark case, e.g. HHG-001
RE_CARD = r"^C\d+-K\d+$"  # canonical card, e.g. C12382-K1  (customer C\d+ maps via owns/mapping)
RE_CUSTOMER = r"^C\d+$"  # customer, e.g. C12382  (Phase 0 source; card adds -K suffix)
RE_TXN_NUMERIC = r"^\d+$"  # transaction numeric string, e.g. 3514030
RE_DEVICE = r"^DP-[0-9a-fA-F]{16}$"  # DP- + 16 hex (SHA256 prefix, see tigergraph/schema/schema.gsql)
RE_CLOSED_CASE = r"^CC-\d+$"  # historical closed case
RE_REGION_CODE = r"^\d+(\.0)?$"  # addr1 as string, e.g. 299.0
RE_DOMAIN = r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"  # crude email domain


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ErrorCode(str, Enum):
    INVALID_INPUT = "INVALID_INPUT"
    NOT_FOUND = "NOT_FOUND"
    POLICY_DENIED = "POLICY_DENIED"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    LIVE_TIGERGRAPH_UNAVAILABLE = "LIVE_TIGERGRAPH_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class EntityType(str, Enum):
    transaction = "transaction"
    customer = "customer"
    card = "card"
    device_profile = "device_profile"
    email_domain = "email_domain"
    billing_region = "billing_region"
    closed_case = "closed_case"
    benchmark_case = "benchmark_case"


class SourceKind(str, Enum):
    tigergraph_live = "tigergraph_live"
    file_fallback = "file_fallback"


# ---------------------------------------------------------------------------
# Structured output envelope
# ---------------------------------------------------------------------------
class SourceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    graph: str = Field(default="hhg_fraud_graph", description="TigerGraph graph name")
    query: str = Field(description="GSQL query name backing the tool")
    entity_ids: List[str] = Field(default_factory=list, description="Primary entity IDs touched")
    kind: SourceKind = Field(default=SourceKind.file_fallback, description="Origin of data")


class ProvenanceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str
    query: str
    entity_ids: List[str] = Field(default_factory=list)
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SuccessEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str
    status: Literal["success"] = "success"
    data: Dict[str, Any] = Field(default_factory=dict)
    source: SourceInfo
    provenance: List[ProvenanceEntry] = Field(default_factory=list)
    truncated: bool = False
    # optional pagination hints
    total_count: Optional[int] = None
    returned_count: Optional[int] = None


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str
    status: Literal["error"] = "error"
    error_code: ErrorCode
    message: str
    source: SourceInfo
    provenance: List[ProvenanceEntry] = Field(default_factory=list)
    truncated: bool = False
    details: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Per-tool input schemas (strict, forbid extra)
# ---------------------------------------------------------------------------
class GetTransactionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    txn_id: str = Field(description="TransactionID as numeric string")

    @field_validator("txn_id")
    @classmethod
    def _check_txn(cls, v: str) -> str:
        import re

        if not re.match(RE_TXN_NUMERIC, v):
            raise ValueError(f"txn_id must match {RE_TXN_NUMERIC}")
        return v


class GetCustomerHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    customer_id: str = Field(description="Customer ID, e.g. C12382")
    limit: int = Field(default=100, ge=1, le=200, description="max transactions returned")

    @field_validator("customer_id")
    @classmethod
    def _check_cust(cls, v: str) -> str:
        import re

        if not re.match(RE_CUSTOMER, v):
            raise ValueError(f"customer_id must match {RE_CUSTOMER}")
        return v


class GetCardHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    card_id: str = Field(description="Canonical card ID, e.g. C12382-K1")
    limit: int = Field(default=200, ge=1, le=200, description="max transactions returned (MAX_TEMPORAL)")

    @field_validator("card_id")
    @classmethod
    def _check_card(cls, v: str) -> str:
        import re

        if not re.match(RE_CARD, v):
            raise ValueError(f"card_id must match {RE_CARD}")
        return v


class FindDeviceConnectionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    txn_id: Optional[str] = Field(default=None, description="Seed transaction numeric string")
    device_profile_id: Optional[str] = Field(default=None, description="Seed device DP-*")
    limit: int = Field(default=100, ge=1, le=200)

    @field_validator("txn_id")
    @classmethod
    def _check_txn_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        import re

        if not re.match(RE_TXN_NUMERIC, v):
            raise ValueError(f"txn_id must match {RE_TXN_NUMERIC}")
        return v

    @field_validator("device_profile_id")
    @classmethod
    def _check_dev_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        import re

        if not re.match(RE_DEVICE, v):
            raise ValueError(f"device_profile_id must match {RE_DEVICE}")
        return v

    @model_validator(mode="after")
    def _require_seed(self) -> "FindDeviceConnectionsInput":
        if not self.txn_id and not self.device_profile_id:
            raise ValueError("At least one of txn_id or device_profile_id must be supplied")
        return self


class FindRelatedTransactionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    txn_id: Optional[str] = None
    card_id: Optional[str] = None
    customer_id: Optional[str] = None
    max_hops: int = Field(default=1, ge=1, le=5, description="traversal depth, capped by MAX_HOPS=5")
    limit: int = Field(default=100, ge=1, le=200)

    @field_validator("txn_id")
    @classmethod
    def _check_txn(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        import re

        if not re.match(RE_TXN_NUMERIC, v):
            raise ValueError(f"txn_id must match {RE_TXN_NUMERIC}")
        return v

    @field_validator("card_id")
    @classmethod
    def _check_card(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        import re

        if not re.match(RE_CARD, v):
            raise ValueError(f"card_id must match {RE_CARD}")
        return v

    @field_validator("customer_id")
    @classmethod
    def _check_cust(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        import re

        if not re.match(RE_CUSTOMER, v):
            raise ValueError(f"customer_id must match {RE_CUSTOMER}")
        return v

    @model_validator(mode="after")
    def _require_seed(self) -> "FindRelatedTransactionsInput":
        if not self.txn_id and not self.card_id and not self.customer_id:
            raise ValueError("At least one of txn_id, card_id, customer_id required")
        return self


class FindRelatedCasesInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    txn_id: Optional[str] = None
    card_id: Optional[str] = None
    customer_id: Optional[str] = None
    device_profile_id: Optional[str] = None
    region_code: Optional[str] = None
    domain: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)

    @field_validator("txn_id")
    @classmethod
    def _v_txn(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        import re

        if not re.match(RE_TXN_NUMERIC, v):
            raise ValueError(f"txn_id must match {RE_TXN_NUMERIC}")
        return v

    @field_validator("card_id")
    @classmethod
    def _v_card(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        import re

        if not re.match(RE_CARD, v):
            raise ValueError(f"card_id must match {RE_CARD}")
        return v

    @field_validator("customer_id")
    @classmethod
    def _v_cust(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        import re

        if not re.match(RE_CUSTOMER, v):
            raise ValueError(f"customer_id must match {RE_CUSTOMER}")
        return v

    @field_validator("device_profile_id")
    @classmethod
    def _v_dev(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        import re

        if not re.match(RE_DEVICE, v):
            raise ValueError(f"device_profile_id must match {RE_DEVICE}")
        return v

    @field_validator("region_code")
    @classmethod
    def _v_region(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        import re

        if not re.match(RE_REGION_CODE, v):
            raise ValueError(f"region_code must match {RE_REGION_CODE}")
        return v

    @field_validator("domain")
    @classmethod
    def _v_domain(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        import re

        if not re.match(RE_DOMAIN, v):
            raise ValueError(f"domain must match {RE_DOMAIN}")
        return v

    @model_validator(mode="after")
    def _require_any(self) -> "FindRelatedCasesInput":
        if not any([self.txn_id, self.card_id, self.customer_id, self.device_profile_id, self.region_code, self.domain]):
            raise ValueError("At least one entity ID required")
        return self


class GetTemporalChainInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    card_id: str = Field(description="Canonical card ID, e.g. C12382-K1")
    limit: int = Field(default=200, ge=1, le=200, description="MAX_TEMPORAL")

    @field_validator("card_id")
    @classmethod
    def _check_card(cls, v: str) -> str:
        import re

        if not re.match(RE_CARD, v):
            raise ValueError(f"card_id must match {RE_CARD}")
        return v


class CalculateExposureInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    transaction_ids: List[str] = Field(min_length=1, max_length=100, description="at most MAX_TX_IDS=100")
    case_id: Optional[str] = Field(default=None, description="Optional benchmark case for provenance, HHG-XXX")

    @field_validator("transaction_ids")
    @classmethod
    def _check_list(cls, v: List[str]) -> List[str]:
        import re

        seen: set[str] = set()
        out: List[str] = []
        for item in v:
            s = str(item).strip()
            if not re.match(RE_TXN_NUMERIC, s):
                raise ValueError(f"transaction_id '{s}' must match {RE_TXN_NUMERIC}")
            if s not in seen:
                seen.add(s)
                out.append(s)
        if len(out) == 0:
            raise ValueError("transaction_ids must contain at least one ID")
        if len(out) > 100:
            raise ValueError("transaction_ids exceeds MAX_TX_IDS=100")
        return out

    @field_validator("case_id")
    @classmethod
    def _check_case(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        import re

        if not re.match(RE_HHG, v):
            raise ValueError(f"case_id must match {RE_HHG}")
        return v


class BenchmarkCaseContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    case_id: str = Field(description="Benchmark case HHG-XXX")

    @field_validator("case_id")
    @classmethod
    def _check_case(cls, v: str) -> str:
        import re

        if not re.match(RE_HHG, v):
            raise ValueError(f"case_id must match {RE_HHG}")
        return v


class ListBenchmarkCasesInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    limit: int = Field(default=20, ge=1, le=200)
    offset: int = Field(default=0, ge=0, le=1000)


# ---------------------------------------------------------------------------
# Helpers to build envelopes (pure dict form as returned over MCP)
# ---------------------------------------------------------------------------
def build_success_envelope(
    *,
    tool: str,
    query: str,
    entity_ids: List[str],
    data: Dict[str, Any],
    truncated: bool = False,
    total_count: Optional[int] = None,
    returned_count: Optional[int] = None,
    graph: str = "hhg_fraud_graph",
    kind: SourceKind = SourceKind.file_fallback,
) -> Dict[str, Any]:
    prov = ProvenanceEntry(tool=tool, query=query, entity_ids=entity_ids)
    src = SourceInfo(graph=graph, query=query, entity_ids=entity_ids, kind=kind)
    env = SuccessEnvelope(
        tool=tool,
        data=data,
        source=src,
        provenance=[prov],
        truncated=truncated,
        total_count=total_count,
        returned_count=returned_count if returned_count is not None else (total_count if total_count is not None else None),
    )
    return env.model_dump(mode="json")


def build_error_envelope(
    *,
    tool: str,
    query: str,
    entity_ids: List[str],
    error_code: ErrorCode,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    truncated: bool = False,
    graph: str = "hhg_fraud_graph",
    kind: SourceKind = SourceKind.file_fallback,
) -> Dict[str, Any]:
    prov = ProvenanceEntry(tool=tool, query=query, entity_ids=entity_ids)
    src = SourceInfo(graph=graph, query=query, entity_ids=entity_ids, kind=kind)
    env = ErrorEnvelope(
        tool=tool,
        error_code=error_code,
        message=message,
        source=src,
        provenance=[prov],
        truncated=truncated,
        details=details,
    )
    return env.model_dump(mode="json")
