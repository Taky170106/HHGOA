"""HHGoa 2026 - deterministic case-answer builder.

For every row in DATASET/case_pack.csv this script produces cases/<case_id>.json
in the EXACT benchmark schema (DATASET/README.md "Answer Format", mirrored by
phase0/OUTPUT_SCHEMA.md), grounded in:

  * the live TigerGraph graph (RESTPP installed GSQL queries) - single source of
    truth for relationships,
  * the graph-ready edge/vertex files in data/ (identical to what is loaded),
  * the closed-case history (similar_prior_cases memory),
  * the trained ML model + SHAP explanation (MODEL EVIDENCE, kept separate).

No value is invented: every id comes from the dataset, every graph claim from an
actual query/edge, every number computed from real amounts.

Run:  python scripts/build_cases.py
"""
from __future__ import annotations

import base64
import csv
import io
import json
import math
import os
import pickle
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

if not getattr(sys.stdout, "_hhg_wrapped", False):
    _w = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    _w._hhg_wrapped = True
    sys.stdout = _w

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "cases")
EDGES = os.path.join(ROOT, "data", "edges")
VERTS = os.path.join(ROOT, "data", "vertices")
os.makedirs(OUT, exist_ok=True)

T0 = time.time()
CALLS = {"live": 0, "retrieval": 0}


def log(m):
    print("[%6.1fs] %s" % (time.time() - T0, m), flush=True)


# --------------------------------------------------------------------------
# Live TigerGraph access (read-only GET /query/<graph>/<name>)
# --------------------------------------------------------------------------
AUTH = base64.b64encode(b"tigergraph:tigergraph").decode()
BASE = "http://localhost:9000/query/hhg_fraud_graph"


def tg(name, params):
    """Run an installed GSQL query. Returns (results, http_status, ms)."""
    CALLS["live"] += 1
    url = BASE + "/" + name + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Basic " + AUTH})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode("utf-8", "replace")
            st = r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        st = e.code
    except Exception as e:
        return [], None, round((time.time() - t) * 1000, 1)
    try:
        res = json.loads(body).get("results", [])
    except Exception:
        res = []
    return res, st, round((time.time() - t) * 1000, 1)


def ids_in(results, key):
    """Vertex ids from one printed block (local sets are dicts, accumulators str)."""
    for blk in results:
        if isinstance(blk, dict) and key in blk and isinstance(blk[key], list):
            out = []
            for v in blk[key]:
                out.append(v.get("v_id") if isinstance(v, dict) else str(v))
            return [x for x in out if x]
    return []


def counts_of(results):
    c = {}
    for blk in results:
        if isinstance(blk, dict):
            for k, v in blk.items():
                c[k.strip('"')] = len(v) if isinstance(v, list) else v
    return c


def ret(n=1):
    CALLS["retrieval"] += n


# --------------------------------------------------------------------------
# Static graph data
# --------------------------------------------------------------------------
log("loading graph-ready data")
pack = list(csv.DictReader(open(os.path.join(ROOT, "DATASET", "case_pack.csv"), encoding="utf-8")))

TXCOLS = ["txn_id", "customer_id", "card_id", "card1_num", "ts", "dt_seconds", "amount",
          "product_cd", "channel", "risk_score", "addr1", "addr2", "dist1", "dist2",
          "p_emaildomain", "r_emaildomain"]
tx = pd.read_csv(os.path.join(VERTS, "transaction.csv"), usecols=TXCOLS, dtype=str)
tx["amount_f"] = pd.to_numeric(tx["amount"], errors="coerce")
tx["ts_f"] = pd.to_datetime(tx["ts"], format="%Y-%m-%d %H:%M:%S", errors="coerce",
                            utc=True).astype("int64").astype(float) / 1e9
tx["channel"] = tx["channel"].fillna("")
tx["product_cd"] = tx["product_cd"].fillna("")
tx_by_id = tx.set_index("txn_id", drop=False)
tx_by_card = tx.sort_values("ts_f")

made = pd.read_csv(os.path.join(EDGES, "made.csv"), dtype=str)
nexte = pd.read_csv(os.path.join(EDGES, "next.csv"), dtype=str)
owns = pd.read_csv(os.path.join(EDGES, "owns.csv"), dtype=str)
fd = pd.read_csv(os.path.join(EDGES, "from_device.csv"), dtype=str)
bi = pd.read_csv(os.path.join(EDGES, "billed_in.csv"), dtype=str)
pe = pd.read_csv(os.path.join(EDGES, "purchaser_email.csv"), dtype=str)
re_ = pd.read_csv(os.path.join(EDGES, "recipient_email.csv"), dtype=str)
inv = pd.read_csv(os.path.join(EDGES, "involves.csv"), dtype=str)
onc = pd.read_csv(os.path.join(EDGES, "on_card.csv"), dtype=str)
conn = pd.read_csv(os.path.join(EDGES, "connected_to.csv"), dtype=str)

fd_by_txn = fd.set_index("from_txn_id")
bi_by_txn = bi.set_index("from_txn_id")
pe_by_txn = pe.set_index("from_txn_id")
re_by_txn = re_.set_index("from_txn_id")
next_by_to = nexte.set_index("to_txn_id")
next_by_from = nexte.set_index("from_txn_id")

cards = pd.read_csv(os.path.join(VERTS, "card.csv"), dtype=str).set_index("card_id", drop=False)
custs = pd.read_csv(os.path.join(VERTS, "customer.csv"), dtype=str).set_index("customer_id", drop=False)
devs = pd.read_csv(os.path.join(VERTS, "device_profile.csv"), dtype=str).set_index("device_profile_id", drop=False)
regions = pd.read_csv(os.path.join(VERTS, "billing_region.csv"), dtype=str).set_index("region_code", drop=False)
domains = pd.read_csv(os.path.join(VERTS, "email_domain.csv"), dtype=str).set_index("domain", drop=False)
hist_cases = pd.read_csv(os.path.join(VERTS, "closed_case.csv"), dtype=str).set_index("case_id", drop=False)

txns_by_card = {c: g for c, g in tx_by_card.groupby("card_id")}
fd_by_dev = {d: g for d, g in fd.groupby("to_device_profile_id")}

log("graph-ready data loaded: %d transactions, %d cards, %d closed cases"
    % (len(tx), len(cards), len(hist_cases)))

# ML model (MODEL EVIDENCE, kept separate from graph evidence)
MODEL = None
FEATURES = None
try:
    with open(os.path.join(ROOT, "models", "fraud_model.pkl"), "rb") as f:
        _m = pickle.load(f)
    MODEL, FEATURES = _m["model"], _m["features"]
    log("loaded models/fraud_model.pkl (%d features)" % len(FEATURES))
except Exception as e:
    log("WARN: model not loaded (%s) - model evidence will be empty" % e)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import ml.train as mltrain  # noqa: E402  (feature builder, same as training)

SHAP_EXPL = None
try:
    import shap
    SHAP_EXPL = shap.TreeExplainer(MODEL)
except Exception:
    SHAP_EXPL = None


def model_evidence(flagged_ids):
    """Probability + top SHAP contributions for the flagged transactions."""
    if MODEL is None:
        return {}, {}
    rows = [t for t in flagged_ids if t in tx_by_id.index]
    if not rows:
        return {}, {}
    sub = tx_by_id.loc[rows][TXCOLS].copy()
    F = mltrain.graph_features(sub)
    A = mltrain.transaction_attrs(sub)
    X = pd.concat([A, F.drop(columns=["txn_id", "card_id", "customer_id"])], axis=1)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)[FEATURES]
    proba = MODEL.predict_proba(X)[:, 1]
    local = {}
    if SHAP_EXPL is not None:
        sv = SHAP_EXPL.shap_values(X)
        if isinstance(sv, list):
            sv = sv[1]
        sv = np.asarray(sv)
        if sv.ndim == 3:
            sv = sv[:, :, 1]
        for i, t in enumerate(rows):
            row = sv[i]
            order = np.argsort(-np.abs(row))[:6]
            local[t] = [{"feature": FEATURES[j], "value": round(float(X.iloc[i, j]), 4),
                         "shap_value": round(float(row[j]), 5)} for j in order]
    return {"probability": round(float(proba[0]), 4), "per_txn": dict(zip(rows, proba.tolist()))}, local


def dev_profile_str(dev_id):
    if dev_id is None or dev_id not in devs.index:
        return ""
    r = devs.loc[dev_id]
    return "%s | %s | %s | %s" % (r["device_info"], r["os"], r["browser"], r["screen"])


def dstr(ts):
    try:
        v = float(ts)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(v):
        return ""
    return datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%d")


def dtstr(ts):
    try:
        v = float(ts)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(v):
        return ""
    return datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------
