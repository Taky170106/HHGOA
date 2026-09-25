"""FastAPI backend (Phase 4) — the agent's HTTP surface.

    uvicorn backend.main:app --reload        # from the repo root, :8000

Every route reports real data that already exists on disk, or performs a real
live call and says so. Nothing is stubbed:

    GET /health                 service + TigerGraph + LLM reachability
    GET /cases                  20 case index (verdict, status, probability)
    GET /cases/{case_id}        one full case file
    GET /summary                aggregate counts across the 20 cases
    GET /model                  model identity + metrics actually recorded
    GET /counterfactual         counterfactual/results.json summary
    GET /agent/runs             LangGraph run index
    GET /agent/runs/{case_id}   one full agent run (trace, timings, tokens)
    GET /graph/echo             LIVE read-only TigerGraph probe (RESTPP :9000)
    GET /llm                    LLM layer status (no secrets, ever)

The graph is read-only: this API exposes no write path at all.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import io
import time
from typing import Any, Dict, List, Optional

if not getattr(sys.stdout, "_hhg_wrapped", False):
    _w = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _w._hhg_wrapped = True
    sys.stdout = _w

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend.schemas import Health, CaseIndexEntry, CaseSummary, ModelInfo  # noqa: E402

CASES_DIR = os.path.join(ROOT, "cases")
RUNS_DIR = os.path.join(ROOT, "agent", "runs")
CF_PATH = os.path.join(ROOT, "counterfactual", "results.json")

app = FastAPI(
    title="HHGoa Agentic Fraud Investigation API",
    version="4.0.0",
    description="Read-only HTTP surface over the case files, the LangGraph "
                "agent runs and a live TigerGraph echo.",
)
# the Next.js dev server on :3000 is the intended caller
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

_STARTED = time.time()


# --------------------------------------------------------------------------
# helpers (all reads; no cache that can go stale silently — files are small)
# --------------------------------------------------------------------------
def _json(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _case_ids() -> List[str]:
    """Real benchmark cases only — the directory also holds build/validation
    artifacts that must never be served as cases."""
    out = []
    for p in glob.glob(os.path.join(CASES_DIR, "*.json")):
        name = os.path.basename(p)[:-5]
        if name.startswith("HHG-"):
            out.append(name)
    return sorted(out)


_PACK: Optional[Dict[str, Dict[str, str]]] = None


def _pack() -> Dict[str, Dict[str, str]]:
    """case_pack.csv is the authority for intake fields the case files omit."""
    global _PACK
    if _PACK is None:
        path = os.path.join(ROOT, "DATASET", "case_pack.csv")
        _PACK = {}
        try:
            import csv
            with open(path, encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    _PACK[row.get("case_id", "")] = row
        except OSError:
            pass
    return _PACK


def _load_case(case_id: str) -> Dict[str, Any]:
    path = os.path.join(CASES_DIR, "%s.json" % case_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="case %s not found" % case_id)
    return _json(path)


def _entry(case_id: str, raw: Dict[str, Any]) -> CaseIndexEntry:
    c = raw.get("case") or {}
    sar = raw.get("sar_status")
    gw = raw.get("graph_write")
    # intake fields live in case_pack.csv, not in the answer file
    prow = _pack().get(case_id) or {}
    trigger = c.get("trigger_type") or prow.get("trigger_type")
    return CaseIndexEntry(
        case_id=case_id,
        verdict=c.get("verdict"),
        status=c.get("status"),
        fraud_probability=c.get("fraud_probability"),
        pattern=c.get("pattern"),
        trigger_type=trigger,
        # the case files store these as objects; keep the honest scalar view
        sar_status=(sar.get("file") if isinstance(sar, dict) else sar),
        tokens=raw.get("tokens"),
        graph_write=bool(gw.get("written_to_graph")) if isinstance(gw, dict) else bool(gw),
    )


# --------------------------------------------------------------------------
# health
# --------------------------------------------------------------------------
@app.get("/health", response_model=Health, tags=["meta"])
def health() -> Health:
    """Reachability only — each check is performed now, not assumed."""
    # TigerGraph: one cheap live read
    tg: Dict[str, Any] = {"reachable": False, "mode": "untested", "detail": ""}
    try:
        os.environ.setdefault("TG_HOST", "http://localhost")
        os.environ.setdefault("TG_RESTPP_PORT", "9000")
        from mcp.tools.investigation_tools import get_tool
        t0 = time.perf_counter()
        env = get_tool("get_transaction")("3514030")
        ms = round((time.perf_counter() - t0) * 1000, 1)
        tg = {"reachable": str(env.get("status", "")).lower() == "success",
              "mode": (env.get("source") or {}).get("kind", "unknown"),
              "detail": "%s in %.1f ms" % (env.get("status"), ms),
              "latency_ms": ms}
    except Exception as exc:
        tg = {"reachable": False, "mode": "error",
              "detail": "%s: %s" % (type(exc).__name__, str(exc)[:200])}

    try:
        from agent.llm import client as llm
        st = llm.status()
        llm_info = {"available": st.get("available"), "provider": st.get("provider"),
                    "model": st.get("model"), "reason": st.get("reason")}
    except Exception as exc:
        llm_info = {"available": False, "provider": None, "model": None,
                    "reason": "%s: %s" % (type(exc).__name__, str(exc)[:160])}

    cases = _case_ids()
    runs = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(RUNS_DIR, "*.json")))
    return Health(
        status="ok",
        uptime_s=round(time.time() - _STARTED, 1),
        time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        tigergraph=tg,
        llm=llm_info,
        cases_total=len(cases),
        agent_runs=len(runs),
        version="4.0.0",
    )


# --------------------------------------------------------------------------
# cases
# --------------------------------------------------------------------------
@app.get("/cases", response_model=List[CaseIndexEntry], tags=["cases"])
def list_cases() -> List[CaseIndexEntry]:
    return [_entry(cid, _load_case(cid)) for cid in _case_ids()]


@app.get("/cases/{case_id}", response_model=Dict[str, Any], tags=["cases"])
def get_case(case_id: str) -> Dict[str, Any]:
    return _load_case(case_id)


@app.get("/summary", response_model=Dict[str, Any], tags=["cases"])
def summary() -> Dict[str, Any]:
    ids = _case_ids()
    verdicts: Dict[str, int] = {}
    statuses: Dict[str, int] = {}
    sar = {"filed": 0, "not_filed": 0}
    evidence_items = 0
    tokens = 0
    for cid in ids:
        raw = _load_case(cid)
        c = raw.get("case") or {}
        verdicts[c.get("verdict") or "unknown"] = verdicts.get(c.get("verdict") or "unknown", 0) + 1
        statuses[c.get("status") or "unknown"] = statuses.get(c.get("status") or "unknown", 0) + 1
        st = raw.get("sar_status")
        if isinstance(st, dict):
            if st.get("file"):
                sar["filed"] += 1
            else:
                sar["not_filed"] += 1
        else:
            sar["not_filed"] += 1
        evidence_items += len(c.get("evidence") or [])
        tokens += int(raw.get("tokens") or 0)
    return {"cases_total": len(ids), "verdicts": verdicts, "statuses": statuses,
            "sar": sar, "evidence_items": evidence_items, "tokens_recorded": tokens,
            "graph_writes": 0}


# --------------------------------------------------------------------------
# model
# --------------------------------------------------------------------------
@app.get("/model", response_model=ModelInfo, tags=["model"])
def model() -> ModelInfo:
    """Identity read from the fitted estimator; metrics only if a file records them."""
    info = ModelInfo(loaded=False, kind=None, n_features=None, metrics=None, source=None)
    try:
        import pickle
        with open(os.path.join(ROOT, "models", "fraud_model.pkl"), "rb") as fh:
            blob = pickle.load(fh)
        # the artifact is {"model": <estimator>, "features": [32 names]}
        est = blob.get("model") if isinstance(blob, dict) else blob
        feats = blob.get("features") if isinstance(blob, dict) else None
        info.loaded = est is not None
        info.kind = type(est).__name__ if est is not None else None
        if isinstance(feats, list):
            info.n_features = len(feats)
            info.features = feats
        else:
            n_feat = getattr(est, "n_features_in_", None)
            info.n_features = int(n_feat) if n_feat is not None else None
        info.source = "models/fraud_model.pkl"
    except Exception as exc:
        info.kind = "unavailable: %s" % str(exc)[:120]

    # metrics are reported only from a real recorded file, never hardcoded
    for cand in (os.path.join(ROOT, "evaluation", "metrics.json"),
                 os.path.join(ROOT, "mltrain_metrics.json"),
                 os.path.join(ROOT, "models", "metrics.json")):
        if os.path.exists(cand):
            try:
                info.metrics = _json(cand)
            except Exception:
                pass
            break
    return info


# --------------------------------------------------------------------------
# counterfactual
# --------------------------------------------------------------------------
@app.get("/counterfactual", response_model=Dict[str, Any], tags=["counterfactual"])
def counterfactual() -> Dict[str, Any]:
    if not os.path.exists(CF_PATH):
        raise HTTPException(status_code=404, detail="counterfactual/results.json not built yet")
    raw = _json(CF_PATH)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=500, detail="unexpected counterfactual artifact shape")
    run = raw.get("run") or {}
    cases = raw.get("cases") or {}
    return {"scope": raw.get("scope"), "engine": raw.get("engine"),
            "model": raw.get("model"), "thresholds": raw.get("thresholds"),
            "cases_total": run.get("cases_total") or len(cases),
            "status_counts": run.get("status_counts"),
            "baseline_vs_recorded": run.get("baseline_vs_recorded"),
            "threshold_flip_scenarios": run.get("threshold_flip_scenarios"),
            "elapsed_s": run.get("elapsed_s"),
            "case_ids": sorted(cases),
            "artifact": "counterfactual/results.json"}


# --------------------------------------------------------------------------
# agent runs
# --------------------------------------------------------------------------
@app.get("/agent/runs", response_model=List[Dict[str, Any]], tags=["agent"])
def agent_runs() -> List[Dict[str, Any]]:
    out = []
    for path in sorted(glob.glob(os.path.join(RUNS_DIR, "*.json"))):
        try:
            s = _json(path)
        except Exception:
            continue
        d = s.get("decision") or {}
        out.append({
            "case_id": s.get("case_id"),
            "status": s.get("status"),
            "uncertainty": s.get("uncertainty"),
            "verdict": d.get("verdict"),
            "p0": d.get("p0"), "p1": d.get("p1"),
            "next_best_action": (s.get("policy") or {}).get("action"),
            "tool_calls": s.get("tool_calls"),
            "tokens": s.get("tokens"),
            "trace_len": len(s.get("trace") or []),
            "errors": s.get("errors") or [],
            "latency_s": s.get("latency_s"),
        })
    return out


@app.get("/agent/runs/{case_id}", response_model=Dict[str, Any], tags=["agent"])
def agent_run(case_id: str) -> Dict[str, Any]:
    path = os.path.join(RUNS_DIR, "%s.json" % case_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="no agent run for %s" % case_id)
    return _json(path)


# --------------------------------------------------------------------------
# live graph echo — the only route that touches TigerGraph on demand
# --------------------------------------------------------------------------
@app.get("/graph/echo", response_model=Dict[str, Any], tags=["graph"])
def graph_echo(txn_id: str = "3514030") -> Dict[str, Any]:
    """Read-only live probe of the local RESTPP. No write path exists here."""
    os.environ.setdefault("TG_HOST", "http://localhost")
    os.environ.setdefault("TG_RESTPP_PORT", "9000")
    t0 = time.perf_counter()
    try:
        from mcp.tools.investigation_tools import get_tool
        env = get_tool("get_transaction")(txn_id)
    except Exception as exc:
        return {"live": False, "txn_id": txn_id,
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:200]),
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    ms = round((time.perf_counter() - t0) * 1000, 1)
    data = env.get("data") or {}
    return {"live": str(env.get("status", "")).lower() == "success",
            "txn_id": txn_id, "tool": env.get("tool"), "status": env.get("status"),
            "source_kind": (env.get("source") or {}).get("kind"),
            "results": data.get("results"),
            "returned_count": env.get("returned_count"),
            "total_count": env.get("total_count"),
            "latency_ms": ms,
            "read_only": True}


@app.get("/llm", response_model=Dict[str, Any], tags=["agent"])
def llm_status() -> Dict[str, Any]:
    """Layer capability only. The API key is never returned by any route."""
    try:
        from agent.llm import client as llm
        return llm.status()
    except Exception as exc:
        return {"available": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
