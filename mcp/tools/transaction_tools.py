"""
mcp.tools.transaction_tools — get_transaction, get_customer_history, get_card_history, calculate_exposure

Each function:
  - validate via Pydantic schema
  - check tool_policy allowlist
  - enforce resource limits
  - if TG credentials absent -> file_fallback via pandas (source=file_fallback, provenance with query)
  - else try official MCP via pyTigerGraph stub; on failure return LIVE_TIGERGRAPH_UNAVAILABLE
  - log via mcp.tools.logging (timestamp, tool, request_id, case_id, status, latency)
  - return structured envelope {tool, status, data, source{graph,query,entity_ids}, provenance[{tool,query,entity_ids,ts}], truncated?}
  File fallback exposes TigerGraph-equivalent traversals via minimal pandas joins — no fraud logic duplication.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, List, Optional

from mcp.schemas.tool_schemas import (
    CalculateExposureInput,
    ErrorCode,
    GetCardHistoryInput,
    GetCustomerHistoryInput,
    GetTransactionInput,
    SourceKind,
    build_error_envelope,
    build_success_envelope,
)
from mcp.tools._common import (
    GRAPH_NAME,
    has_live_credentials,
    is_allowed,
    limit_exceeded_envelope,
    load_edges,
    load_vertices,
    policy_denied_envelope,
    resource_limits,
    try_live_call,
)
from mcp.tools.logging import Timer, log_tool_call, new_request_id


def _norm(v: Any) -> str:
    return str(v).strip()


# ---------------------------------------------------------------------------
# get_transaction
# ---------------------------------------------------------------------------
def get_transaction(txn_id: str, *, request_id: Optional[str] = None, case_id: Optional[str] = None) -> Dict[str, Any]:
    tool = "get_transaction"
    query = "get_transaction"
    rid = request_id or new_request_id()
    t = Timer()
    entity_ids = [str(txn_id)]

    # 1. validate
    try:
        inp = GetTransactionInput(txn_id=str(txn_id))
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INVALID_INPUT, message=str(e), kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INVALID_INPUT"})
        return env

    # 2. allowlist
    if not is_allowed(tool):
        env = policy_denied_envelope(tool, query)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "POLICY_DENIED"})
        return env

    # 3. live attempt (only if configured)
    if has_live_credentials():
        live_env = try_live_call(tool, query, entity_ids, {"txn_id": inp.txn_id})
        if live_env is not None:
            status = live_env.get("status", "error")
            sk = live_env.get("source", {}).get("kind", "tigergraph_live")
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status=status, latency_ms=t.elapsed_ms(), source_kind=sk)
            return live_env

    # 4. file_fallback via pandas (minimal joins, TigerGraph-equivalent)
    try:
        import pandas as pd  # noqa: F401

        tx = load_vertices("transaction")
        # txn_id is string PK
        row = tx[tx["txn_id"].astype(str) == inp.txn_id]
        if row.empty:
            env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.NOT_FOUND, message=f"Transaction {inp.txn_id} not found", kind=SourceKind.file_fallback)
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "NOT_FOUND"})
            return env
        rec = row.iloc[0].to_dict()

        # Card & Customer via reverse MADE + OWNS (expose attributes only — do not compute risk)
        card_id = _norm(rec.get("card_id", ""))
        customer_id = _norm(rec.get("customer_id", ""))
        card_rec: Optional[Dict[str, Any]] = None
        customer_rec: Optional[Dict[str, Any]] = None
        if card_id:
            try:
                cdf = load_vertices("card")
                cr = cdf[cdf["card_id"].astype(str) == card_id]
                if not cr.empty:
                    card_rec = cr.iloc[0].to_dict()
            except Exception:
                pass
        if customer_id:
            try:
                custdf = load_vertices("customer")
                ur = custdf[custdf["customer_id"].astype(str) == customer_id]
                if not ur.empty:
                    customer_rec = ur.iloc[0].to_dict()
            except Exception:
                pass

        # Device (FROM_DEVICE edge)
        devices: List[Dict[str, Any]] = []
        try:
            fd = load_edges("from_device")
            dev_ids = fd[fd["from_txn_id"].astype(str) == inp.txn_id]["to_device_profile_id"].astype(str).tolist()
            if dev_ids:
                ddf = load_vertices("device_profile")
                devices = ddf[ddf["device_profile_id"].astype(str).isin(dev_ids)].to_dict(orient="records")  # type: ignore
        except Exception:
            devices = []

        # Billing region
        regions: List[Dict[str, Any]] = []
        try:
            bi = load_edges("billed_in")
            r_ids = bi[bi["from_txn_id"].astype(str) == inp.txn_id]["to_region_code"].astype(str).tolist()
            if r_ids:
                rdf = load_vertices("billing_region")
                regions = rdf[rdf["region_code"].astype(str).isin(r_ids)].to_dict(orient="records")  # type: ignore
        except Exception:
            regions = []

        # Emails (purchaser / recipient edges)
        p_emails: List[str] = []
        r_emails: List[str] = []
        try:
            pe = load_edges("purchaser_email")
            p_emails = pe[pe["from_txn_id"].astype(str) == inp.txn_id]["to_domain"].astype(str).tolist()
        except Exception:
            pass
        try:
            re_ = load_edges("recipient_email")
            r_emails = re_[re_["from_txn_id"].astype(str) == inp.txn_id]["to_domain"].astype(str).tolist()
        except Exception:
            pass

        # Temporal neighbors (NEXT edge forward/backward) — TigerGraph temporal ordering exposed as edges
        next_txns: List[str] = []
        prev_txns: List[str] = []
        try:
            nxt = load_edges("next")
            next_txns = nxt[nxt["from_txn_id"].astype(str) == inp.txn_id]["to_txn_id"].astype(str).tolist()
            prev_txns = nxt[nxt["to_txn_id"].astype(str) == inp.txn_id]["from_txn_id"].astype(str).tolist()
        except Exception:
            pass

        data: Dict[str, Any] = {
            "transaction": rec,
            "card": card_rec,
            "customer": customer_rec,
            "devices": devices,
            "billing_regions": regions,
            "purchaser_email_domains": p_emails,
            "recipient_email_domains": r_emails,
            "next_txn_ids": next_txns,
            "prev_txn_ids": prev_txns,
        }
        env = build_success_envelope(tool=tool, query=query, entity_ids=entity_ids, data=data, truncated=False, graph=GRAPH_NAME, kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="success", latency_ms=t.elapsed_ms(), source_kind="file_fallback")
        return env
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INTERNAL_ERROR, message=f"file_fallback failed: {e}", kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INTERNAL_ERROR"})
        return env


# ---------------------------------------------------------------------------
# get_customer_history
# ---------------------------------------------------------------------------
def get_customer_history(customer_id: str, limit: int = 100, *, request_id: Optional[str] = None, case_id: Optional[str] = None) -> Dict[str, Any]:
    tool = "get_customer_history"
    query = "get_customer_history"
    rid = request_id or new_request_id()
    t = Timer()
    entity_ids = [str(customer_id)]

    try:
        inp = GetCustomerHistoryInput(customer_id=str(customer_id), limit=int(limit))
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INVALID_INPUT, message=str(e), kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INVALID_INPUT"})
        return env

    if not is_allowed(tool):
        env = policy_denied_envelope(tool, query)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "POLICY_DENIED"})
        return env

    rl = resource_limits()
    if inp.limit > rl["MAX_RESULTS"]:
        env = limit_exceeded_envelope(tool, query, f"limit {inp.limit} exceeds MAX_RESULTS={rl['MAX_RESULTS']}", entity_ids)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "RESOURCE_LIMIT_EXCEEDED"})
        return env

    if has_live_credentials():
        live_env = try_live_call(tool, query, entity_ids, {"customer_id": inp.customer_id})
        if live_env is not None:
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status=live_env.get("status", "error"), latency_ms=t.elapsed_ms(), source_kind=live_env.get("source", {}).get("kind", "tigergraph_live"))
            return live_env

    try:
        custdf = load_vertices("customer")
        row = custdf[custdf["customer_id"].astype(str) == inp.customer_id]
        if row.empty:
            env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.NOT_FOUND, message=f"Customer {inp.customer_id} not found", kind=SourceKind.file_fallback)
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "NOT_FOUND"})
            return env
        customer = row.iloc[0].to_dict()

        # Cards via OWNS
        owns = load_edges("owns")
        card_ids = owns[owns["from_customer_id"].astype(str) == inp.customer_id]["to_card_id"].astype(str).tolist()
        cards: List[Dict[str, Any]] = []
        if card_ids:
            cdf = load_vertices("card")
            cards = cdf[cdf["card_id"].astype(str).isin(card_ids)].to_dict(orient="records")  # type: ignore

        # Transactions via MADE (card -> transaction)
        tx = load_vertices("transaction")
        made = load_edges("made")
        txn_ids: List[str] = []
        if card_ids:
            txn_ids = made[made["from_card_id"].astype(str).isin(card_ids)]["to_txn_id"].astype(str).tolist()
        txns = []
        total = 0
        truncated = False
        if txn_ids:
            # preserve temporal order by ts if available; TigerGraph returns unsorted, caller sorts — we sort here
            tx_sub = tx[tx["txn_id"].astype(str).isin(txn_ids)].copy()
            total = len(tx_sub)
            if "ts" in tx_sub.columns:
                try:
                    import pandas as pd  # noqa: F401
                    tx_sub["ts_parsed"] = pd.to_datetime(tx_sub["ts"], errors="coerce")
                    tx_sub = tx_sub.sort_values("ts_parsed")
                except Exception:
                    pass
            if len(tx_sub) > inp.limit:
                truncated = True
                tx_sub = tx_sub.head(inp.limit)
            txns = tx_sub.drop(columns=[c for c in ["ts_parsed"] if c in tx_sub.columns]).to_dict(orient="records")  # type: ignore

        data: Dict[str, Any] = {"customer": customer, "cards": cards, "transactions": txns, "total_transactions": total}
        env = build_success_envelope(tool=tool, query=query, entity_ids=entity_ids, data=data, truncated=truncated, total_count=total, returned_count=len(txns), graph=GRAPH_NAME, kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="success", latency_ms=t.elapsed_ms(), truncated=truncated, source_kind="file_fallback")
        return env
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INTERNAL_ERROR, message=f"file_fallback failed: {e}", kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INTERNAL_ERROR"})
        return env


# ---------------------------------------------------------------------------
# get_card_history
# ---------------------------------------------------------------------------
def get_card_history(card_id: str, limit: int = 200, *, request_id: Optional[str] = None, case_id: Optional[str] = None) -> Dict[str, Any]:
    tool = "get_card_history"
    query = "get_card_history"
    rid = request_id or new_request_id()
    t = Timer()
    entity_ids = [str(card_id)]

    try:
        inp = GetCardHistoryInput(card_id=str(card_id), limit=int(limit))
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INVALID_INPUT, message=str(e), kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INVALID_INPUT"})
        return env

    if not is_allowed(tool):
        env = policy_denied_envelope(tool, query)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "POLICY_DENIED"})
        return env

    rl = resource_limits()
    if inp.limit > rl["MAX_TEMPORAL"]:
        env = limit_exceeded_envelope(tool, query, f"limit {inp.limit} exceeds MAX_TEMPORAL={rl['MAX_TEMPORAL']}", entity_ids)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "RESOURCE_LIMIT_EXCEEDED"})
        return env

    if has_live_credentials():
        live_env = try_live_call(tool, query, entity_ids, {"card_id": inp.card_id})
        if live_env is not None:
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status=live_env.get("status", "error"), latency_ms=t.elapsed_ms(), source_kind=live_env.get("source", {}).get("kind", "tigergraph_live"))
            return live_env

    try:
        cdf = load_vertices("card")
        cr = cdf[cdf["card_id"].astype(str) == inp.card_id]
        if cr.empty:
            env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.NOT_FOUND, message=f"Card {inp.card_id} not found", kind=SourceKind.file_fallback)
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "NOT_FOUND"})
            return env
        card = cr.iloc[0].to_dict()

        made = load_edges("made")
        txn_ids = made[made["from_card_id"].astype(str) == inp.card_id]["to_txn_id"].astype(str).tolist()
        tx = load_vertices("transaction")
        tx_sub = tx[tx["txn_id"].astype(str).isin(txn_ids)].copy() if txn_ids else tx.head(0).copy()
        total = len(tx_sub)
        truncated = False
        # order by ts; NEXT edges encode temporal ordering — expose them
        if "ts" in tx_sub.columns and not tx_sub.empty:
            try:
                import pandas as pd
                tx_sub["ts_parsed"] = pd.to_datetime(tx_sub["ts"], errors="coerce")
                tx_sub = tx_sub.sort_values("ts_parsed")
            except Exception:
                pass
        if len(tx_sub) > inp.limit:
            truncated = True
            tx_sub = tx_sub.head(inp.limit)
        txns = tx_sub.drop(columns=[c for c in ["ts_parsed"] if c in tx_sub.columns]).to_dict(orient="records")  # type: ignore

        # NEXT edges among these txns (temporal chain)
        next_edges: List[Dict[str, Any]] = []
        try:
            nxt = load_edges("next")
            # only edges where both endpoints in this card's transactions (MADE set) — but for simplicity include forward edges from these txns
            if txn_ids:
                nxt_sub = nxt[nxt["from_txn_id"].astype(str).isin([str(x.get("txn_id")) for x in txns]) | nxt["to_txn_id"].astype(str).isin([str(x.get("txn_id")) for x in txns])]
                # limit to avoid huge payload
                if len(nxt_sub) > inp.limit:
                    truncated = True
                    nxt_sub = nxt_sub.head(inp.limit)
                next_edges = nxt_sub.to_dict(orient="records")  # type: ignore
        except Exception:
            next_edges = []

        data: Dict[str, Any] = {"card": card, "transactions": txns, "next_edges": next_edges, "total_transactions": total}
        env = build_success_envelope(tool=tool, query=query, entity_ids=entity_ids, data=data, truncated=truncated, total_count=total, returned_count=len(txns), graph=GRAPH_NAME, kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="success", latency_ms=t.elapsed_ms(), truncated=truncated, source_kind="file_fallback")
        return env
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INTERNAL_ERROR, message=f"file_fallback failed: {e}", kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INTERNAL_ERROR"})
        return env


# ---------------------------------------------------------------------------
# calculate_exposure
# ---------------------------------------------------------------------------
def calculate_exposure(transaction_ids: List[str] | str, *, request_id: Optional[str] = None, case_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Accepts List[str] or comma-separated string (GSQL variant). Validates MAX_TX_IDS.
    Exposure = sum(amount) over affected_txn_ids (including flagged) — mounts TigerGraph calculate_exposure_list semantics.
    """
    tool = "calculate_exposure"
    query = "calculate_exposure_list"
    rid = request_id or new_request_id()
    t = Timer()

    # normalize input to List[str]
    if isinstance(transaction_ids, str):
        # GSQL csv variant: "3514030,3514031"
        ids = [s.strip() for s in transaction_ids.split(",") if s.strip()]
    else:
        ids = [str(x).strip() for x in (transaction_ids or [])]

    entity_ids = ids[:5]  # provenance sample (avoid huge list in source)

    try:
        inp = CalculateExposureInput(transaction_ids=ids, case_id=case_id)  # type: ignore[arg-type]
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INVALID_INPUT, message=str(e), kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INVALID_INPUT"})
        return env

    if not is_allowed(tool):
        env = policy_denied_envelope(tool, query)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "POLICY_DENIED"})
        return env

    rl = resource_limits()
    if len(inp.transaction_ids) > rl["MAX_TX_IDS"]:
        env = limit_exceeded_envelope(tool, query, f"transaction_ids count {len(inp.transaction_ids)} exceeds MAX_TX_IDS={rl['MAX_TX_IDS']}", entity_ids)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "RESOURCE_LIMIT_EXCEEDED"})
        return env

    if has_live_credentials():
        live_env = try_live_call(tool, query, entity_ids, {"txn_ids": inp.transaction_ids})
        if live_env is not None:
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status=live_env.get("status", "error"), latency_ms=t.elapsed_ms(), source_kind=live_env.get("source", {}).get("kind", "tigergraph_live"))
            return live_env

    try:
        tx = load_vertices("transaction")
        # amount column may be string or float
        tx_sub = tx[tx["txn_id"].astype(str).isin(inp.transaction_ids)].copy()
        if tx_sub.empty:
            # 0 exposure but still success — mirrors TigerGraph sum over 0 rows = 0
            data: Dict[str, Any] = {"matched_count": 0, "total_requested": len(inp.transaction_ids), "exposure_usd": 0.0, "matched_txn_ids": [], "missing_txn_ids": inp.transaction_ids}
            env = build_success_envelope(tool=tool, query=query, entity_ids=entity_ids, data=data, truncated=False, graph=GRAPH_NAME, kind=SourceKind.file_fallback)
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="success", latency_ms=t.elapsed_ms(), source_kind="file_fallback")
            return env
        # coerce amount
        import pandas as pd

        tx_sub["amount_num"] = pd.to_numeric(tx_sub["amount"], errors="coerce").fillna(0.0)
        exposure = float(tx_sub["amount_num"].sum())
        matched_ids = tx_sub["txn_id"].astype(str).tolist()
        missing = [x for x in inp.transaction_ids if x not in set(matched_ids)]
        data = {
            "matched_count": len(matched_ids),
            "total_requested": len(inp.transaction_ids),
            "exposure_usd": exposure,
            "matched_txn_ids": matched_ids,
            "missing_txn_ids": missing,
            # also expose matched rows (capped)
            "matched_transactions": tx_sub.drop(columns=["amount_num"]).head(rl["MAX_RESULTS"]).to_dict(orient="records"),  # type: ignore
        }
        truncated = len(matched_ids) > rl["MAX_RESULTS"]
        env = build_success_envelope(tool=tool, query=query, entity_ids=entity_ids, data=data, truncated=truncated, total_count=len(matched_ids), returned_count=min(len(matched_ids), rl["MAX_RESULTS"]), graph=GRAPH_NAME, kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="success", latency_ms=t.elapsed_ms(), truncated=truncated, source_kind="file_fallback")
        return env
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INTERNAL_ERROR, message=f"file_fallback failed: {e}", kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INTERNAL_ERROR"})
        return env