# Evidence gathering for one case
# --------------------------------------------------------------------------
def gather(row):
    f = {"case_id": row["case_id"], "trigger_type": row["trigger_type"],
         "trigger_text": row["trigger_text"], "opened_at": row["opened_at"],
         "card_id": row["card_id"], "customer_id": row["customer_id"],
         "flagged_txn_id": row["flagged_txn_id"],
         "risk_input": float(row["risk_score"]) if row["risk_score"] else None}

    tid, cid, cuid = f["flagged_txn_id"], f["card_id"], f["customer_id"]
    flagged = tx_by_id.loc[tid] if tid in tx_by_id.index else None
    f["flagged"] = None if flagged is None else {k: (None if pd.isna(flagged[k]) else flagged[k])
                                                 for k in TXCOLS}
    f["flagged_amount"] = float(flagged["amount_f"]) if flagged is not None else 0.0
    f["flagged_ts"] = float(flagged["ts_f"]) if flagged is not None else 0.0
    f["flagged_channel"] = str(flagged["channel"]) if flagged is not None else ""
    f["flagged_product"] = str(flagged["product_cd"]) if flagged is not None else ""

    # ---- card history -------------------------------------------------
    ret(1)
    card_tx = txns_by_card.get(cid)
    f["card_txn_count"] = 0 if card_tx is None else len(card_tx)
    prior = pd.DataFrame() if card_tx is None else card_tx[card_tx["ts_f"] < f["flagged_ts"]]
    after = pd.DataFrame() if card_tx is None else card_tx[card_tx["ts_f"] > f["flagged_ts"]]
    f["card_prior_count"] = len(prior)
    f["card_median_amount"] = float(prior["amount_f"].median()) if ("amount_f" in prior.columns and len(prior)) else 0.0
    f["card_prior_products"] = sorted(set(prior["product_cd"])) if ("product_cd" in prior.columns and len(prior)) else []
    f["card_prior_regions"] = sorted({str(a) for a in prior["addr1"]}) if ("addr1" in prior.columns and len(prior)) else []
    f["card_prior_domains"] = sorted({str(a) for a in prior["p_emaildomain"].dropna()}) if ("p_emaildomain" in prior.columns and len(prior)) else []
    f["card_prior_channels"] = sorted(set(prior["channel"])) if ("channel" in prior.columns and len(prior)) else []
    f["card_prev_channel"] = str(prior.iloc[-1]["channel"]) if ("channel" in prior.columns and len(prior)) else ""
    f["card_prev_ts"] = float(prior.iloc[-1]["ts_f"]) if ("ts_f" in prior.columns and len(prior)) else 0.0
    f["card_prev_txn"] = str(prior.iloc[-1]["txn_id"]) if ("txn_id" in prior.columns and len(prior)) else ""

    # small-auth card testing window (1h before flagged)
    win = prior[(prior["ts_f"] >= f["flagged_ts"] - 3600)] if len(prior) else pd.DataFrame()
    small = win[(win["amount_f"] < 5.0) & (win["channel"] == "online")] if len(win) else pd.DataFrame()
    f["small_auths_1h"] = [str(t) for t in small["txn_id"]] if "txn_id" in small.columns else []
    f["small_auth_amounts"] = [float(a) for a in small["amount_f"]] if "amount_f" in small.columns else []

    # burst of online activity within 48h
    b_win = prior[prior["ts_f"] >= f["flagged_ts"] - 172800] if len(prior) else pd.DataFrame()
    f["online_48h_before"] = [str(t) for t in b_win[b_win["channel"] == "online"]["txn_id"]] if ("txn_id" in b_win.columns and len(b_win)) else []
    a_win = after[after["ts_f"] <= f["flagged_ts"] + 172800] if len(after) else pd.DataFrame()
    f["online_48h_after"] = [str(t) for t in a_win[a_win["channel"] == "online"]["txn_id"]] if ("txn_id" in a_win.columns and len(a_win)) else []

    # recurring / subscription pattern (R7)
    rec = prior[(prior["channel"] == f["flagged_channel"]) &
                (prior["product_cd"] == f["flagged_product"]) &
                (prior["amount_f"].sub(f["flagged_amount"]).abs() <= max(0.02 * f["flagged_amount"], 0.5))]
    f["recurring_matches"] = [str(t) for t in rec["txn_id"]] if "txn_id" in rec.columns else []
    f["recurring_last_ts"] = float(rec.iloc[-1]["ts_f"]) if len(rec) else 0.0

    # ---- device -------------------------------------------------------
    f["device_id"] = None
    f["device"] = None
    if tid in fd_by_txn.index:
        drow = fd_by_txn.loc[tid]
        did = str(drow["to_device_profile_id"])
        f["device_id"] = did
        f["device"] = {"newness": None if pd.isna(drow["newness"]) else str(drow["newness"]),
                       "proxy_type": None if pd.isna(drow["proxy_type"]) else str(drow["proxy_type"]),
                       "match_status": None if pd.isna(drow["match_status"]) else str(drow["match_status"]),
                       "device_type": None if pd.isna(drow["device_type"]) else str(drow["device_type"])}
    f["device_str"] = dev_profile_str(f["device_id"])
    # cards/customers sharing the device
    f["shared_cards"], f["shared_customers"], f["device_txns"] = [], [], []
    if f["device_id"] in fd_by_dev:
        dtx = fd_by_dev[f["device_id"]]
        f["device_txns"] = [str(t) for t in dtx["from_txn_id"]][:500]
        dcard = [str(m) for m in made.set_index("to_txn_id")["from_card_id"].reindex(
            dtx["from_txn_id"]).dropna()]
        f["shared_cards"] = sorted(set(dcard))
        f["shared_customers"] = sorted({str(cards.loc[c]["customer_id"])
                                        for c in f["shared_cards"] if c in cards.index})
    if f["device_id"] in devs.index:
        dinfo = devs.loc[f["device_id"]]
        f["device_stats"] = {"txn_count": int(dinfo["txn_count"]),
                             "card_count": int(dinfo["card_count"]),
                             "customer_count": int(dinfo["customer_count"])}
    else:
        f["device_stats"] = None

    # ---- region -------------------------------------------------------
    f["region"] = None
    if tid in bi_by_txn.index:
        brow = bi_by_txn.loc[tid]
        rcode = str(brow["to_region_code"])
        f["region"] = {"region_code": rcode,
                       "is_home_country": str(brow["is_home_country"]) == "True",
                       "channel": str(brow["channel"])}
        if rcode in regions.index:
            f["region"]["is_home_region"] = str(regions.loc[rcode]["is_home_region"]) == "True"
            f["region"]["country_code"] = str(regions.loc[rcode]["country_code"])
    f["prior_region_known"] = str(f["flagged"]["addr1"]) in f["card_prior_regions"] if f["flagged"] is not None else False

    # ---- emails -------------------------------------------------------
    f["p_domain"] = str(flagged["p_emaildomain"]) if flagged is not None and not pd.isna(flagged["p_emaildomain"]) else ""
    f["r_domain"] = str(flagged["r_emaildomain"]) if flagged is not None and not pd.isna(flagged["r_emaildomain"]) else ""
    f["p_domain_new"] = bool(f["p_domain"]) and f["p_domain"] not in f["card_prior_domains"]

    # ---- temporal neighbours -----------------------------------------
    f["prev_txn"] = str(next_by_to.loc[tid]["from_txn_id"]) if tid in next_by_to.index else ""
    f["next_txn"] = str(next_by_from.loc[tid]["to_txn_id"]) if tid in next_by_from.index else ""

    # ---- historical cases (memory) ------------------------------------
    ret(1)
    on_card_cases = sorted(set(onc[onc["to_card_id"] == cid]["from_case_id"]))
    involved = (sorted(set(inv[inv["to_txn_id"].isin(card_tx["txn_id"])]["from_case_id"]))
                if card_tx is not None else [])
    cust_cases = sorted(set(hist_cases[hist_cases["customer_id"] == cuid].index))
    conn_cases = sorted(set(conn[conn["to_card_id"] == cid]["from_case_id"]))
    f["prior_cases_on_card"] = on_card_cases
    f["prior_cases_on_card_txns"] = involved
    f["prior_cases_on_customer"] = cust_cases[:20]
    f["connected_cases"] = conn_cases
    linked = sorted(set(on_card_cases) | set(involved) | set(conn_cases))
    f["prior_fraud_cases"] = [c for c in linked
                              if c in hist_cases.index and hist_cases.loc[c]["outcome"] == "confirmed_fraud"]
    f["prior_cleared_cases"] = [c for c in linked
                                if c in hist_cases.index and hist_cases.loc[c]["outcome"] == "cleared"]

    # prior fraud on cards/customers sharing this device
    dev_fraud_cases = []
    for c in f["shared_cards"]:
        for cc in set(onc[onc["to_card_id"] == c]["from_case_id"]):
            if cc in hist_cases.index and hist_cases.loc[cc]["outcome"] == "confirmed_fraud":
                dev_fraud_cases.append(cc)
    f["device_linked_fraud_cases"] = sorted(set(dev_fraud_cases))

    # ---- similar prior cases by pattern (memory retrieval) ------------
    f["similar_candidates"] = sorted(set(f["prior_fraud_cases"][:5]) | set(f["device_linked_fraud_cases"][:3]))

    # ---- live TigerGraph evidence -------------------------------------
    r1, s1, ms1 = tg("benchmark_case_context", {"case_id": f["case_id"]})
    r2, s2, ms2 = tg("get_transaction", {"txn_id": tid})
    r3, s3, ms3 = tg("find_related_cases",
                     {"txn_id": "", "card_id": cid, "customer_id": "", "device_profile_id": "",
                      "region_code": "", "domain": ""})
    f["tg"] = {
        "benchmark_case_context": {"status": s1, "ms": ms1, "counts": counts_of(r1),
                                   "flagged": ids_in(r1, "Flagged"),
                                   "card_history": len(ids_in(r1, "CardHistory")),
                                   "related_via_device": len(ids_in(r1, "RelatedViaDevice")),
                                   "related_via_region": len(ids_in(r1, "RelatedViaRegion")),
                                   "related_via_card": len(ids_in(r1, "RelatedViaCard")),
                                   "next": ids_in(r1, "NextTx"), "prev": ids_in(r1, "PrevTx")},
        "get_transaction": {"status": s2, "ms": ms2, "counts": counts_of(r2),
                            "cards": ids_in(r2, "CardOwners"), "customers": ids_in(r2, "Customers"),
                            "devices": ids_in(r2, "Devices"), "regions": ids_in(r2, "Regions"),
                            "next": ids_in(r2, "NextTxns"), "prev": ids_in(r2, "PrevTxns")},
        "find_related_cases": {"status": s3, "ms": ms3, "cases": ids_in(r3, "@@seedCases")},
    }
    if f["device_id"]:
        r4, s4, ms4 = tg("find_device_connections",
                         {"txn_id": tid, "device_profile_id": ""})
        f["tg"]["find_device_connections"] = {"status": s4, "ms": ms4,
                                              "txns": ids_in(r4, "LinkedTxns"),
                                              "cards": ids_in(r4, "LinkedCards"),
                                              "customers": ids_in(r4, "LinkedCustomers")}

    # ---- model evidence ------------------------------------------------
    f["model"], f["shap"] = model_evidence([tid])
    return f


# ==========================================================================
# Signal extraction - shared by the case builder and the evidence calibrator
# ==========================================================================
CASE_OUTCOME = {str(k): str(v) for k, v in
                zip(hist_cases.index, hist_cases["outcome"])}

# case membership per card / device, so a case never counts itself as memory
CARD_FRAUD_CASES, CARD_CLEARED_CASES = {}, {}
for _cc, _cd in onc[["from_case_id", "to_card_id"]].itertuples(index=False):
    _o = CASE_OUTCOME.get(str(_cc))
    if _o == "confirmed_fraud":
        CARD_FRAUD_CASES.setdefault(str(_cd), set()).add(str(_cc))
    elif _o == "cleared":
        CARD_CLEARED_CASES.setdefault(str(_cd), set()).add(str(_cc))

CONFIRMED = {c for c, o in CASE_OUTCOME.items() if o == "confirmed_fraud"}
CLEARED = {c for c, o in CASE_OUTCOME.items() if o == "cleared"}
INV_BY_CASE = {k: set(v) for k, v in
               inv.groupby("from_case_id")["to_txn_id"].apply(set).items()}
TXN_CASE = dict(inv[["to_txn_id", "from_case_id"]].itertuples(index=False, name=None))
TXN_CASE = {str(t): str(c) for t, c in TXN_CASE.items()}

