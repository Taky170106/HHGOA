import csv, io, json, sys, time, urllib.request, urllib.parse, base64, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = "http://localhost:9000/query/hhg_fraud_graph"
AUTH = base64.b64encode(b"tigergraph:tigergraph").decode()
ROOT = r"D:\HHG"

def call(name, params=None, timeout=180):
    url = BASE + "/" + name
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Basic " + AUTH})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace"); status = r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace"); status = e.code
    except Exception as e:
        return {"http_status": None, "ok": False, "error": str(e),
                "elapsed_ms": round((time.time()-t0)*1000, 1)}
    ms = round((time.time()-t0)*1000, 1)
    out = {"http_status": status, "elapsed_ms": ms}
    try:
        j = json.loads(body)
    except Exception:
        out["ok"] = status == 200; out["raw"] = body[:300]; return out
    out["ok"] = (not j.get("error", False)) and status == 200
    if j.get("error"):
        out["error"] = j.get("message", "")
    res = j.get("results", [])
    counts = {}
    if res and isinstance(res[0], dict):
        for x in res:
            for k, v in x.items():
                counts[k] = len(v) if isinstance(v, list) else v
    out["result_structure"] = counts
    return out

def ids(name, params, key):
    r = call(name, params)
    out = []
    try:
        body = urllib.request.urlopen(
            urllib.request.Request(BASE + "/" + name + "?" + urllib.parse.urlencode(params),
                                   headers={"Authorization": "Basic " + AUTH}), timeout=120
        ).read().decode()
        for blk in json.loads(body).get("results", []):
            if key in blk and isinstance(blk[key], list):
                out = [v["v_id"] for v in blk[key]]
    except Exception:
        pass
    return out, r

