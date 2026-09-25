"""
mcp.tools.history_tools — find_related_cases, get_temporal_chain (with limit)

Pattern: validate -> allowlist -> enforce limits -> live attempt -> file_fallback -> envelope + log.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.schemas.tool_schemas import ErrorCode, FindRelatedCasesInput, GetTemporalChainInput, SourceKind, build_error_envelope, build_success_envelope
from mcp.tools._common import GRAPH_NAME, has_live_credentials, is_allowed, limit_exceeded_envelope, load_edges, load_vertices, policy_denied_envelope, resource_limits, try_live_call
from mcp.tools.logging import Timer, log_tool_call, new_request_id


# ---------------------------------------------------------------------------
# find_related_cases
# ---------------------------------------------------------------------------
def find_related_cases(
    txn_id: Optional[str] = None,
    card_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    device_profile_id: Optional[str] = None,
    region_code: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = 50,
    *,
    request_id: Optional[str] = None,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    tool = "find_related_cases"
    query = "find_related_cases"
    rid = request_id or new_request_id()
    t = Timer()
    entity_ids: List[str] = [x for x in [txn_id, card_id, customer_id, device_profile_id, region_code, domain] if x]

    try:
        inp = FindRelatedCasesInput(
            txn_id=txn_id,
            card_id=card_id,
            customer_id=customer_id,
            device_profile_id=device_profile_id,
            region_code=region_code,
            domain=domain,
            limit=int(limit),
        )
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
        payload: Dict[str, Any] = {
            "txn_id": inp.txn_id or "",
            "card_id": inp.card_id or "",
            "customer_id": inp.customer_id or "",
            "device_profile_id": inp.device_profile_id or "",
            "region_code": inp.region_code or "",
            "domain": inp.domain or "",
            "limit": inp.limit,
        }
        live_env = try_live_call(tool, query, entity_ids, payload)
        if live_env is not None:
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status=live_env.get("status", "error"), latency_ms=t.elapsed_ms(), source_kind=live_env.get("source", {}).get("kind", "tigergraph_live"))
            return live_env

    try:
        # Collect ClosedCase IDs via verified paths (mirrors find_related_cases.gsql):
        # txn -> INVOLVES reverse, txn->device->other txn->case, card ON_CARD/CONNECTED_TO, customer OWNS->card ON_CARD, device->txn->case, region->txn->case, email->txn->case
        collected: List[str] = []

        # via txn direct + device hop
        if inp.txn_id:
            try:
                inv = load_edges("involves")
                direct = inv[inv["to_txn_id"].astype(str) == inp.txn_id]["from_case_id"].astype(str).tolist()
                collected += direct
            except Exception:
                pass
            # device hop
            try:
                fd = load_edges("from_device")
                inv2 = load_edges("involves")
                dev_ids = fd[fd["from_txn_id"].astype(str) == inp.txn_id]["to_device_profile_id"].astype(str).tolist()
                if dev_ids:
                    other_txns = fd[fd["to_device_profile_id"].astype(str).isin(dev_ids)]["from_txn_id"].astype(str).tolist()
                    if other_txns:
                        dev_cases = inv2[inv2["to_txn_id"].astype(str).isin(other_txns)]["from_case_id"].astype(str).tolist()
                        collected += dev_cases
            except Exception:
                pass

        if inp.card_id:
            try:
                oc = load_edges("on_card")
                ct = load_edges("connected_to")
                collected += oc[oc["to_card_id"].astype(str) == inp.card_id]["from_case_id"].astype(str).tolist()
                collected += ct[ct["to_card_id"].astype(str) == inp.card_id]["from_case_id"].astype(str).tolist()
            except Exception:
                pass

        if inp.customer_id:
            try:
                owns = load_edges("owns")
                oc2 = load_edges("on_card")
                card_ids = owns[owns["from_customer_id"].astype(str) == inp.customer_id]["to_card_id"].astype(str).tolist()
                if card_ids:
                    collected += oc2[oc2["to_card_id"].astype(str).isin(card_ids)]["from_case_id"].astype(str).tolist()
            except Exception:
                pass

        if inp.device_profile_id:
            try:
                fd3 = load_edges("from_device")
                inv3 = load_edges("involves")
                other_txns2 = fd3[fd3["to_device_profile_id"].astype(str) == inp.device_profile_id]["from_txn_id"].astype(str).tolist()
                if other_txns2:
                    collected += inv3[inv3["to_txn_id"].astype(str).isin(other_txns2)]["from_case_id"].astype(str).tolist()
            except Exception:
                pass

        if inp.region_code:
            try:
                bi = load_edges("billed_in")
                inv4 = load_edges("involves")
                other_txns3 = bi[bi["to_region_code"].astype(str) == inp.region_code]["from_txn_id"].astype(str).tolist()
                if other_txns3:
                    collected += inv4[inv4["to_txn_id"].astype(str).isin(other_txns3)]["from_case_id"].astype(str).tolist()
            except Exception:
                pass

        if inp.domain:
            try:
                pe = load_edges("purchaser_email")
                re_ = load_edges("recipient_email")
                inv5 = load_edges("involves")
                tx_p = pe[pe["to_domain"].astype(str) == inp.domain]["from_txn_id"].astype(str).tolist()
                tx_r = re_[re_["to_domain"].astype(str) == inp.domain]["from_txn_id"].astype(str).tolist()
                tx_all = list(dict.fromkeys(tx_p + tx_r))
                if tx_all:
                    collected += inv5[inv5["to_txn_id"].astype(str).isin(tx_all)]["from_case_id"].astype(str).tolist()
            except Exception:
                pass

        # dedup + sort
        uniq = list(dict.fromkeys([str(x) for x in collected if x]))
        total = len(uniq)
        truncated = False
        if len(uniq) > inp.limit:
            truncated = True
            uniq = uniq[: inp.limit]

        # materialize cases
        cases: List[Dict[str, Any]] = []
        try:
            if uniq:
                cdf = load_vertices("closed_case")
                cdf_sub = cdf[cdf["case_id"].astype(str).isin(uniq)].head(inp.limit).to_dict(orient="records")  # type: ignore
                # preserve order of uniq
                order = {cid: i for i, cid in enumerate(uniq)}
                cdf_sub_sorted = sorted(cdf_sub, key=lambda r: order.get(str(r.get("case_id")), 9999))
                cases = cdf_sub_sorted
        except Exception:
            cases = [{"case_id": cid} for cid in uniq]

        data: Dict[str, Any] = {"related_case_ids": uniq, "related_cases": cases, "total_found": total}
        env = build_success_envelope(tool=tool, query=query, entity_ids=entity_ids, data=data, truncated=truncated, total_count=total, returned_count=len(uniq), graph=GRAPH_NAME, kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="success", latency_ms=t.elapsed_ms(), truncated=truncated, source_kind="file_fallback")
        return env
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INTERNAL_ERROR, message=f"file_fallback failed: {e}", kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INTERNAL_ERROR"})
        return env


# ---------------------------------------------------------------------------
# get_temporal_chain
# ---------------------------------------------------------------------------
def get_temporal_chain(card_id: str, limit: int = 200, *, request_id: Optional[str] = None, case_id: Optional[str] = None) -> Dict[str, Any]:
    tool = "get_temporal_chain"
    query = "temporal_chain"
    rid = request_id or new_request_id()
    t = Timer()
    entity_ids = [str(card_id)]

    try:
        inp = GetTemporalChainInput(card_id=str(card_id), limit=int(limit))
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INVALID_INPUT, message=str(e), kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INVALID_INPUT"})
        return env

    if not is_allowed(tool):
        # also allow alias temporal_chain
        if not is_allowed("get_temporal_chain"):
            env = policy_denied_envelope(tool, query)
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "POLICY_DENIED"})
            return env

    rl = resource_limits()
    if inp.limit > rl["MAX_TEMPORAL"]:
        env = limit_exceeded_envelope(tool, query, f"limit {inp.limit} exceeds MAX_TEMPORAL={rl['MAX_TEMPORAL']}", entity_ids)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "RESOURCE_LIMIT_EXCEEDED"})
        return env

    if has_live_credentials():
        live_env = try_live_call(tool, query, entity_ids, {"card_id": inp.card_id, "limit": inp.limit})
        if live_env is not None:
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status=live_env.get("status", "error"), latency_ms=t.elapsed_ms(), source_kind=live_env.get("source", {}).get("kind", "tigergraph_live"))
            return live_env

    try:
        cdf = load_vertices("card")
        crow = cdf[cdf["card_id"].astype(str) == inp.card_id]
        if crow.empty:
            env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.NOT_FOUND, message=f"Card {inp.card_id} not found", kind=SourceKind.file_fallback)
            log_tool_call(tool=tool, request_id=rid, case_id=case_id, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "NOT_FOUND"})
            return env
        card = crow.iloc[0].to_dict()

        made = load_edges("made")
        txn_ids = made[made["from_card_id"].astype(str) == inp.card_id]["to_txn_id"].astype(str).tolist()
        tx = load_vertices("transaction")
        sub = tx[tx["txn_id"].astype(str).isin(txn_ids)].copy() if txn_ids else tx.head(0).copy()
        total = len(sub)
        truncated = False

        if "ts" in sub.columns and not sub.empty:
            try:
                import pandas as pd

                sub["ts_parsed"] = pd.to_datetime(sub["ts"], errors="coerce")
                sub = sub.sort_values("ts_parsed")
            except Exception:
                pass

        if len(sub) > inp.limit:
            truncated = True
            sub = sub.head(inp.limit)

        txns = sub.drop(columns=[c for c in ["ts_parsed"] if c in sub.columns]).to_dict(orient="records")  # type: ignore

        # NEXT edges among this chain (preserve temporal ordering edges)
        next_edges: List[Dict[str, Any]] = []
        try:
            nxt = load_edges("next")
            if txn_ids:
                # edges where from in chain
                nid_set = set(str(r.get("txn_id")) for r in txns)
                # also include outgoing from capped set + incoming to capped set for continuity
                nxt_sub = nxt[nxt["from_txn_id"].astype(str).isin(nid_set) | nxt["to_txn_id"].astype(str).isin(nid_set)]
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