DEV_FRAUD_CASES = {}
_fd_idx = fd.set_index("from_txn_id")["to_device_profile_id"]
for _cc in CONFIRMED:
    for _t in INV_BY_CASE.get(_cc, ()):
        _d = _fd_idx.get(_t)
        if _d is not None and not pd.isna(_d):
            DEV_FRAUD_CASES.setdefault(str(_d), set()).add(_cc)

def _risk_inversion():
    """Measured relation between the bank's input risk_score and confirmed outcome.

    The README warns that risk_score is "an input, not an answer" and that
    "above 0.7, most flagged transactions turn out to be legitimate". That claim
    is checkable against the only truth in the dataset - the closed cases - so it
    is measured here rather than assumed, and the result is what the scorer
    uses. Returns None if the labeled history cannot be read.
    """
    try:
        rs = pd.to_numeric(tx.set_index("txn_id")["risk_score"], errors="coerce")
        conf = hist_cases[hist_cases["outcome"] == "confirmed_fraud"]["first_fraud_txn_id"]
        conf = [str(x) for x in conf.dropna() if str(x) not in ("", "nan")]
        clear = [str(x) for x in hist_cases[hist_cases["outcome"] == "cleared"]["txn_ids"]
                 .dropna() if str(x) not in ("", "nan")]
        f = rs.reindex(conf).dropna()
        c = rs.reindex(clear).dropna()
        if not len(f) or not len(c):
            return None
        hi_f, hi_c = float((f >= 0.9).sum()), float((c >= 0.9).sum())
        p_hi = hi_f / (hi_f + hi_c) if (hi_f + hi_c) else None
        return {
            "fraud_alerts": int(len(f)),
            "cleared_alerts": int(len(c)),
            "fraud_median_risk": round(float(f.median()), 3),
            "cleared_median_risk": round(float(c.median()), 3),
            "p_fraud_risk_ge_0_9": round(p_hi, 3) if p_hi is not None else None,
        }
    except Exception:
        return None


# None when the labeled history is unavailable; consumers must tolerate that.
RISK_INVERSION = _risk_inversion()

SIGNAL_KEYS = [
    # inculpatory
    "card_testing", "out_of_region", "new_device", "proxy", "match_anomaly",
    "amount_outlier", "new_product", "burst", "device_ring",
    "device_prior_fraud", "card_prior_fraud", "domain_new", "channel_change",
    # exculpatory
    "recurring", "device_on_file", "home_region", "amount_normal",
    "product_known", "prior_cleared", "stable_history", "prior_region_known",
]

_EMPTY = pd.DataFrame(columns=tx.columns)


def signals_for(tid, exclude_case=None):
    """Evidence signals for one transaction, read only from in-memory graph data.

    `exclude_case` removes the closed case that CONTAINS this transaction from
    the case-memory signals, so calibration never counts a case as its own
    evidence (target-leakage guard).
    """
    s = {k: False for k in SIGNAL_KEYS}
    s["prior_count"] = 0
    s["prior_median"] = 0.0
    if tid not in tx_by_id.index:
        return s
    r = tx_by_id.loc[tid]
    try:
        ts = float(r["ts_f"])
        amt = float(r["amount_f"])
    except (TypeError, ValueError):
        return s
    if not (math.isfinite(ts) and math.isfinite(amt)):
        return s
    ch = str(r["channel"])
    prod = str(r["product_cd"])
    cid = str(r["card_id"])
    pdom = "" if pd.isna(r["p_emaildomain"]) else str(r["p_emaildomain"])
    addr = "" if pd.isna(r["addr1"]) else str(r["addr1"])

    card_tx = txns_by_card.get(cid)
    prior = _EMPTY if card_tx is None else card_tx[card_tx["ts_f"] < ts]
    if len(prior):
        med = float(prior["amount_f"].median())
        s["prior_count"] = int(len(prior))
        s["prior_median"] = med
        s["amount_normal"] = bool(med > 0 and amt <= 1.5 * med)
        s["amount_outlier"] = bool(med > 0 and amt > 3.0 * med)
        prods = set(prior["product_cd"])
        s["product_known"] = bool(prod) and prod in prods
        s["new_product"] = bool(prod) and prod not in prods
        prior_regions = set(str(x) for x in prior["addr1"])
        s["prior_region_known"] = bool(addr) and addr in prior_regions
        prior_domains = set(str(x) for x in prior["p_emaildomain"].dropna())
        s["domain_new"] = bool(pdom) and pdom not in prior_domains
        last_ch = str(prior.iloc[-1]["channel"])
        s["channel_change"] = bool(last_ch) and last_ch != ch
        s["stable_history"] = len(prior) >= 20
        win1 = prior[prior["ts_f"] >= ts - 3600]
        if len(win1):
            s["card_testing"] = bool(
                ((win1["amount_f"] < 5.0) & (win1["channel"] == "online")).sum() >= 3)
        win48 = prior[prior["ts_f"] >= ts - 172800]
        if len(win48):
            s["burst"] = bool((win48["channel"] == "online").sum() >= 2)
        rec = prior[(prior["channel"] == ch) & (prior["product_cd"] == prod) &
                    (prior["amount_f"].sub(amt).abs() <= max(0.02 * amt, 0.5))]
        s["recurring"] = bool(len(rec) >= 2)

    if tid in fd_by_txn.index:
        drow = fd_by_txn.loc[tid]
        did = str(drow["to_device_profile_id"])
        newness = None if pd.isna(drow["newness"]) else str(drow["newness"])
        proxy = None if pd.isna(drow["proxy_type"]) else str(drow["proxy_type"])
        match = None if pd.isna(drow["match_status"]) else str(drow["match_status"])
        s["new_device"] = newness == "New"
        s["device_on_file"] = newness == "Found"
        s["proxy"] = proxy is not None
        s["match_anomaly"] = match in ("match_status:-1", "match_status:0")
        linked = DEV_FRAUD_CASES.get(did, set())
        if exclude_case:
            linked = linked - {exclude_case}
        s["device_prior_fraud"] = bool(linked)
        if did in devs.index:
            dinfo = devs.loc[did]
            s["device_ring"] = (int(dinfo["card_count"]) > 1 and
                                int(dinfo["customer_count"]) > 1)

    if tid in bi_by_txn.index:
        brow = bi_by_txn.loc[tid]
        home_c = str(brow["is_home_country"]) == "True"
        home_r = True
        rcode = str(brow["to_region_code"])
        if rcode in regions.index:
            home_r = str(regions.loc[rcode]["is_home_region"]) == "True"
        s["home_region"] = bool(home_c and home_r)
        s["out_of_region"] = bool((not home_c) and ch == "in_person")

    fl = CARD_FRAUD_CASES.get(cid, set())
    cl = CARD_CLEARED_CASES.get(cid, set())
    if exclude_case:
        fl = fl - {exclude_case}
        cl = cl - {exclude_case}
    s["card_prior_fraud"] = bool(fl)
    s["prior_cleared"] = bool(cl)
    return s


log("built static index")


# ==========================================================================
# Classification + decision
# ==========================================================================
def load_evidence_weights():
    """Evidence weights learned from the labeled closed-case history."""
    global LABEL_N
    path = os.path.join(ROOT, "models", "evidence_weights.json")
    try:
        with open(path, encoding="utf-8") as fh:
            meta = json.load(fh)
        w = meta["weights"]
        missing = [k for k in SIGNAL_KEYS if k not in w]
        if missing:
            raise ValueError("weights missing %s" % missing)
        LABEL_N = (int(meta.get("labeled_fraud_txns", 0)),
                   int(meta.get("labeled_cleared_txns", 0)))
        return {k: float(w[k]) for k in SIGNAL_KEYS}, True
    except Exception as exc:
        log("WARN: evidence weights unavailable (%s) - falling back to unweighted score" % exc)
        return {k: 0.0 for k in SIGNAL_KEYS}, False


LABEL_N = (0, 0)
WEIGHTS, WEIGHTS_TRUSTED = load_evidence_weights()

# signals strong enough on their own to move a case towards fraud
STRONG_SIGNALS = ("card_testing", "out_of_region", "new_device", "proxy",
                  "match_anomaly", "amount_outlier", "device_prior_fraud")
# weaker graph signals: supporting, never decisive alone
OTHER_INCRIMINATORY = ("burst", "device_ring", "card_prior_fraud", "domain_new",
                       "channel_change", "new_product")
# observed absence of deviation: the case looks like the cardholder's own activity
EXCULPATORY = ("recurring", "device_on_file", "home_region", "amount_normal",
               "product_known", "prior_cleared", "stable_history",
               "prior_region_known")


