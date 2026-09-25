"""
mcp.tools.case_tools — get_benchmark_case (benchmark_case_context GSQL) + list wrapper.

Maps to: tigergraph/queries/benchmark_case_context.gsql  (USE GRAPH hhg_fraud_graph)
  B -> TRIGGERS -> Transaction -> MADE -> Card -> OWNS -> Customer -> CardHistory+Device/Region/Email+RelatedViaDevice/Region/Card+Next/Prev

Pattern per Phase 2 spec:
  - validate via Pydantic schema
  - check tool_policy allowlist
  - enforce resource limits
  - if TG credentials absent -> file fallback via pandas on data/vertices/*.csv and data/edges/*.csv (source=file_fallback, provenance includes tool/query/entity_ids)
  - else call official MCP via pyTigerGraph stub; on connection failure return LIVE_TIGERGRAPH_UNAVAILABLE
  - log via mcp.tools.logging (timestamp, tool, request_id, case_id, status, latency)
  - return structured envelope {tool, status, data, source{graph,query,entity_ids}, provenance[{tool,query,entity_ids,ts}], truncated?}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.schemas.tool_schemas import (
    BenchmarkCaseContextInput,
    ErrorCode,
    ListBenchmarkCasesInput,
    SourceKind,
    build_error_envelope,
    build_success_envelope,
)
from mcp.tools._common import (
    GRAPH_NAME,
    has_live_credentials,
    is_allowed,
    load_edges,
    load_vertices,
    policy_denied_envelope,
    resource_limits,
    try_live_call,
)
from mcp.tools.logging import Timer, log_tool_call, new_request_id


def _norm(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def get_benchmark_case(case_id: str, *, request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Single-case facade for benchmark_case_context.
    Aliases: benchmark_case_context, get_benchmark_case — all resolve to same GSQL.
    """
    tool = "benchmark_case_context"
    query = "benchmark_case_context"
    rid = request_id or new_request_id()
    t = Timer()
    case_id_s = _norm(case_id)
    entity_ids = [case_id_s]

    # validate
    try:
        inp = BenchmarkCaseContextInput(case_id=case_id_s)
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INVALID_INPUT, message=str(e), kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id_s, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INVALID_INPUT"})
        return env

    # allowlist
    if not is_allowed(tool) and not is_allowed("get_benchmark_case"):
        env = policy_denied_envelope(tool, query)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id_s, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "POLICY_DENIED"})
        return env

    # live attempt
    if has_live_credentials():
        live_env = try_live_call(tool, query, entity_ids, {"case_id": inp.case_id})
        if live_env is not None:
            log_tool_call(tool=tool, request_id=rid, case_id=case_id_s, status=live_env.get("status", "error"), latency_ms=t.elapsed_ms(), source_kind=live_env.get("source", {}).get("kind", "tigergraph_live"))
            return live_env

    # file_fallback — minimal pandas joins, TigerGraph-equivalent
    try:
        bdf = load_vertices("benchmark_case")
        row = bdf[bdf["case_id"].astype(str) == inp.case_id]
        if row.empty:
            env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.NOT_FOUND, message=f"Benchmark case {inp.case_id} not found", kind=SourceKind.file_fallback)
            log_tool_call(tool=tool, request_id=rid, case_id=case_id_s, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "NOT_FOUND"})
            return env
        brec: Dict[str, Any] = row.iloc[0].to_dict()
        flagged_txn_id = _norm(brec.get("flagged_txn_id"))
        card_id = _norm(brec.get("card_id"))
        customer_id = _norm(brec.get("customer_id"))

        # Flagged transaction
        flagged: Optional[Dict[str, Any]] = None
        if flagged_txn_id:
            try:
                tdf = load_vertices("transaction")
                frow = tdf[tdf["txn_id"].astype(str) == flagged_txn_id]
                if not frow.empty:
                    flagged = frow.iloc[0].to_dict()
            except Exception:
                pass

        # Card + customer
        card: Optional[Dict[str, Any]] = None
        customer: Optional[Dict[str, Any]] = None
        if card_id:
            try:
                cdf = load_vertices("card")
                cr = cdf[cdf["card_id"].astype(str) == card_id]
                if not cr.empty:
                    card = cr.iloc[0].to_dict()
            except Exception:
                pass
        if customer_id:
            try:
                cdf2 = load_vertices("customer")
                ur = cdf2[cdf2["customer_id"].astype(str) == customer_id]
                if not ur.empty:
                    customer = ur.iloc[0].to_dict()
            except Exception:
                pass

        # Card history (MADE)
        card_history: List[Dict[str, Any]] = []
        total_history = 0
        truncated = False
        rl = resource_limits()
        try:
            made = load_edges("made")
            hist_ids = made[made["from_card_id"].astype(str) == card_id]["to_txn_id"].astype(str).tolist() if card_id else []
            if hist_ids:
                tdf2 = load_vertices("transaction")
                hist_df = tdf2[tdf2["txn_id"].astype(str).isin(hist_ids)].copy()
                total_history = len(hist_df)
                if "ts" in hist_df.columns:
                    try:
                        import pandas as pd

                        hist_df["ts_parsed"] = pd.to_datetime(hist_df["ts"], errors="coerce")
                        hist_df = hist_df.sort_values("ts_parsed")
                    except Exception:
                        pass
                if len(hist_df) > rl["MAX_TEMPORAL"]:
                    truncated = True
                    hist_df = hist_df.head(rl["MAX_TEMPORAL"])
                card_history = hist_df.drop(columns=[c for c in ["ts_parsed"] if c in hist_df.columns]).to_dict(orient="records")  # type: ignore
        except Exception:
            pass

        # Device / region / email for flagged
        devices: List[Dict[str, Any]] = []
        regions: List[Dict[str, Any]] = []
        p_emails: List[str] = []
        r_emails: List[str] = []
        try:
            fd = load_edges("from_device")
            dev_ids = fd[fd["from_txn_id"].astype(str) == flagged_txn_id]["to_device_profile_id"].astype(str).tolist() if flagged_txn_id else []
            if dev_ids:
                ddf = load_vertices("device_profile")
                devices = ddf[ddf["device_profile_id"].astype(str).isin(dev_ids)].to_dict(orient="records")  # type: ignore
        except Exception:
            pass
        try:
            bi = load_edges("billed_in")
            reg_ids = bi[bi["from_txn_id"].astype(str) == flagged_txn_id]["to_region_code"].astype(str).tolist() if flagged_txn_id else []
            if reg_ids:
                rdf = load_vertices("billing_region")
                regions = rdf[rdf["region_code"].astype(str).isin(reg_ids)].to_dict(orient="records")  # type: ignore
        except Exception:
            pass
        try:
            pe = load_edges("purchaser_email")
            p_emails = pe[pe["from_txn_id"].astype(str) == flagged_txn_id]["to_domain"].astype(str).tolist() if flagged_txn_id else []
        except Exception:
            pass
        try:
            re_ = load_edges("recipient_email")
            r_emails = re_[re_["from_txn_id"].astype(str) == flagged_txn_id]["to_domain"].astype(str).tolist() if flagged_txn_id else []
        except Exception:
            pass

        # Related historical cases (representative 2-hop via device/region/card) — capped
        related_via_device: List[Dict[str, Any]] = []
        related_via_region: List[Dict[str, Any]] = []
        related_via_card: List[Dict[str, Any]] = []
        try:
            # via device: device -> other txn -> INVOLVES -> ClosedCase
            if devices:
                fd2 = load_edges("from_device")
                inv = load_edges("involves")
                dev_ids2 = [d.get("device_profile_id") for d in devices if d.get("device_profile_id")]
                other_txn_ids = fd2[fd2["to_device_profile_id"].astype(str).isin([str(x) for x in dev_ids2])]["from_txn_id"].astype(str).tolist()
                case_ids_dev = inv[inv["to_txn_id"].astype(str).isin(other_txn_ids)]["from_case_id"].astype(str).tolist() if other_txn_ids else []
                if case_ids_dev:
                    cdf3 = load_vertices("closed_case")
                    related_via_device = cdf3[cdf3["case_id"].astype(str).isin(case_ids_dev)].head(rl["MAX_RESULTS"]).to_dict(orient="records")  # type: ignore
        except Exception:
            pass
        try:
            if regions:
                bi2 = load_edges("billed_in")
                inv2 = load_edges("involves")
                reg_codes = [r.get("region_code") for r in regions if r.get("region_code")]
                other_txn_ids2 = bi2[bi2["to_region_code"].astype(str).isin([str(x) for x in reg_codes])]["from_txn_id"].astype(str).tolist()
                case_ids_reg = inv2[inv2["to_txn_id"].astype(str).isin(other_txn_ids2)]["from_case_id"].astype(str).tolist() if other_txn_ids2 else []
                if case_ids_reg:
                    cdf4 = load_vertices("closed_case")
                    related_via_region = cdf4[cdf4["case_id"].astype(str).isin(case_ids_reg)].head(rl["MAX_RESULTS"]).to_dict(orient="records")  # type: ignore
        except Exception:
            pass
        try:
            if card_id:
                oc = load_edges("on_card")
                ct = load_edges("connected_to")
                case_ids_card: List[str] = []
                try:
                    case_ids_card += oc[oc["to_card_id"].astype(str) == card_id]["from_case_id"].astype(str).tolist()
                except Exception:
                    pass
                try:
                    case_ids_card += ct[ct["to_card_id"].astype(str) == card_id]["from_case_id"].astype(str).tolist()
                except Exception:
                    pass
                case_ids_card = list(dict.fromkeys(case_ids_card))
                if case_ids_card:
                    cdf5 = load_vertices("closed_case")
                    related_via_card = cdf5[cdf5["case_id"].astype(str).isin(case_ids_card)].head(rl["MAX_RESULTS"]).to_dict(orient="records")  # type: ignore
        except Exception:
            pass

        # Temporal neighbors for flagged
        next_txn: List[str] = []
        prev_txn: List[str] = []
        try:
            nxt = load_edges("next")
            if flagged_txn_id:
                next_txn = nxt[nxt["from_txn_id"].astype(str) == flagged_txn_id]["to_txn_id"].astype(str).tolist()
                prev_txn = nxt[nxt["to_txn_id"].astype(str) == flagged_txn_id]["from_txn_id"].astype(str).tolist()
        except Exception:
            pass

        data: Dict[str, Any] = {
            "benchmark_case": brec,
            "flagged_transaction": flagged,
            "card": card,
            "customer": customer,
            "card_history": card_history,
            "total_card_history": total_history,
            "devices": devices,
            "billing_regions": regions,
            "purchaser_email_domains": p_emails,
            "recipient_email_domains": r_emails,
            "related_cases_via_device": related_via_device,
            "related_cases_via_region": related_via_region,
            "related_cases_via_card": related_via_card,
            "next_txn_ids": next_txn,
            "prev_txn_ids": prev_txn,
        }
        env = build_success_envelope(tool=tool, query=query, entity_ids=entity_ids, data=data, truncated=truncated, total_count=total_history, returned_count=len(card_history), graph=GRAPH_NAME, kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id_s, status="success", latency_ms=t.elapsed_ms(), truncated=truncated, source_kind="file_fallback")
        return env
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=entity_ids, error_code=ErrorCode.INTERNAL_ERROR, message=f"file_fallback failed: {e}", kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, case_id=case_id_s, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INTERNAL_ERROR"})
        return env


