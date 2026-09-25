"""
mcp.tools.relationship_tools — find_device_connections, find_related_transactions (with max_hops, truncated)

Pattern: validate -> allowlist -> enforce limits (MAX_HOPS, MAX_RESULTS) -> live attempt -> file_fallback (pandas) -> envelope + log.
File fallback uses minimal pandas joins to mirror TigerGraph GSQL traversals.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.schemas.tool_schemas import ErrorCode, FindDeviceConnectionsInput, FindRelatedTransactionsInput, SourceKind, build_error_envelope, build_success_envelope
from mcp.tools._common import GRAPH_NAME, has_live_credentials, is_allowed, limit_exceeded_envelope, load_edges, load_vertices, policy_denied_envelope, resource_limits, try_live_call
from mcp.tools.logging import Timer, log_tool_call, new_request_id


# ---------------------------------------------------------------------------
# find_device_connections
# ---------------------------------------------------------------------------
def find_device_connections(
    txn_id: Optional[str] = None,
    device_profile_id: Optional[str] = None,
    limit: int = 100,
    *,
    request_id: Optional[str] = None,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    tool = "find_device_connections"
    query = "find_device_connections"
    rid = request_id or new_request_id()
    t = Timer()
    # ensure entity_ids are strings (provenance validation requires string)
    txn_id = str(txn_id) if txn_id is not None and str(txn_id).strip() != "" else None
    device_profile_id = str(device_profile_id) if device_profile_id is not None and str(device_profile_id).strip() != "" else None
    entity_ids: List[str] = [str(x) for x in [txn_id, device_profile_id] if x]

    # validate (limit bounds included via schema)
    try:
        inp = FindDeviceConnectionsInput(txn_id=txn_id, device_profile_id=device_profile_id, limit=int(limit))
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
        payload: Dict[str, Any] = {"txn_id": inp.txn_id or "", "device_profile_id": inp.device_profile_id or "", "limit": inp.limit}
        live_env = try_live_call(tool, query, entity_ids, payload)
        if live_env is not None:
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status=live_env.get("status", "error"), latency_ms=t.elapsed_ms(), source_kind=live_env.get("source", {}).get("kind", "tigergraph_live"))
            return live_env

    try:
        # Resolve device IDs
        device_ids: List[str] = []
        if inp.txn_id:
            fd = load_edges("from_device")
            device_ids = fd[fd["from_txn_id"].astype(str) == inp.txn_id]["to_device_profile_id"].astype(str).tolist()
        if inp.device_profile_id:
            device_ids.append(inp.device_profile_id)
        device_ids = list(dict.fromkeys([str(x) for x in device_ids if x]))

        if not device_ids:
            env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.NOT_FOUND, message="NO_DEVICE_FOUND: no DeviceProfile for seed", kind=SourceKind.file_fallback)
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "NOT_FOUND"})
            return env

        # Devices
        try:
            ddf = load_vertices("device_profile")
            devices = ddf[ddf["device_profile_id"].astype(str).isin(device_ids)].to_dict(orient="records")  # type: ignore
        except Exception:
            devices = [{"device_profile_id": did} for did in device_ids]

        # Linked transactions: DeviceProfile -> Transaction (FROM_DEVICE reverse)
        fd2 = load_edges("from_device")
        linked_txn_ids = fd2[fd2["to_device_profile_id"].astype(str).isin(device_ids)]["from_txn_id"].astype(str).tolist()
        linked_txn_ids = list(dict.fromkeys(linked_txn_ids))
        total_txns = len(linked_txn_ids)
        truncated = False
        if len(linked_txn_ids) > inp.limit:
            truncated = True
            linked_txn_ids = linked_txn_ids[: inp.limit]

        # Linked cards/customers via MADE + OWNS
        linked_cards: List[Dict[str, Any]] = []
        linked_customers: List[Dict[str, Any]] = []
        try:
            if linked_txn_ids:
                tdf = load_vertices("transaction")
                # map txn -> card
                txn_to_card = tdf[tdf["txn_id"].astype(str).isin(linked_txn_ids)][["txn_id", "card_id", "customer_id"]].copy()
                card_ids = txn_to_card["card_id"].astype(str).unique().tolist()
                if card_ids:
                    cdf = load_vertices("card")
                    linked_cards_full = cdf[cdf["card_id"].astype(str).isin(card_ids)].to_dict(orient="records")  # type: ignore
                    # respect MAX_RESULTS for cards as well
                    if len(linked_cards_full) > rl["MAX_RESULTS"]:
                        truncated = True
                        linked_cards_full = linked_cards_full[: rl["MAX_RESULTS"]]
                    linked_cards = linked_cards_full
                    # customers via OWNS or txn customer_id
                    owns = load_edges("owns")
                    cust_ids = owns[owns["to_card_id"].astype(str).isin(card_ids)]["from_customer_id"].astype(str).tolist()
                    if not cust_ids:
                        cust_ids = txn_to_card["customer_id"].astype(str).unique().tolist()
                    cust_ids = list(dict.fromkeys([str(x) for x in cust_ids if x]))
                    if cust_ids:
                        custdf = load_vertices("customer")
                        linked_customers = custdf[custdf["customer_id"].astype(str).isin(cust_ids)].head(rl["MAX_RESULTS"]).to_dict(orient="records")  # type: ignore
        except Exception:
            pass

        # Also expose linked_txn rows (capped)
        linked_transactions: List[Dict[str, Any]] = []
        try:
            if linked_txn_ids:
                tdf2 = load_vertices("transaction")
                linked_transactions = tdf2[tdf2["txn_id"].astype(str).isin(linked_txn_ids)].head(rl["MAX_RESULTS"]).to_dict(orient="records")  # type: ignore
        except Exception:
            linked_transactions = []

        data: Dict[str, Any] = {
            "seed_device_ids": device_ids,
            "devices": devices,
            "linked_transaction_ids": linked_txn_ids,
            "linked_transactions": linked_transactions,
            "linked_cards": linked_cards,
            "linked_customers": linked_customers,
            "total_linked_transactions": total_txns,
        }
        env = build_success_envelope(tool=tool, query=query, entity_ids=entity_ids, data=data, truncated=truncated, total_count=total_txns, returned_count=len(linked_txn_ids), graph=GRAPH_NAME, kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="success", latency_ms=t.elapsed_ms(), truncated=truncated, source_kind="file_fallback")
        return env
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INTERNAL_ERROR, message=f"file_fallback failed: {e}", kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INTERNAL_ERROR"})
        return env


# ---------------------------------------------------------------------------
# find_related_transactions
# ---------------------------------------------------------------------------
def find_related_transactions(
    txn_id: Optional[str] = None,
    card_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    max_hops: int = 1,
    limit: int = 100,
    *,
    request_id: Optional[str] = None,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    tool = "find_related_transactions"
    query = "find_related_transactions"
    rid = request_id or new_request_id()
    t = Timer()
    txn_id = str(txn_id) if txn_id is not None and str(txn_id).strip() != "" else None
    card_id = str(card_id) if card_id is not None and str(card_id).strip() != "" else None
    customer_id = str(customer_id) if customer_id is not None and str(customer_id).strip() != "" else None
    entity_ids: List[str] = [str(x) for x in [txn_id, card_id, customer_id] if x]

    try:
        inp = FindRelatedTransactionsInput(txn_id=txn_id, card_id=card_id, customer_id=customer_id, max_hops=int(max_hops), limit=int(limit))
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INVALID_INPUT, message=str(e), kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INVALID_INPUT"})
        return env

    if not is_allowed(tool):
        env = policy_denied_envelope(tool, query)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "POLICY_DENIED"})
        return env

    rl = resource_limits()
    if inp.max_hops > rl["MAX_HOPS"]:
        env = limit_exceeded_envelope(tool, query, f"max_hops {inp.max_hops} exceeds MAX_HOPS={rl['MAX_HOPS']}", entity_ids)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "RESOURCE_LIMIT_EXCEEDED"})
        return env
    if inp.limit > rl["MAX_RESULTS"]:
        env = limit_exceeded_envelope(tool, query, f"limit {inp.limit} exceeds MAX_RESULTS={rl['MAX_RESULTS']}", entity_ids)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "RESOURCE_LIMIT_EXCEEDED"})
        return env

    if has_live_credentials():
        payload: Dict[str, Any] = {"txn_id": inp.txn_id or "", "card_id": inp.card_id or "", "customer_id": inp.customer_id or "", "max_hops": inp.max_hops, "limit": inp.limit}
        live_env = try_live_call(tool, query, entity_ids, payload)
        if live_env is not None:
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status=live_env.get("status", "error"), latency_ms=t.elapsed_ms(), source_kind=live_env.get("source", {}).get("kind", "tigergraph_live"))
            return live_env

    try:
        # Resolve seed transaction IDs
        seed_txn_ids: List[str] = []
        if inp.txn_id:
            seed_txn_ids = [inp.txn_id]
        elif inp.card_id:
            made = load_edges("made")
            seed_txn_ids = made[made["from_card_id"].astype(str) == inp.card_id]["to_txn_id"].astype(str).tolist()
        elif inp.customer_id:
            owns = load_edges("owns")
            made2 = load_edges("made")
            card_ids = owns[owns["from_customer_id"].astype(str) == inp.customer_id]["to_card_id"].astype(str).tolist()
            if card_ids:
                seed_txn_ids = made2[made2["from_card_id"].astype(str).isin(card_ids)]["to_txn_id"].astype(str).tolist()

        if not seed_txn_ids:
            env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.NOT_FOUND, message="NO_SEED: no transactions for seed", kind=SourceKind.file_fallback)
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "NOT_FOUND"})
            return env

        # Build related sets via verified edges (file_fallback mirrors GSQL query E)
        # Via card, region, device, purchaser email, recipient email
        tdf = load_vertices("transaction")
        # For related expansion we need seed's attributes: card_id, region, device, emails
        seed_rows = tdf[tdf["txn_id"].astype(str).isin(seed_txn_ids)] if seed_txn_ids else tdf.head(0)
        # Via card: MADE -> Card -> MADE
        via_card_ids: List[str] = []
        try:
            made = load_edges("made")
            # collect card_ids for seeds
            seed_card_ids = seed_rows["card_id"].astype(str).unique().tolist() if not seed_rows.empty else []
            if inp.card_id:
                seed_card_ids = [inp.card_id]
            if seed_card_ids:
                via_card_ids = made[made["from_card_id"].astype(str).isin(seed_card_ids)]["to_txn_id"].astype(str).tolist()
        except Exception:
            via_card_ids = []

        # Via region: BILLED_IN bridge
        via_region_ids: List[str] = []
        try:
            bi = load_edges("billed_in")
            seed_regions = bi[bi["from_txn_id"].astype(str).isin(seed_txn_ids)]["to_region_code"].astype(str).tolist()
            if seed_regions:
                via_region_ids = bi[bi["to_region_code"].astype(str).isin(seed_regions)]["from_txn_id"].astype(str).tolist()
        except Exception:
            pass

        # Via device: FROM_DEVICE bridge
        via_device_ids: List[str] = []
        try:
            fd = load_edges("from_device")
            seed_devices = fd[fd["from_txn_id"].astype(str).isin(seed_txn_ids)]["to_device_profile_id"].astype(str).tolist()
            if seed_devices:
                via_device_ids = fd[fd["to_device_profile_id"].astype(str).isin(seed_devices)]["from_txn_id"].astype(str).tolist()
        except Exception:
            pass

        # Via purchaser / recipient email
        via_pemail_ids: List[str] = []
        via_remail_ids: List[str] = []
        try:
            pe = load_edges("purchaser_email")
            seed_p = pe[pe["from_txn_id"].astype(str).isin(seed_txn_ids)]["to_domain"].astype(str).tolist()
            if seed_p:
                via_pemail_ids = pe[pe["to_domain"].astype(str).isin(seed_p)]["from_txn_id"].astype(str).tolist()
        except Exception:
            pass
        try:
            re_ = load_edges("recipient_email")
            seed_r = re_[re_["from_txn_id"].astype(str).isin(seed_txn_ids)]["to_domain"].astype(str).tolist()
            if seed_r:
                via_remail_ids = re_[re_["to_domain"].astype(str).isin(seed_r)]["from_txn_id"].astype(str).tolist()
        except Exception:
            pass

        # Deduplicate and cap each set, also compute truncated
        def _cap(ids: List[str]) -> tuple[List[str], bool]:
            uniq = list(dict.fromkeys([str(x) for x in ids if x]))
            # exclude seeds from related for clarity (TigerGraph query keeps them but caller filters)
            # keep them here but mark — we keep as-is to match GSQL PRINT (includes seeds)
            if len(uniq) > inp.limit:
                return uniq[: inp.limit], True
            return uniq, False

        via_card_ids, t1 = _cap(via_card_ids)
        via_region_ids, t2 = _cap(via_region_ids)
        via_device_ids, t3 = _cap(via_device_ids)
        via_pemail_ids, t4 = _cap(via_pemail_ids)
        via_remail_ids, t5 = _cap(via_remail_ids)
        truncated = any([t1, t2, t3, t4, t5])

        # For data payload, also materialize a few rows for each bucket (capped)
        def _rows_for(ids: List[str]) -> List[Dict[str, Any]]:
            if not ids:
                return []
            sub = tdf[tdf["txn_id"].astype(str).isin(ids)].head(rl["MAX_RESULTS"])
            # sort by ts for readability
            if "ts" in sub.columns:
                try:
                    import pandas as pd

                    sub = sub.copy()
                    sub["ts_parsed"] = pd.to_datetime(sub["ts"], errors="coerce")
                    sub = sub.sort_values("ts_parsed").drop(columns=["ts_parsed"])
                except Exception:
                    pass
            return sub.to_dict(orient="records")  # type: ignore

        data: Dict[str, Any] = {
            "seed_txn_ids": seed_txn_ids[: inp.limit],
            "via_card_ids": via_card_ids,
            "via_region_ids": via_region_ids,
            "via_device_ids": via_device_ids,
            "via_p_email_ids": via_pemail_ids,
            "via_r_email_ids": via_remail_ids,
            # sample rows
            "via_card": _rows_for(via_card_ids),
            "via_region": _rows_for(via_region_ids),
            "via_device": _rows_for(via_device_ids),
            "via_p_email": _rows_for(via_pemail_ids),
            "via_r_email": _rows_for(via_remail_ids),
            "max_hops": inp.max_hops,
        }
        # also report combined unique count
        combined = list(dict.fromkeys(via_card_ids + via_region_ids + via_device_ids + via_pemail_ids + via_remail_ids))
        total = len(combined)
        env = build_success_envelope(tool=tool, query=query, entity_ids=entity_ids, data=data, truncated=truncated, total_count=total, returned_count=min(total, inp.limit), graph=GRAPH_NAME, kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="success", latency_ms=t.elapsed_ms(), truncated=truncated, source_kind="file_fallback")
        return env
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INTERNAL_ERROR, message=f"file_fallback failed: {e}", kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INTERNAL_ERROR"})
        return env