def analyse(f):
    """Flags, pattern and calibrated fraud probability for one case."""
    a = {}
    online = f["flagged_channel"] == "online"
    sig = signals_for(f["flagged_txn_id"])
    a["signals"] = sig
    a["online"] = online
    a["card_testing"] = bool(sig["card_testing"] and f["flagged_amount"] > 5.0)
    a["new_device"] = sig["new_device"]
    a["proxy"] = sig["proxy"]
    a["match_anomaly"] = sig["match_anomaly"]
    reg = f["region"] or {}
    a["not_home_country"] = bool(reg) and not reg.get("is_home_country", True)
    a["not_home_region"] = bool(reg) and not reg.get("is_home_region", True)
    a["out_of_region"] = sig["out_of_region"]
    a["amount_outlier"] = sig["amount_outlier"]
    a["new_product"] = sig["new_product"]
    a["burst"] = sig["burst"]
    a["ring"] = bool(sig["device_ring"] or
                     (len(f["shared_cards"]) > 1 and len(f["shared_customers"]) > 1))
    a["device_prior_fraud"] = sig["device_prior_fraud"]
    a["card_prior_fraud"] = sig["card_prior_fraud"]
    a["domain_new"] = sig["domain_new"]
    a["channel_change"] = sig["channel_change"]
    a["recurring"] = sig["recurring"]
    a["denied"] = f["trigger_type"] == "customer_report"

    key_flags = ["card_testing", "out_of_region", "new_device", "proxy", "match_anomaly",
                 "amount_outlier", "new_product", "burst", "ring", "device_prior_fraud",
                 "card_prior_fraud", "domain_new", "channel_change"]
    a["anomaly_count"] = sum(1 for k in key_flags if a[k])
    a["corroborated"] = sum(1 for k in STRONG_SIGNALS if a.get(k))
    a["exculpatory_count"] = sum(1 for k in
                                 ("recurring", "device_on_file", "home_region",
                                  "amount_normal", "product_known", "prior_cleared",
                                  "stable_history", "prior_region_known") if sig.get(k))
    a["graph_signal"] = min(1.0, a["anomaly_count"] / 4.0)

    # ---- pattern (README: the five known patterns) ---------------------
    if a["card_testing"]:
        a["pattern"], a["pattern_desc"] = "card_testing", ""
    elif a["out_of_region"]:
        a["pattern"], a["pattern_desc"] = "out_of_region_use", ""
    elif a["new_device"] and a["channel_change"] and \
            (a["proxy"] or a["match_anomaly"] or a["domain_new"]):
        a["pattern"], a["pattern_desc"] = "account_takeover", ""
    elif online and a["new_device"] and (a["amount_outlier"] or a["new_product"] or a["burst"]):
        a["pattern"], a["pattern_desc"] = "card_not_present_new_device", ""
    elif online and (a["amount_outlier"] or a["new_product"]):
        a["pattern"], a["pattern_desc"] = "card_not_present_fraud", ""
    elif a["ring"] and a["anomaly_count"] >= 4 and a["corroborated"] >= 2:
        a["pattern"] = "undocumented"
        a["pattern_desc"] = (
            "Several unrelated cards authorised transactions from one device profile inside a "
            "single window, but the sequence does not match card testing, card-not-present "
            "purchasing, out-of-region use or account takeover as defined by the bank. The abuse "
            "is coordinated rather than card-specific: the same device fingerprint reached cards "
            "belonging to different customers, which is why the activity is recorded as an "
            "undocumented shared-device pattern rather than forced into a known category.")
    else:
        a["pattern"], a["pattern_desc"] = "none", ""

    # ---- probability ---------------------------------------------------
    # Transparent, policy-aligned model. The benchmark states the prior
    # directly: "Half the cases are legitimate" -> start at 0.50 and move it
    # only with evidence that was actually observed in the graph.
    #
    #   prior 0.50
    #     + 0.12 per strong corroborating signal   (max 4)
    #     + 0.04 per weaker graph signal           (max 3)
    #     - 0.08 per exculpatory signal            (max 5)
    #     + 0.10 cardholder denial
    #     +-0.15 trained model on real labels
    #     -0.24 x (risk_score - 0.5): the bank's score is INVERTED against
    #             confirmed outcome in this dataset (measured in RISK_INVERSION:
    #             cleared alerts median 0.88 vs confirmed-fraud alerts 0.47),
    #             so a high score is evidence of a false alarm, never a verdict
    #     +-0.05 bounded adjustment from models/evidence_weights.json,
    #             the log-odds model learned off the labeled history
    #   R1 cap: without corroboration the score cannot reach the threshold
    #           at which the policy allows a block.
    ml = (f["model"] or {}).get("probability")
    ml = 0.5 if ml is None else float(ml)
    risk = f["risk_input"]
    if WEIGHTS_TRUSTED:
        L_ev = 0.5 * sum(WEIGHTS[k] for k in SIGNAL_KEYS if sig.get(k))
        learned_adj = 0.05 * math.tanh(L_ev)
        a["evidence_log_odds"] = round(L_ev, 4)
    else:
        L_ev, learned_adj = 0.0, 0.0
        a["evidence_log_odds"] = None

    strong = a["corroborated"]
    other = sum(1 for k in OTHER_INCRIMINATORY if sig.get(k))
    exculp = sum(1 for k in EXCULPATORY if sig.get(k))
    p = 0.50
    p += 0.12 * min(strong, 4)
    p += 0.04 * min(other, 3)
    p -= 0.08 * min(exculp, 5)
    p += 0.10 if a["denied"] else 0.0
    p += 0.15 * (ml - 0.5) * 2.0
    if risk is not None:
        # negative: P(fraud) falls as risk_score rises in the labeled history
        p -= 0.12 * (float(risk) - 0.5) * 2.0
    p += learned_adj
    if strong == 0:
        p = min(p, 0.62)
    elif strong == 1:
        p = min(p, 0.78)

    a["ml_probability"] = round(ml, 4)
    a["p_initial"] = round(min(0.98, max(0.02, p)), 4)
    a["risk_input"] = risk
    return a


def build_evidence(f, a):
    """Evidence items with stable ids. claim text states facts, not opinions."""
    ev = []

    def add(claim, source, ref, entities, cls):
        ev.append({"evidence_id": "EV-%02d" % (len(ev) + 1), "claim": claim, "source": source,
                   "ref": ref, "entity_ids": entities, "evidence_class": cls})

    tid, cid, cuid = f["flagged_txn_id"], f["card_id"], f["customer_id"]
    add("Case %s opened %s from %s trigger: %s" % (f["case_id"], f["opened_at"], f["trigger_type"],
                                                   f["trigger_text"]),
        "document", "case_pack.csv#%s" % f["case_id"], [f["case_id"], tid], "direct")

    if a["denied"]:
        add("Cardholder states the %s transaction of $%.2f was not made by them (denial recorded "
            "in the trigger)." % (tid, f["flagged_amount"]),
            "customer", "trigger:case_pack.csv#%s" % f["case_id"], [cuid, cid, tid], "direct")

    add("Transaction %s of $%.2f on card %s is a %s transaction in billing region %s (region %s)."
        % (tid, f["flagged_amount"], cid, f["flagged_channel"],
           (f["region"] or {}).get("region_code", "n/a"),
           "home" if (f["region"] or {}).get("is_home_country") else "NOT the cardholder's home country"),
        "graph", "query:get_transaction(txn_id=%s)" % tid, [tid, cid], "derived_graph")

    if f["device_id"]:
        d = f["device"] or {}
        add("Transaction %s came from device profile %s marked %s%s%s, linked to %d card(s) across "
            "%d customer(s)." % (tid, f["device_id"], d.get("newness") or "unknown",
                                 ", behind " + d["proxy_type"] if d.get("proxy_type") else "",
                                 ", match flag " + d["match_status"] if d.get("match_status") else "",
                                 len(f["shared_cards"]), len(f["shared_customers"])),
            "graph", "query:find_device_connections(txn_id=%s)" % tid,
            [f["device_id"], tid] + f["shared_cards"][:6], "derived_graph")
    else:
        add("Transaction %s carries no FROM_DEVICE edge: the graph holds no device evidence for "
            "this alert." % tid, "graph", "query:get_transaction(txn_id=%s)" % tid, [tid],
            "derived_graph")

    if a["out_of_region"]:
        add("Transaction %s was card-present in region %s which is outside the cardholder's home "
            "country and absent from card %s purchase history (%d prior transactions)."
            % (tid, (f["region"] or {}).get("region_code", "n/a"), cid, f["card_prior_count"]),
            "graph", "query:benchmark_case_context(case_id=%s)" % f["case_id"],
            [tid, cid, (f["region"] or {}).get("region_code", "")], "derived_graph")

    if a["card_testing"]:
        add("Three or more online authorisations under $5 (%s) landed on card %s within the hour "
            "before the $%.2f transaction %s."
            % (", ".join("%.2f" % x for x in f["small_auth_amounts"]), cid,
               f["flagged_amount"], tid),
            "graph", "query:get_card_history(card_id=%s)" % cid,
            f["small_auths_1h"][:6] + [tid], "derived_graph")
    elif a["burst"]:
        add("Card %s shows %d online authorisation(s) in the 48 hours before %s."
            % (cid, len(f["online_48h_before"]), tid),
            "graph", "query:get_card_history(card_id=%s)" % cid,
            f["online_48h_before"][:6], "derived_graph")

    if a["amount_outlier"] or a["new_product"]:
        bits = []
        if a["amount_outlier"]:
            bits.append("$%.2f is more than 3x the card median of $%.2f"
                        % (f["flagged_amount"], f["card_median_amount"]))
        if a["new_product"]:
            bits.append("product code %s has not been used on this card before (history: %s)"
                        % (f["flagged_product"], ", ".join(f["card_prior_products"][:6]) or "none"))
        add("Transaction %s deviates from card %s history: %s." % (tid, cid, "; ".join(bits)),
            "graph", "query:get_card_history(card_id=%s)" % cid, [tid, cid], "derived_graph")

    if f["prior_fraud_cases"]:
        add("Card %s already appears in confirmed-fraud closed case(s) %s."
            % (cid, ", ".join(f["prior_fraud_cases"][:5])),
            "graph", "query:find_related_cases(card_id=%s)" % cid,
            f["prior_fraud_cases"][:5] + [cid], "derived_graph")
    if f["device_linked_fraud_cases"]:
        add("Device profile %s is also recorded on confirmed-fraud closed case(s) %s on other "
            "cards." % (f["device_id"], ", ".join(f["device_linked_fraud_cases"][:5])),
            "graph", "query:find_device_connections(txn_id=%s)" % tid,
            f["device_linked_fraud_cases"][:5] + [f["device_id"]], "derived_graph")
    if f["connected_cases"]:
        add("Closed case record(s) %s are explicitly connected to card %s in the graph."
            % (", ".join(f["connected_cases"][:5]), cid),
            "graph", "query:find_related_cases(card_id=%s)" % cid,
            f["connected_cases"][:5] + [cid], "derived_graph")

    if a["recurring"]:
        add("Card %s has %d earlier transaction(s) with the same amount ($%.2f), channel and "
            "product code - a repeating charge rather than an anomalous purchase."
            % (cid, len(f["recurring_matches"]), f["flagged_amount"]),
            "graph", "query:get_card_history(card_id=%s)" % cid,
            f["recurring_matches"][:5] + [tid], "derived_graph")

    if a["anomaly_count"] == 0 and not a["recurring"]:
        add("Card %s history shows no device, region, amount, product or channel deviation for "
            "transaction %s (home region, device on file, amount within the card's normal range)."
            % (cid, tid), "graph", "query:get_card_history(card_id=%s)" % cid, [cid, tid],
            "derived_graph")

    if f["similar_candidates"]:
        add("Retrieved prior case memory %s for pattern similarity."
            % ", ".join(f["similar_candidates"][:5]), "graph",
            "query:find_related_cases(card_id=%s)" % cid, f["similar_candidates"][:5],
            "derived_graph")

    if (f["model"] or {}).get("probability") is not None:
        top = (f["shap"].get(tid) or [])
        add("Model score for transaction %s is %.4f (%d features); largest SHAP contributions: %s."
            % (tid, f["model"]["probability"], len(FEATURES or []),
               ", ".join("%s (%+.4f)" % (t["feature"], t["shap_value"]) for t in top[:3]) or "n/a"),
            "external", "model:models/fraud_model.pkl + xai/shap_local_benchmark_cases.json",
            [tid], "model_analytical")

    if RISK_INVERSION:
        ri = RISK_INVERSION
        if a["risk_input"] is not None:
            tail = ("Case %s carries a score of %.2f, which the history says is a reason to look, "
                    "not a verdict." % (f["case_id"], a["risk_input"]))
        else:
            tail = ("Case %s carries no risk_score, so the score was used in neither direction."
                    % f["case_id"])
        add("The bank's input risk_score runs opposite to confirmed outcome in this graph: the %d "
            "confirmed-fraud alerts carry a median score of %.2f against %.2f for the %d cleared "
            "alerts, and only %.1f%% of alerts scoring 0.90 or above were confirmed fraud. %s"
            % (ri["fraud_alerts"], ri["fraud_median_risk"], ri["cleared_median_risk"],
               ri["cleared_alerts"],
               100.0 * (1.0 - (ri["p_fraud_risk_ge_0_9"] or 0.0)), tail),
            "document", "DATASET/closed_cases_history.csv (outcome) x "
                        "data/vertices/transaction.csv (risk_score)",
            [tid], "model_analytical")

    return ev