def rd(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return list(csv.DictReader(f))

bench = rd("data/vertices/benchmark_case.csv")
INV = rd("data/edges/involves.csv")
DEV = rd("data/edges/from_device.csv")

TXN = "3000120"            # first transaction inside a real ClosedCase
TXN_DEV = DEV[0]["from_txn_id"]
DEV_ID = DEV[0]["to_device_profile_id"]
CARD = "C00259-K1"
CUST = "C00259"
CASE = "CC-0001"

INVQ = ["get_transaction", "find_related_transactions", "find_device_connections",
        "find_related_cases", "benchmark_case_context", "get_card_history",
        "get_customer_history", "temporal_chain", "calculate_exposure",
        "calculate_exposure_list"]

res = {"install": {}, "execution": {}, "invalid": {}, "benchmark": [],
       "e2e": {}, "determinism": {}, "performance": []}

print("=" * 72); print("1. INSTALL STATE (bare GET; 404 == NOT installed)"); print("=" * 72)
for n in INVQ:
    r = call(n)
    res["install"][n] = {"http_status": r.get("http_status"), "elapsed_ms": r.get("elapsed_ms"),
                         "message": r.get("error", ""), "installed": r.get("http_status") != 404}
    print(f"  {n:28s} HTTP {r.get('http_status')} {r.get('elapsed_ms')}ms  "
          f"{'NOT-404 OK' if r.get('http_status') != 404 else '404 !!!'}  "
          f"{r.get('error','')[:55]}")

tests = [
 ("get_transaction","valid txn",{"txn_id":TXN}),
 ("get_transaction","valid txn w/ device",{"txn_id":TXN_DEV}),
 ("find_related_transactions","txn depth2 limit50",{"txn_id":TXN,"card_id":"","customer_id":"","max_depth":2,"max_results":50}),
 ("find_related_transactions","card depth2 limit50",{"txn_id":"","card_id":CARD,"customer_id":"","max_depth":2,"max_results":50}),
 ("find_related_transactions","customer depth2 limit50",{"txn_id":"","card_id":"","customer_id":CUST,"max_depth":2,"max_results":50}),
 ("find_related_transactions","depth1 bounded",{"txn_id":TXN,"card_id":"","customer_id":"","max_depth":1,"max_results":50}),
 ("find_device_connections","valid txn",{"txn_id":TXN_DEV,"device_profile_id":""}),
 ("find_device_connections","valid device",{"txn_id":"","device_profile_id":DEV_ID}),
 ("find_related_cases","valid txn",{"txn_id":TXN,"card_id":"","customer_id":"","device_profile_id":"","region_code":"","domain":""}),
 ("find_related_cases","valid card",{"txn_id":"","card_id":CARD,"customer_id":"","device_profile_id":"","region_code":"","domain":""}),
 ("find_related_cases","valid customer",{"txn_id":"","card_id":"","customer_id":CUST,"device_profile_id":"","region_code":"","domain":""}),
 ("find_related_cases","valid device",{"txn_id":"","card_id":"","customer_id":"","device_profile_id":DEV_ID,"region_code":"","domain":""}),
 ("get_card_history","valid card",{"card_id":CARD}),
 ("get_customer_history","valid customer",{"customer_id":CUST}),
 ("temporal_chain","valid card",{"card_id":CARD}),
 ("calculate_exposure","valid txns",{"txn_ids_csv":TXN}),
]

print(); print("=" * 72); print("2. LIVE EXECUTION (real dataset identifiers)"); print("=" * 72)
for name, label, p in tests:
    r = call(name, p)
    res["execution"][f"{name} :: {label}"] = {
        "params": p, "http_status": r.get("http_status"), "ok": r.get("ok"),
        "elapsed_ms": r.get("elapsed_ms"), "error": r.get("error", ""),
        "result_structure": r.get("result_structure", {})}
    res["performance"].append({"query": name, "elapsed_ms": r.get("elapsed_ms")})
    print(f"  [{'OK ' if r.get('ok') else 'ERR'}] {name:26s} {label:24s} "
          f"HTTP {r.get('http_status')} {r.get('elapsed_ms'):>7}ms "
          f"{str(r.get('result_structure'))[:80]}")

invs = [
 ("get_transaction","invalid id",{"txn_id":"999999999"}),
 ("get_transaction","empty input",{"txn_id":""}),
 ("find_related_transactions","empty input",{"txn_id":"","card_id":"","customer_id":"","max_depth":2,"max_results":50}),
 ("find_device_connections","invalid id",{"txn_id":"NOPE","device_profile_id":""}),
 ("benchmark_case_context","invalid case",{"case_id":"HHG-999"}),
]
print(); print("=" * 72); print("3. INVALID / EMPTY INPUT"); print("=" * 72)
for name, label, p in invs:
    r = call(name, p)
    res["invalid"][f"{name} :: {label}"] = {"params": p, "http_status": r.get("http_status"),
        "ok": r.get("ok"), "error": r.get("error",""), "result_structure": r.get("result_structure",{})}
    print(f"  [{ 'OK ' if r.get('ok') else 'ERR'}] {name:26s} {label:16s} "
          f"HTTP {r.get('http_status')} {str(r.get('result_structure'))[:70]}")

# ---------- end-to-end investigation path for HHG-001 ----------
print(); print("=" * 72); print("4. END-TO-END INVESTIGATION PATH (HHG-001)"); print("=" * 72)
bc = bench[0]
e2e = {"case_id": "HHG-001"}
_, r = ids("benchmark_case_context", {"case_id": "HHG-001"}, "Flagged")
e2e["benchmark__flagged_txn"] = r.get("result_structure", {}).get("Flagged")
flagged = ids("benchmark_case_context", {"case_id": "HHG-001"}, "Flagged")[0]
e2e["step1_benchmark_triggers_txn"] = {"ids": flagged, "expected": bc["flagged_txn_id"],
                                       "match": flagged[:1] == [bc["flagged_txn_id"]]}
print(f"  1. BenchmarkCase -TRIGGERS-> Transaction : {flagged} (expected {bc['flagged_txn_id']})")

txn = flagged[0] if flagged else TXN
crd = ids("get_transaction", {"txn_id": txn}, "CardOwners")[0]
e2e["step2_txn_to_card"] = {"ids": crd, "expected": bc["card_id"], "match": crd[:1] == [bc["card_id"]]}
print(f"  2. Transaction -<-MADE- Card             : {crd} (expected {bc['card_id']})")

cus = ids("get_transaction", {"txn_id": txn}, "Customers")[0]
e2e["step3_card_to_customer"] = {"ids": cus, "expected": bc["customer_id"], "match": cus[:1] == [bc["customer_id"]]}
print(f"  3. Card -<-OWNS- Customer                : {cus} (expected {bc['customer_id']})")

dev = ids("get_transaction", {"txn_id": txn}, "Devices")
e2e["step4_txn_to_device"] = {"ids": dev}
print(f"  4. Transaction -FROM_DEVICE-> DeviceProfile: {dev}")

dtx = ids("find_device_connections", {"txn_id": txn, "device_profile_id": ""}, "LinkedTxns")
e2e["step5_device_to_related_txns"] = {"count": len(dtx), "sample": dtx[:5]}
print(f"  5. DeviceProfile -> related Transactions  : {len(dtx)} {dtx[:5]}")

cases_ids, rc = ids("find_related_cases", {"txn_id": txn, "card_id": "", "customer_id": "",
                                           "device_profile_id": "", "region_code": "", "domain": ""},
                    "@@seedCases")
card_cases = ids("find_related_cases", {"txn_id": "", "card_id": crd[0] if crd else CARD,
                                        "customer_id": "", "device_profile_id": "",
                                        "region_code": "", "domain": ""}, "@@seedCases")
e2e["step6_historical_cases"] = {"via_txn": cases_ids, "via_card": card_cases,
                                 "case_expected": CASE}
print(f"  6. historical ClosedCase via txn         : {cases_ids}")
print(f"     historical ClosedCase via card        : {card_cases}")
bh = res["execution"].get("get_card_history :: valid card", {}).get("result_structure", {})
e2e["card_history"] = bh
e2e["all_steps_ok"] = (e2e["step1_benchmark_triggers_txn"]["match"]
                       and e2e["step2_txn_to_card"]["match"]
                       and e2e["step3_card_to_customer"]["match"])
print(f"  E2E core path (case->txn->card->customer) OK = {e2e['all_steps_ok']}")
res["e2e"] = e2e

# ---------- 20 benchmark cases ----------
print(); print("=" * 72); print("5. ALL 20 BENCHMARK CASES"); print("=" * 72)
ok = 0
for row in bench:
    cid = row["case_id"]
    r = call("benchmark_case_context", {"case_id": cid})
    st = r.get("result_structure", {})
    fid = ids("benchmark_case_context", {"case_id": cid}, "Flagged")[0]
    good = bool(r.get("ok")) and fid[:1] == [row["flagged_txn_id"]]
    ok += 1 if good else 0
    res["benchmark"].append({"case_id": cid, "http_status": r.get("http_status"),
        "expected_txn": row["flagged_txn_id"], "returned_txn": fid[:1],
        "expected_card": row["card_id"], "ok": bool(r.get("ok")),
        "trigger_match": fid[:1] == [row["flagged_txn_id"]],
        "elapsed_ms": r.get("elapsed_ms"), "result_structure": st})
    print(f"  {cid} HTTP {r.get('http_status')} txn {fid[:1]} == {row['flagged_txn_id']} "
          f"{'OK' if good else 'FAIL'} {r.get('elapsed_ms')}ms")
res["benchmark_pass"] = ok
print(f"  BENCHMARK: {ok}/20")

a = call("get_transaction", {"txn_id": txn})
b = call("get_transaction", {"txn_id": txn})
res["determinism"] = {"run1": a.get("result_structure"), "run2": b.get("result_structure"),
                      "equivalent": a.get("result_structure") == b.get("result_structure")}
print(f"\n  DETERMINISM equivalent = {res['determinism']['equivalent']}")

res["inputs_used"] = {"txn_id": txn, "txn_with_device": TXN_DEV, "card_id": CARD,
                      "customer_id": CUST, "device_profile_id": DEV_ID, "closed_case": CASE}
res["http_404_count"] = sum(1 for v in res["install"].values() if v["http_status"] == 404)
res["execution_failures"] = [k for k, v in res["execution"].items() if not v["ok"]]
res["invalid_failures"] = [k for k, v in res["invalid"].items() if not v["ok"]]

os.makedirs(os.path.join(ROOT, "tigergraph", "validation"), exist_ok=True)
p = os.path.join(ROOT, "tigergraph", "validation", "phase3_validation.json")
with open(p, "w", encoding="utf-8") as f:
    json.dump(res, f, indent=2)
print(f"\n  http_404_count = {res['http_404_count']}")
print(f"  execution_failures = {res['execution_failures']}")
print(f"  invalid_failures = {res['invalid_failures']}")
print(f"  WROTE {p}")