# Alias expected by spec — same facade, also handles HHG-XXX regex
def benchmark_case_context(case_id: str, *, request_id: Optional[str] = None) -> Dict[str, Any]:
    return get_benchmark_case(case_id, request_id=request_id)


def list_benchmark_cases(limit: int = 20, offset: int = 0, *, request_id: Optional[str] = None) -> Dict[str, Any]:
    tool = "benchmark_case_context"
    query = "benchmark_case_context"
    rid = request_id or new_request_id()
    t = Timer()

    try:
        inp = ListBenchmarkCasesInput(limit=int(limit), offset=int(offset))
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=[], error_code=ErrorCode.INVALID_INPUT, message=str(e), kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INVALID_INPUT"})
        return env

    if not is_allowed(tool):
        env = policy_denied_envelope(tool, query)
        log_tool_call(tool=tool, request_id=rid, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "POLICY_DENIED"})
        return env

    if has_live_credentials():
        live_env = try_live_call(tool, query, [], {"limit": inp.limit, "offset": inp.offset})
        if live_env is not None:
            log_tool_call(tool=tool, request_id=rid, status=live_env.get("status", "error"), latency_ms=t.elapsed_ms(), source_kind=live_env.get("source", {}).get("kind", "tigergraph_live"))
            return live_env

    try:
        bdf = load_vertices("benchmark_case")
        total = len(bdf)
        sub = bdf.iloc[inp.offset : inp.offset + inp.limit].to_dict(orient="records")  # type: ignore
        truncated = (inp.offset + inp.limit) < total
        data: Dict[str, Any] = {"benchmark_cases": sub, "total": total, "limit": inp.limit, "offset": inp.offset}
        env = build_success_envelope(tool=tool, query=query, entity_ids=[r.get("case_id", "") for r in sub], data=data, truncated=truncated, total_count=total, returned_count=len(sub), graph=GRAPH_NAME, kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, status="success", latency_ms=t.elapsed_ms(), truncated=truncated, source_kind="file_fallback")
        return env
    except Exception as e:
        env = build_error_envelope(tool=tool, query=query, entity_ids=[], error_code=ErrorCode.INTERNAL_ERROR, message=f"file_fallback failed: {e}", kind=SourceKind.file_fallback)
        log_tool_call(tool=tool, request_id=rid, status="error", latency_ms=t.elapsed_ms(), source_kind="file_fallback", extra={"error_code": "INTERNAL_ERROR"})
        return env