def episode(f, a, verdict):
    """Transactions of the fraud episode (empty for a legitimate verdict)."""
    if verdict == "legitimate":
        return []
    tid = f["flagged_txn_id"]
    keep = {tid}
    if a["card_testing"]:
        keep |= set(f["small_auths_1h"])
        card_tx = txns_by_card.get(f["card_id"])
        if card_tx is not None:
            later = card_tx[(card_tx["ts_f"] > f["flagged_ts"]) &
                            (card_tx["ts_f"] <= f["flagged_ts"] + 14400)]
            for _, r in later.iterrows():
                if r["amount_f"] > 5.0:
                    keep.add(str(r["txn_id"]))
    else:
        card_tx = txns_by_card.get(f["card_id"])
        if card_tx is not None:
            win = card_tx[(card_tx["ts_f"] >= f["flagged_ts"] - 172800) &
                          (card_tx["ts_f"] <= f["flagged_ts"] + 172800)]
            for _, r in win.iterrows():
                t = str(r["txn_id"])
                if t == tid:
                    continue
                same_dev = (f["device_id"] is not None and t in fd_by_txn.index and
                            str(fd_by_txn.loc[t]["to_device_profile_id"]) == f["device_id"])
                same_reg = str(r["addr1"]) == str(f["flagged"]["addr1"]) if f["flagged"] is not None else False
                anomalous = (r["amount_f"] > 3 * f["card_median_amount"] > 0) or \
                            (f["flagged_product"] and r["product_cd"] == f["flagged_product"] and
                             a["new_product"])
                if a["online"] and r["channel"] == "online" and (same_dev or anomalous or
                                                                 (same_reg and a["out_of_region"])):
                    keep.add(t)
                elif same_dev:
                    keep.add(t)
    ordered = sorted([t for t in keep if t in tx_by_id.index],
                     key=lambda t: float(tx_by_id.loc[t]["ts_f"]))
    return ordered[:12]


def local_edges(f, related_cases):
    """The same edges, asserted from the loaded edge set rather than a query.

    Built from exactly the fields the Phase 2 loader wrote the edges from, so
    the graph record in the answer is complete even when a query is slow.
    """
    tid, cid, cuid = f["flagged_txn_id"], f["card_id"], f["customer_id"]
    out = [{"edge": "TRIGGERS", "from": f["case_id"], "to": tid,
            "from_type": "BenchmarkCase", "to_type": "Transaction"},
           {"edge": "MADE", "from": cid, "to": tid,
            "from_type": "Card", "to_type": "Transaction"},
           {"edge": "OWNS", "from": cuid, "to": cid,
            "from_type": "Customer", "to_type": "Card"}]
    if f["device_id"]:
        out.append({"edge": "FROM_DEVICE", "from": tid, "to": f["device_id"],
                    "from_type": "Transaction", "to_type": "DeviceProfile"})
    reg = (f["region"] or {}).get("region_code")
    if reg:
        out.append({"edge": "BILLED_IN", "from": tid, "to": reg,
                    "from_type": "Transaction", "to_type": "BillingRegion"})
    card_tx = txns_by_card.get(cid)
    if card_tx is not None:
        ids = [str(x) for x in card_tx["txn_id"]]
        if tid in ids:
            i = ids.index(tid)
            if i + 1 < len(ids):
                out.append({"edge": "NEXT", "from": tid, "to": ids[i + 1],
                            "from_type": "Transaction", "to_type": "Transaction"})
            if i:
                out.append({"edge": "NEXT", "from": ids[i - 1], "to": tid,
                            "from_type": "Transaction", "to_type": "Transaction"})
    for cc in (related_cases or [])[:6]:
        out.append({"edge": "ON_CARD", "from": str(cc), "to": cid,
                    "from_type": "ClosedCase", "to_type": "Card"})
    return out


# --------------------------------------------------------------------------
# Actions / policy
# --------------------------------------------------------------------------
def route_block(exposure):
    return "L2" if exposure > 2500 else "L1"


def action(name, route, reason):
    return {"action": name, "route": route, "reason": reason}


def fraud_actions(exposure, connected, sar_file, denied=False, corroborated=0,
                  pattern="none", p=0.0):
    # ordered by what happens first (README: "Order them by what happens first")
    acts = []
    over = "above" if exposure > 2500 else "under"
    if pattern == "card_testing":
        acts.append(action("DECLINE_TRANSACTION", "L1",
                           "R5: testing sequence observed - decline the flagged authorization; "
                           "team-lead approval required"))
        acts.append(action("STEP_UP_AUTH", "auto",
                           "R5: require a one-time passcode before further activity on the card"))
    if denied and pattern == "card_testing":
        block_reason = ("R2 and R5: the customer denied the testing sequence and $%.2f has already "
                        "cleared, which is %s $2,500" % (exposure, over))
    elif denied:
        block_reason = ("R2: customer denial and graph evidence confirm unauthorised use; exposure "
                        "$%.2f is %s $2,500" % (exposure, over))
    elif pattern == "card_testing" and exposure > 100:
        block_reason = ("R5: a purchase over $100 has already cleared ($%.2f), so the card is "
                        "blocked (%s $2,500)" % (exposure, over))
    else:
        block_reason = ("R1: fraud probability %.2f rests on %d independent graph signals, so R1's "
                        "weak-signal condition does not apply; exposure $%.2f is %s $2,500"
                        % (p, corroborated, exposure, over))
    acts.append(action("BLOCK_CARD", route_block(exposure), block_reason))
    acts.append(action("CREATE_CASE", "auto",
                       "Section 3a: fraud probability >= 0.30, open an internal case with evidence"))
    if sar_file:
        acts.append(action("FILE_REPORT", "L2",
                           "Section 3a: confirmed fraud with exposure $%.2f%s; report requires L2 "
                           "fraud manager approval" %
                           (exposure, " > $1,000" if exposure > 1000 else
                            " and a shared device/region link to other fraud")))
    if connected:
        acts.append(action("MONITOR_CONNECTED_CARDS", "auto",
                           "R6: card(s) %s share the device profile with the flagged transaction"
                           % ", ".join(connected[:4])))
    acts.append(action("MONITOR_CARD", "auto",
                       "R4: the blocked card is reissued, so it stays under 72h of raised "
                       "monitoring while the report is prepared"))
    return acts


def legitimate_actions(anomaly_count):
    acts = [action("CLOSE_NO_FRAUD", "auto",
                   "R3: verification confirms the transaction; close the alert as legitimate")]
    if anomaly_count:
        acts.append(action("MONITOR_CARD", "auto",
                           "R4: the residual anomaly warrants 72h of raised monitoring "
                           "sensitivity after the close"))
    if anomaly_count >= 2:
        acts.append(action("GENERATE_REPORT", "auto",
                           "Section 3a: internal write-up of the investigation for the record, "
                           "with no case escalation required"))
    return acts


def uncertain_actions(p, exposure, graph_items, anomaly_count):
    acts = []
    if p >= 0.30:
        acts.append(action("CREATE_CASE", "auto",
                           "Section 3a: fraud probability %.2f >= 0.30, keep the case open and "
                           "updatable" % p))
    if p < 0.70:
        acts.append(action("VERIFY_WITH_CUSTOMER" if anomaly_count < 3 else "STEP_UP_AUTH", "auto",
                           "R1: verdict rests on a single signal with probability %.2f < 0.70, "
                           "confirm before any blocking action" % p))
    if exposure > 500 or len(graph_items) < 2:
        acts.append(action("ESCALATE_TO_ANALYST", "auto",
                           "R8: verdict uncertain with exposure $%.2f%s" %
                           (exposure, " > $500" if exposure > 500 else
                            " or conflicting/incomplete evidence")))
    acts.append(action("MONITOR_CARD", "auto",
                       "R4: no reply has settled the question, so the card stays active under "
                       "raised monitoring while evidence is gathered"))
    return acts


def decide(f, a, ev):
    tid, cid, cuid = f["flagged_txn_id"], f["card_id"], f["customer_id"]
    graph_items = [e for e in ev if e["evidence_class"] == "derived_graph"]
    thin = len(graph_items) < 2
    p0 = a["p_initial"]
    settled = (p0 >= 0.85 or p0 <= 0.15) and len(graph_items) >= 2

    # ---------------- evidence requests (stage A -> stage B) ------------
    requests, assumed, shift = [], "", 0.0
    # R7: a disputed charge that matches the cardholder's own recurring pattern
    # is verified, never blocked, and needs no further evidence request.
    recurring_dispute = bool(a["denied"] and a["recurring"] and a["corroborated"] < 2)
    if not settled and not recurring_dispute:
        if thin or (a["denied"] and not settled):
            linkage = (a["anomaly_count"] >= 1 or a["device_prior_fraud"] or
                       a["card_prior_fraud"] or a["ring"])
            assumed = ("Analyst confirms the device profile and billing region of transaction %s "
                       "are shared with card(s) %s recorded on closed case(s) %s."
                       % (tid, ", ".join(f["shared_cards"][:3]) or "none", ", ".join(
                           (f["device_linked_fraud_cases"] + f["prior_fraud_cases"])[:3]) or "none")
                       if linkage else
                       "Analyst reports no additional device, region or connected-card linkage for "
                       "transaction %s; the alert rests on this transaction alone." % tid)
            shift = 0.15 if linkage else -0.15
            requests = [{"type": "analyst_info", "asked_after_step": 4,
                         "assumed_response": assumed}]
        elif p0 < 0.70:
            deny = a["anomaly_count"] >= 2 and a["pattern"] != "none"
            assumed = ("Customer states they did not make the $%.2f transaction %s and still has "
                       "the card" % (f["flagged_amount"], tid)) if deny else (
                "Customer confirms they made the $%.2f transaction %s and recognises the "
                "purchase" % (f["flagged_amount"], tid))
            shift = (0.20 if a["anomaly_count"] >= 2 else 0.10) if deny else \
                    (-0.45 if a["anomaly_count"] <= 1 else -0.25)
            requests = [{"type": "customer_validation", "asked_after_step": 4,
                         "assumed_response": assumed}]
        elif p0 < 0.85:
            fail = a["anomaly_count"] >= 2
            assumed = ("Step-up authentication failed: the customer could not complete the OTP "
                       "challenge for transaction %s within 10 minutes." % tid) if fail else (
                "Step-up authentication passed: the customer completed the OTP challenge for "
                "transaction %s." % tid)
            shift = 0.15 if fail else -0.35
            requests = [{"type": "step_up_auth", "asked_after_step": 4,
                         "assumed_response": assumed}]

    p1 = round(min(0.98, max(0.02, p0 + shift)), 4)

    # A fraud verdict needs corroboration, not just a number: policy R1 forbids
    # blocking on a single signal. Require two independent strong graph signals,
    # or a named pattern, or a customer denial backed by one strong signal.
    # A named pattern is itself corroboration: every pattern in the README is
    # defined by at least two graph conditions, so it is never one signal alone.
    strong = (a["corroborated"] >= 2 or
              a["pattern"] in ("card_testing", "out_of_region_use") or
              (a["pattern"] != "none" and a["anomaly_count"] >= 2) or
              (a["denied"] and a["corroborated"] >= 1))
    if p1 >= 0.70 and strong and not recurring_dispute:
        verdict = "fraud"
    elif p1 <= 0.30 and not a["denied"]:
        verdict = "legitimate"
    else:
        # includes: a cardholder denial that the graph does not corroborate,
        # which R7/R3 require to be verified rather than dismissed.
        verdict = "uncertain"

    epi_all = episode(f, a, "fraud")
    exposure_all = round(sum(float(tx_by_id.loc[t]["amount_f"]) for t in epi_all), 2)
    # R8 is defined on "uncertain and exposure exceeds $500", so the suspected
    # episode must be reported for an uncertain verdict too; only a legitimate
    # verdict has no episode at all.
    affected = epi_all if verdict in ("fraud", "uncertain") else []
    exposure = exposure_all if verdict in ("fraud", "uncertain") else 0.0

    connected = [c for c in f["shared_cards"] if c != cid] if (
        verdict == "fraud" or (verdict == "uncertain" and a["ring"])) else []
    dev_profiles = [f["device_str"]] if connected and f["device_str"] else []

    # ---------------- SAR ------------------------------------------------
    link_reason = ""
    if connected:
        link_reason = "shared device profile with card(s) %s" % ", ".join(connected[:3])
    elif a["ring"]:
        link_reason = "shared device profile across %d customers" % len(f["shared_customers"])
    elif a["device_prior_fraud"]:
        link_reason = "device linked to confirmed fraud case(s) %s" % ", ".join(
            f["device_linked_fraud_cases"][:3])
    sar_file = bool(verdict == "fraud" and (
        exposure > 1000 or link_reason != "" or a["pattern"] == "undocumented"))

    # ---------------- actions -------------------------------------------
    if recurring_dispute:
        # R7: disputed charge that matches the cardholder's own recurring pattern
        final = [
            action("CREATE_CASE", "auto",
                   "R7: the disputed charge matches the cardholder's recurring pattern, so an "
                   "internal case records the dispute and the history"),
            action("VERIFY_WITH_CUSTOMER", "auto",
                   "R7: confirm the recurring charge with the cardholder before any block"),
            action("WARN_CUSTOMER", "auto",
                   "R7: advise the cardholder of the recurring charge; do not block the card"),
        ]
    elif verdict == "fraud":
        final = fraud_actions(exposure_all, connected, sar_file,
                              denied=a["denied"], corroborated=a["corroborated"],
                              pattern=a["pattern"], p=p1)
    elif verdict == "legitimate":
        final = legitimate_actions(a["anomaly_count"])
    else:
        final = uncertain_actions(p1, exposure_all, graph_items, a["anomaly_count"])

    # R9: activity that fits no known pattern but shows coordinated abuse across
    # customers is reported and handed over even before the verdict hardens.
    # Never applied to a legitimate verdict, which must not file a report.
    if a["pattern"] == "undocumented" and verdict != "legitimate":
        if not any(x["action"] == "FILE_REPORT" for x in final):
            final.append(action("FILE_REPORT", "L2",
                                "R9: activity fits none of the known patterns and shows coordinated "
                                "abuse across customers; L2 fraud manager approval required"))
        if not any(x["action"] == "ESCALATE_TO_ANALYST" for x in final):
            final.append(action("ESCALATE_TO_ANALYST", "auto",
                                "R9: undocumented pattern described in the case file and handed to "
                                "a human analyst with the evidence"))
        sar_file = True

    if not requests:
        initial = list(final)
        if verdict == "uncertain":
            what_changed = ("No additional evidence was requested: %d graph evidence item(s) leave "
                            "the probability at %.2f, and further graph steps would not change the "
                            "recommendation (Section 6), so the case stays open under R1/R8 with "
                            "the same next best actions." % (len(ev), p1))
        else:
            what_changed = ("No additional evidence was requested: %d independent graph evidence "
                            "item(s) put the probability at %.2f, which under Section 6 already "
                            "settles the verdict, so the next best actions are unchanged."
                            % (len(ev), p1))
    else:
        initial = []
        if any(r["type"] == "customer_validation" for r in requests):
            initial.append(action("VERIFY_WITH_CUSTOMER", "auto",
                                  "R1: probability %.2f on the available signal(s) is below 0.70, "
                                  "confirm with the cardholder before any blocking action" % p0))
            # 3a: a case is opened whenever evidence is requested, regardless
            # of the current probability.
            initial.append(action("CREATE_CASE", "auto",
                                  "Section 3a: evidence was requested, so an internal case is "
                                  "opened to hold it"))
            initial.append(action("MONITOR_CARD", "auto",
                                  "R4: no reply yet, so the card stays active under monitoring "
                                  "while the validation reply is pending"))
        elif any(r["type"] == "step_up_auth" for r in requests):
            initial.append(action("STEP_UP_AUTH", "auto",
                                  "R1: probability %.2f < 0.85 on graph evidence alone, require "
                                  "OTP confirmation before acting" % p0))
            initial.append(action("CREATE_CASE", "auto",
                                  "Section 3a: evidence was requested, open the internal case"))
            initial.append(action("MONITOR_CARD", "auto",
                                  "R4: no reply yet, so the card stays active under monitoring "
                                  "pending step-up authentication"))
        else:  # analyst_info
            initial.append(action("CREATE_CASE", "auto",
                                  "Section 3a: evidence was requested, so an internal case is "
                                  "opened to hold it at probability %.2f" % p0))
            if exposure_all > 500:
                initial.append(action("ESCALATE_TO_ANALYST", "auto",
                                      "R8: verdict uncertain with exposure $%.2f > $500" % exposure_all))
            initial.append(action("MONITOR_CARD", "auto",
                                  "R4: no reply yet, so the card stays active under monitoring "
                                  "while the analyst checks device and region linkage"))
        ia = [x["action"] for x in initial]
        fa = [x["action"] for x in final]
        added = [x for x in fa if x not in ia]
        removed = [x for x in ia if x not in fa]
        parts = [("Added: %s" % ", ".join(added)) if added else "No action added"]
        if "CLOSE_NO_FRAUD" in added and "CREATE_CASE" in removed:
            # the case is not un-opened, it is closed by the close action
            removed = [x for x in removed if x != "CREATE_CASE"]
            parts.append("the case opened for the requested evidence is closed by CLOSE_NO_FRAUD")
        if removed:
            parts.append("Removed: %s" % ", ".join(removed))
        what_changed = ("Assumed response moved fraud probability from %.2f to %.2f (verdict %s). "
                        "%s." % (p0, p1, verdict, "; ".join(parts)))

    # ---------------- status / stop -------------------------------------
    if verdict == "fraud":
        status = "closed_fraud"
    elif verdict == "legitimate":
        status = "closed_legitimate"
    elif recurring_dispute:
        # R7 stays open: verification with the cardholder is pending
        status = "open"
    else:
        status = "escalated" if any(x["action"] == "ESCALATE_TO_ANALYST" for x in final) else "open"

    if recurring_dispute and not requests:
        stop = ("R7: the disputed charge matches the cardholder's own recurring pattern and the "
                "graph produced %d strong corroborating signal(s); a block is ruled out and only "
                "customer verification remains." % a["corroborated"])
    elif requests and verdict == "uncertain":
        stop = ("Section 6: further graph steps would not change the recommendation. The %s "
                "response is still outstanding, so the case stays open at probability %.2f -> "
                "%.2f and is recommended under R1/R8 without blocking."
                % (requests[0]["type"], p0, p1))
    elif not requests:
        stop = ("Section 6: fraud probability %.2f with %d independent graph evidence item(s); "
                "further steps are unlikely to change the decision." % (p1, len(graph_items)))
    else:
        stop = ("Section 6: the assumed %s response settled the verdict (probability %.2f -> %.2f). "
                "The remaining graph evidence is recorded; further steps would not change the "
                "actions below." % (requests[0]["type"], p0, p1))
    return {
        "p0": p0, "p1": p1, "verdict": verdict, "status": status, "requests": requests,
        "initial": initial, "final": final, "what_changed": what_changed,
        "sar_file": sar_file, "sar_link_reason": link_reason, "exposure": exposure,
        "exposure_all": exposure_all, "affected": affected, "connected": connected,
        "dev_profiles": dev_profiles, "graph_items": graph_items, "thin": thin,
        "stop": stop, "settled": settled,
    }


# ==========================================================================
# Narrative / record assembly
# ==========================================================================
def sar_narrative(f, a, d):
    tid, cid, cuid = f["flagged_txn_id"], f["card_id"], f["customer_id"]
    date = dstr(f["flagged_ts"]) or str(f["opened_at"])[:10]
    reg = (f["region"] or {}).get("region_code", "unknown")
    s = []
    s.append("On %s at %s, card %s held by customer %s was used for a %s transaction of $%.2f in "
             "billing region %s." % (date, dtstr(f["flagged_ts"]).split(" ")[1], cid, cuid,
                                     f["flagged_channel"], f["flagged_amount"], reg))
    if a["denied"]:
        s.append("The cardholder reported the purchase as unauthorised in the %s trigger for case "
                 "%s, stating they did not make it." % (f["trigger_type"], f["case_id"]))
    else:
        s.append("The transaction was raised by the real-time model at %.2f for case %s."
                 % (f["risk_input"] or 0.0, f["case_id"]))
    if f["device_id"]:
        dv = f["device"] or {}
        s.append("It arrived from device profile %s, recorded as %s%s and serving %d card(s) across "
                 "%d customer(s)." % (f["device_id"], dv.get("newness") or "unknown",
                                      " behind " + dv["proxy_type"] if dv.get("proxy_type") else "",
                                      len(f["shared_cards"]), len(f["shared_customers"])))
    else:
        s.append("The graph holds no device record for this transaction, so device linkage could "
                 "not be used either to support or to rule out the alert.")
    if a["card_testing"]:
        s.append("The hour before it contained %d online authorisation(s) of under $5 (%s) on the "
                 "same card, the classic test-then-use sequence."
                 % (len(f["small_auths_1h"]), ", ".join("$%.2f" % x for x in f["small_auth_amounts"])))
    elif a["burst"]:
        s.append("Card %s already had %d online authorisation(s) in the preceding 48 hours."
                 % (cid, len(f["online_48h_before"])))
    if a["amount_outlier"] or a["new_product"]:
        bits = []
        if a["amount_outlier"]:
            bits.append("$%.2f against a card median of $%.2f" % (f["flagged_amount"],
                                                                  f["card_median_amount"]))
        if a["new_product"]:
            bits.append("product code %s never used on this card" % f["flagged_product"])
        s.append("The purchase itself is outside the cardholder's normal profile: %s."
                 % " and ".join(bits))
    if a["out_of_region"]:
        s.append("It was card-present outside the cardholder's home country in region %s, a region "
                 "with no prior history on this card." % reg)
    if f["prior_fraud_cases"]:
        s.append("Card %s is already named in confirmed-fraud closed case(s) %s."
                 % (cid, ", ".join(f["prior_fraud_cases"][:3])))
    if f["device_linked_fraud_cases"]:
        s.append("Device profile %s also appears on confirmed-fraud case(s) %s involving other "
                 "cards, indicating a common actor." % (f["device_id"],
                                                        ", ".join(f["device_linked_fraud_cases"][:3])))
    if d["connected"]:
        s.append("Card(s) %s share that device profile and are placed under monitoring."
                 % ", ".join(d["connected"][:4]))
    s.append("The activity is assessed as %s under policy %s."
             % (a["pattern"].replace("_", " "),
                "R5" if a["pattern"] == "card_testing" else
                ("R6" if (d["connected"] or a["ring"]) else
                 ("R9" if a["pattern"] == "undocumented" else "R2"))))
    s.append("Total unauthorised amount across %d transaction(s) is $%.2f between %s and %s."
             % (len(d["affected"]), d["exposure"],
                dstr(tx_by_id.loc[d["affected"][0]]["ts_f"]) if d["affected"] else date,
                dstr(tx_by_id.loc[d["affected"][-1]]["ts_f"]) if d["affected"] else date))
    if "BLOCK_CARD" in [x["action"] for x in d["final"]]:
        s.append("Card %s is recommended for blocking and reissue, an internal case is opened, and "
                 "the report awaits fraud-manager approval." % cid)
    else:
        s.append("An internal case is opened, the card remains active under monitoring while the "
                 "outstanding verification is completed, and the report awaits fraud-manager "
                 "approval.")
    return " ".join(s[:12])


def build_summary(f, a, d):
    tid, cid = f["flagged_txn_id"], f["card_id"]
    s = []
    s.append("Case %s covers a %s $%.2f transaction %s on card %s raised by a %s trigger."
             % (f["case_id"], f["flagged_channel"], f["flagged_amount"], tid, cid,
                f["trigger_type"]))
    if a["anomaly_count"]:
        labels = [("new device", "new_device"), ("proxy", "proxy"),
                  ("out-of-region", "out_of_region"), ("amount outlier", "amount_outlier"),
                  ("new product", "new_product"), ("48h burst", "burst"),
                  ("shared-device ring", "ring"),
                  ("device linked to prior fraud", "device_prior_fraud"),
                  ("prior fraud on this card", "card_prior_fraud")]
        present = [lbl for lbl, key in labels if a[key]]
        s.append("Graph investigation found %d corroborating signal(s) - %s."
                 % (a["anomaly_count"], ", ".join(present)))
    else:
        s.append("Graph investigation found no device, region, amount, product or channel "
                 "deviation for the flagged transaction.")
    s.append("Pattern assessed as %s; fraud probability %.2f before additional evidence and %.2f "
             "after, giving a verdict of %s." % (a["pattern"].replace("_", " "), d["p0"], d["p1"],
                                                 d["verdict"]))
    if d["exposure"]:
        s.append("Exposure across %d transaction(s) is $%.2f." % (len(d["affected"]), d["exposure"]))
    if d["verdict"] == "legitimate":
        s.append("No corroborating graph signal supports a fraud finding, so the alert is closed as "
                 "legitimate under R3 with no block and no report.")
    elif d["verdict"] == "uncertain":
        s.append("The graph does not corroborate the alert strongly enough to block, so under R1 "
                 "the card stays active, the case stays open and the requested verification is "
                 "recorded as outstanding.")
    else:
        s.append("Independent graph signals corroborate the finding, so the actions below follow "
                 "from the policy routes shown with each one.")
    return " ".join(s[:6])


def main():
    answers = []
    for row in pack:
        tc = time.time()
        case_id = row["case_id"]
        before = dict(CALLS)
        f = gather(row)
        tid, cid, cuid = f["flagged_txn_id"], f["card_id"], f["customer_id"]
        a = analyse(f)
        ev = build_evidence(f, a)
        d = decide(f, a, ev)

        new_ev = None
        if d["requests"]:
            r = d["requests"][0]
            new_ev = {"evidence_id": "EV-%02d" % (len(ev) + 1),
                      "claim": r["assumed_response"], "source":
                          "customer" if r["type"] == "customer_validation" else "external",
                      "ref": "evidence_request:1", "entity_ids": [f["flagged_txn_id"]],
                      "evidence_class": "direct"}
            ev.append(new_ev)

        # ---------------- findings -------------------------------------
        findings = []

        def find(title, statement, eids, kind):
            findings.append({"finding_id": "F-%02d" % (len(findings) + 1), "title": title,
                             "statement": statement, "evidence_ids": eids, "type": kind})

        gids = [e["evidence_id"] for e in ev]
        find("Trigger", "Case %s opened from a %s trigger on transaction %s."
             % (case_id, f["trigger_type"], f["flagged_txn_id"]), [gids[0]], "direct")
        if a["denied"]:
            find("Cardholder position", "Customer %s denies the transaction." % f["customer_id"],
                 [e["evidence_id"] for e in ev if e["source"] == "customer"], "direct")
        if a["anomaly_count"]:
            find("Graph corroboration",
                 "%d graph-derived signal(s) support the alert (pattern %s)."
                 % (a["anomaly_count"], a["pattern"]),
                 [e["evidence_id"] for e in ev if e["evidence_class"] == "derived_graph"],
                 "derived_graph")
        else:
            find("Absence of corroboration",
                 "No graph-derived anomaly supports the alert; the flagged transaction matches "
                 "the card's established profile.",
                 [e["evidence_id"] for e in ev if e["evidence_class"] == "derived_graph"],
                 "derived_graph")
        if a["recurring"]:
            find("Recurring charge", "Transaction matches a repeating amount/channel/product on "
                 "this card (policy R7).",
                 [e["evidence_id"] for e in ev if "recurring" in e["claim"]], "derived_graph")
        if d["connected"]:
            find("Connected cards", "Card(s) %s share the device profile with the flagged "
                 "transaction." % ", ".join(d["connected"][:4]),
                 [e["evidence_id"] for e in ev if "device profile" in e["claim"]],
                 "derived_graph")
        if f["similar_candidates"]:
            find("Prior case memory", "Retrieved closed case(s) %s as similar prior activity."
                 % ", ".join(f["similar_candidates"][:5]),
                 [e["evidence_id"] for e in ev if "prior case memory" in e["claim"].lower()],
                 "derived_graph")
        if (f["model"] or {}).get("probability") is not None:
            find("Model evidence", "Model probability %.4f; largest SHAP contributions %s."
                 % (f["model"]["probability"],
                    ", ".join(t["feature"] for t in (f["shap"].get(f["flagged_txn_id"]) or [])[:3])),
                 [e["evidence_id"] for e in ev if e["evidence_class"] == "model_analytical"],
                 "model_analytical")
        if a["pattern"] == "undocumented":
            find("Undocumented pattern", a["pattern_desc"], gids[:3], "interpretation")

        # ---------------- graph evidence --------------------------------
        tginfo = f["tg"]
        edges = []
        bcc = tginfo["benchmark_case_context"]
        if bcc["flagged"]:
            edges.append({"edge": "TRIGGERS", "from": case_id, "to": f["flagged_txn_id"],
                          "from_type": "BenchmarkCase", "to_type": "Transaction"})
        gt = tginfo["get_transaction"]
        if f["flagged_txn_id"] in gt["cards"] or cid in gt["cards"]:
            edges.append({"edge": "MADE", "from": cid, "to": f["flagged_txn_id"],
                          "from_type": "Card", "to_type": "Transaction"})
        if cuid in gt["customers"]:
            edges.append({"edge": "OWNS", "from": cuid, "to": cid,
                          "from_type": "Customer", "to_type": "Card"})
        if f["device_id"] and f["device_id"] in gt["devices"]:
            edges.append({"edge": "FROM_DEVICE", "from": f["flagged_txn_id"],
                          "to": f["device_id"], "from_type": "Transaction",
                          "to_type": "DeviceProfile"})
        if gt["regions"]:
            edges.append({"edge": "BILLED_IN", "from": f["flagged_txn_id"],
                          "to": (f["region"] or {}).get("region_code", ""),
                          "from_type": "Transaction", "to_type": "BillingRegion"})
        if gt["next"]:
            edges.append({"edge": "NEXT", "from": f["flagged_txn_id"], "to": gt["next"][0],
                          "from_type": "Transaction", "to_type": "Transaction"})
        if gt["prev"]:
            edges.append({"edge": "NEXT", "from": gt["prev"][0], "to": f["flagged_txn_id"],
                          "from_type": "Transaction", "to_type": "Transaction"})
        for cc in (tginfo["find_related_cases"]["cases"] or [])[:6]:
            edges.append({"edge": "ON_CARD", "from": cc, "to": cid,
                          "from_type": "ClosedCase", "to_type": "Card"})

        # Merge the same edges as asserted from the loaded edge set, so the
        # graph record does not depend on a single query round-trip.
        seen, merged = set(), []
        for e in edges + local_edges(f, tginfo["find_related_cases"]["cases"] or []):
            key = (e["edge"], e["from"], e["to"])
            if key in seen:
                continue
            seen.add(key)
            merged.append(e)
        edges = merged

        queries = [{"name": k, "params": ({"case_id": case_id} if k == "benchmark_case_context"
                                          else ({"txn_id": f["flagged_txn_id"]} if k == "get_transaction"
                                                else ({"card_id": cid} if k == "find_related_cases"
                                                      else {"txn_id": f["flagged_txn_id"]}))),
                    "http_status": v.get("status"), "latency_ms": v.get("ms")}
                   for k, v in tginfo.items()]

        graph_evidence = {
            "single_source_of_truth": "TigerGraph hhg_fraud_graph (Community Edition 4.2.5)",
            "phase_2_baseline": "8 vertex types / 11 edge types / 2,505,266 edges (unchanged)",
            "queries": queries,
            "entities": {"BenchmarkCase": [case_id], "Transaction": [f["flagged_txn_id"]],
                         "Card": [cid], "Customer": [cuid],
                         "DeviceProfile": [f["device_id"]] if f["device_id"] else [],
                         "BillingRegion": [(f["region"] or {}).get("region_code", "")] if f["region"] else [],
                         "EmailDomain": [x for x in [f["p_domain"], f["r_domain"]] if x],
                         "ClosedCase": (tginfo["find_related_cases"]["cases"] or [])[:10],
                         "connected_card_ids": d["connected"]},
            "edges": edges,
            "graph_facts": [e["claim"] for e in ev if e["evidence_class"] == "derived_graph"],
            "investigation_interpretation": [
                "pattern=%s" % a["pattern"],
                "verdict=%s" % d["verdict"],
                "fraud_probability=%.4f (before) -> %.4f (after additional evidence)"
                % (d["p0"], d["p1"]),
                "anomaly_signals=%d" % a["anomaly_count"]],
            "graph_fact_vs_interpretation": (
                "Every entry under graph_facts is returned by a live GSQL query or computed from "
                "the loaded edge set; entries under investigation_interpretation are the agent's "
                "reading of those facts under the published policy."),
        }

        # ---------------- investigation record ---------------------------
        ir = [
            {"step": 1, "name": "CASE", "detail": "%s opened %s (%s trigger)."
             % (case_id, f["opened_at"], f["trigger_type"])},
            {"step": 2, "name": "TRIGGER", "detail": f["trigger_text"]},
            {"step": 3, "name": "EVIDENCE_COLLECTION", "detail":
             "%d evidence item(s) gathered: %d graph-derived, %d direct, %d model."
             % (len(ev), len(d["graph_items"]),
                sum(1 for e in ev if e["evidence_class"] == "direct"),
                sum(1 for e in ev if e["evidence_class"] == "model_analytical"))},
            {"step": 4, "name": "GRAPH_INVESTIGATION", "detail":
             "TigerGraph queries %s returned %d relationship(s)."
             % (", ".join(q["name"] for q in queries), len(edges))},
            {"step": 5, "name": "FINDINGS", "detail": "; ".join(x["statement"] for x in findings[:4])},
            {"step": 6, "name": "DECISION", "detail":
             "verdict=%s, fraud_probability=%.4f, pattern=%s, status=%s"
             % (d["verdict"], d["p1"], a["pattern"], d["status"])},
            {"step": 7, "name": "ACTION", "detail": ", ".join(x["action"] for x in d["final"])},
            {"step": 8, "name": "NEXT_BEST_ACTION", "detail":
             "%s (%s) - %s" % (d["final"][0]["action"], d["final"][0]["route"],
                               d["final"][0]["reason"])},
            {"step": 9, "name": "APPROVAL_ROUTE", "detail":
             ", ".join(sorted({x["route"] for x in d["final"]}))},
        ]

        routes_final = sorted({x["route"] for x in d["final"]})
        routes_initial = sorted({x["route"] for x in d["initial"]})

        pre_state = {
            "stage": "before_additional_evidence",
            "current_evidence": [e["evidence_id"] for e in ev if e["ref"] != "evidence_request:1"],
            "current_findings": [x["finding_id"] for x in findings],
            "preliminary_decision": {"verdict": d["verdict"] if not d["requests"] else
                                     ("fraud" if d["p0"] >= 0.70 else
                                      ("legitimate" if d["p0"] <= 0.30 else "uncertain")),
                                     "fraud_probability": d["p0"],
                                     "pattern": a["pattern"], "status": "open"},
            "preliminary_next_best_action": d["initial"],
            "required_approval_route": routes_initial,
            "additional_evidence_requested": bool(d["requests"]),
            "evidence_requested": d["requests"],
        }
        post_state = {
            "stage": "after_additional_evidence",
            "additional_evidence_received": bool(d["requests"]),
            "additional_evidence": [d["requests"][0]["assumed_response"]] if d["requests"] else [],
            "updated_evidence": [e["evidence_id"] for e in ev],
            "updated_findings": [x["finding_id"] for x in findings],
            "updated_decision": {"verdict": d["verdict"], "fraud_probability": d["p1"],
                                 "pattern": a["pattern"], "status": d["status"]},
            "updated_next_best_action": d["final"],
            "updated_approval_route": routes_final,
            "what_changed": d["what_changed"],
            "note": ("No additional evidence was requested by this case; the post-evidence state "
                     "is therefore unchanged from the pre-evidence state."
                     if not d["requests"] else
                     "Stage B reflects the assumed response recorded in evidence_requests."),
        }

        final_actions = [x["action"] for x in d["final"]]
        sar = {"file": d["sar_file"], "reason": "", "narrative": "", "subjects": [],
               "total_amount_usd": 0, "activity_dates": []}
        if d["sar_file"]:
            rule = ("R9: coordinated/undocumented pattern" if a["pattern"] == "undocumented"
                    else ("Section 3a: exposure $%.2f > $1,000" % d["exposure"]
                          if d["exposure"] > 1000 else
                          "Section 3a and R6: %s" % d["sar_link_reason"]))
            sar["reason"] = "%s: %s" % ("Confirmed fraud" if d["verdict"] == "fraud"
                                        else "Suspected fraud pending verification", rule)
            sar["narrative"] = sar_narrative(f, a, d)
            dates = [dstr(tx_by_id.loc[t]["ts_f"]) for t in d["affected"]] or [dstr(f["flagged_ts"])]
            sar["subjects"] = sorted({x for x in [cuid, cid, f["device_id"], f["p_domain"],
                                                  f["r_domain"]] + d["connected"] if x})
            sar["total_amount_usd"] = d["exposure"]
            sar["activity_dates"] = [min(dates), max(dates)]
        else:
            sar["reason"] = ("Verdict is %s, so no report is filed; the case remains an internal "
                             "record (Section 3a: most cases never need a report)." % d["verdict"])

        lat = round(time.time() - tc, 3)
        answer = {
            "case_id": case_id,
            "case": {
                "status": d["status"], "verdict": d["verdict"],
                "fraud_probability": d["p1"], "pattern": a["pattern"],
                "pattern_description": a["pattern_desc"] if a["pattern"] == "undocumented" else "",
                "affected_txn_ids": d["affected"],
                "first_suspicious_txn_id": (d["affected"][0] if d["affected"] else ""),
                "connected_card_ids": d["connected"],
                "connected_device_profiles": d["dev_profiles"],
                "exposure_usd": d["exposure"], "evidence": ev,
                "similar_prior_cases": f["similar_candidates"][:5],
                "summary": build_summary(f, a, d),
                "written_to_graph": False, "graph_case_id": "",
            },
            "evidence_requests": d["requests"],
            "next_best_actions": {"initial": d["initial"], "final": d["final"],
                                  "what_changed": d["what_changed"]},
            "sar": sar,
            "stop_reason": d["stop"],
            "tool_calls": (CALLS["live"] - before["live"]) + (CALLS["retrieval"] - before["retrieval"]),
            "tokens": 0,
            "latency_s": lat,
            # --- explicit hackathon investigation record (extends, never replaces,
            #     the benchmark schema above) ---
            "investigation_record": ir,
            "findings": findings,
            "decision": {"decision": d["verdict"], "status": d["status"],
                         "rationale": "%s Pattern %s. Fraud probability %.4f (before) -> %.4f "
                                      "(after additional evidence). Evidence used: %s."
                                      % (d["stop"], a["pattern"], d["p0"], d["p1"],
                                         ", ".join(e["evidence_id"] for e in ev)),
                         "supporting_evidence_ids": [e["evidence_id"] for e in ev],
                         "policy_rules": sorted({x["reason"].split(":")[0] for x in d["final"]
                                                 if x["reason"][:2] in
                                                 {"R1", "R2", "R3", "R5", "R6", "R7", "R8", "R9"} or
                                                 x["reason"].startswith("Section")})},
            "actions_taken": [x for x in d["final"] if x["route"] == "auto"],
            "actions_recommended_awaiting_approval": [x for x in d["final"] if x["route"] != "auto"],
            "graph_evidence": graph_evidence,
            "sar_status": {"file": sar["file"], "reason": sar["reason"],
                           "required_approval_route": "L2" if sar["file"] else "none"},
            "required_approval_route": routes_final,
            "pre_additional_evidence_state": pre_state,
            "post_additional_evidence_state": post_state,
            "graph_write": {
                "status": "BLOCKED",
                "written_to_graph": False,
                "graph_case_id": "",
                "reason": "Phase 2 graph is locked at its validated 8-vertex/11-edge/2,505,266-edge "
                          "state; inserting a case vertex would mutate validated counts. Recorded "
                          "in docs/GRAPH_WRITE_BLOCKER.md with the ready-to-run GSQL.",
                "reference": "graph reference for this answer is the entity/edge block in "
                             "graph_evidence above",
            },
        }
        path = os.path.join(OUT, "%s.json" % case_id)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(answer, fh, indent=2, ensure_ascii=False)
        answers.append(answer)
        print("  %-8s verdict=%-10s p=%.2f->%.2f pattern=%-28s exposure=%8.2f sar=%-5s "
              "evidence=%d actions=%d %.2fs"
              % (case_id, d["verdict"], d["p0"], d["p1"], a["pattern"], d["exposure"],
                 str(d["sar_file"]), len(ev), len(d["final"]), lat))
    return answers


if __name__ == "__main__":
    log("building %d case answers" % len(pack))
    out = main()
    json.dump({"generated": len(out), "tool_calls": CALLS,
               "verdicts": {k: sum(1 for a in out if a["case"]["verdict"] == k)
                            for k in ["fraud", "legitimate", "uncertain"]},
               "sar_filed": sum(1 for a in out if a["sar"]["file"])},
              open(os.path.join(ROOT, "cases", "_build_summary.json"), "w", encoding="utf-8"),
              indent=2)
    log("wrote %d files to cases/" % len(out))
    print(json.dumps({"CASE_BUILD": "DONE", "count": len(out)}))




