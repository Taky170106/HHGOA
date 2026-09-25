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
            body = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        status = e.code
    except Exception as e:
        return {"http_status": None, "ok": False, "error": str(e),
                "elapsed_ms": round((time.time()-t0)*1000, 1)}
    ms = round((time.time()-t0)*1000, 1)
    out = {"http_status": status, "elapsed_ms": ms}
    try:
        j = json.loads(body)
    except Exception:
        out["ok"] = status == 200
        out["raw"] = body[:300]
        return out
    out["ok"] = (not j.get("error", False)) and status == 200
    if j.get("error"):
        out["error"] = j.get("message", "")
    res = j.get("results", [])
    out["result_keys"] = [list(x.keys())[0] for x in res if isinstance(x, dict) and x] if res else []
    counts = {}
    if res and isinstance(res[0], dict):
        for x in res:
            for k, v in x.items():
                if isinstance(v, list):
                    counts[k] = len(v)
                elif isinstance(v, str) and v in ("NOT_FOUND", "NO_SEED", "NO_DEVICE_FOUND",
                                                  "BENCHMARK_NOT_FOUND"):
                    counts[k] = v
                else:
                    counts[k] = v
    out["result_structure"] = counts
    if not out.get("error") and not counts and status == 200:
        out["ok"] = True
    return out

def rd(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return list(csv.DictReader(f))

bench = rd("data/vertices/benchmark_case.csv")
cases = rd("data/vertices/closed_case.csv")
doms = rd("data/vertices/email_domain.csv")
txns = rd("data/edges/triggers.csv")

TXN = "3514030"
CARD = "C12382-K1"
CUST = "C12382"
DOMAIN = doms[0]["domain"]
CASE = cases[0]["case_id"]

# discover a real device id from the graph itself
probe = call("get_transaction", {"txn_id": TXN})
DEV = None
if probe.get("result_structure", {}).get("Devices"):
    pass
# fall back: read device ids from the loader source edge file
for r in rd("data/edges/from_device.csv"):
    if r["from_txn_id"] == TXN:
        DEV = r["to_device_profile_id"]
        break
if not DEV:
    DEV = rd("data/edges/from_device.csv")[0]["to_device_profile_id"]

Q = ["get_transaction", "find_related_transactions", "find_device_connections",
     "find_related_cases", "benchmark_case_context"]

results = {"install_check": {}, "execution": {}, "invalid_input": {}, "benchmark": []}

print("=" * 70)
print("A. INSTALL STATE (bare RESTPP GET - 404 would mean NOT installed)")
print("=" * 70)
for n in Q:
    r = call(n)
    results["install_check"][n] = {"http_status": r.get("http_status"),
                                   "elapsed_ms": r.get("elapsed_ms"),
                                   "message": r.get("error", "")}
    print(f"  {n:30s} HTTP {r.get('http_status')}  {r.get('elapsed_ms')}ms  "
          f"{r.get('error','')[:70]}")

tests = [
    ("get_transaction", "valid transaction", {"txn_id": TXN}),
    ("find_related_transactions", "valid transaction", {"txn_id": TXN}),
    ("find_related_transactions", "valid card", {"txn_id": "", "card_id": CARD, "customer_id": ""}),
    ("find_related_transactions", "valid customer", {"txn_id": "", "card_id": "", "customer_id": CUST}),
    ("find_device_connections", "valid transaction", {"txn_id": TXN, "device_profile_id": ""}),
    ("find_device_connections", "valid device", {"txn_id": "", "device_profile_id": DEV}),
    ("find_related_cases", "valid transaction", {"txn_id": TXN, "card_id": "", "customer_id": "",
                                                 "device_profile_id": "", "region_code": "", "domain": ""}),
    ("find_related_cases", "valid card", {"txn_id": "", "card_id": CARD, "customer_id": "",
                                          "device_profile_id": "", "region_code": "", "domain": ""}),
    ("find_related_cases", "valid customer", {"txn_id": "", "card_id": "", "customer_id": CUST,
                                              "device_profile_id": "", "region_code": "", "domain": ""}),
    ("find_related_cases", "valid device", {"txn_id": "", "card_id": "", "customer_id": "",
                                            "device_profile_id": DEV, "region_code": "", "domain": ""}),
    ("find_related_cases", "valid billing region", {"txn_id": "", "card_id": "", "customer_id": "",
                                                    "device_profile_id": "", "region_code": "444.0", "domain": ""}),
    ("find_related_cases", "valid email domain", {"txn_id": "", "card_id": "", "customer_id": "",
                                                  "device_profile_id": "", "region_code": "", "domain": DOMAIN}),
    ("benchmark_case_context", "valid benchmark HHG-001", {"case_id": "HHG-001"}),
    ("get_transaction", "invalid id", {"txn_id": "999999999"}),
    ("find_device_connections", "invalid id", {"txn_id": "NOPE", "device_profile_id": ""}),
    ("benchmark_case_context", "invalid case", {"case_id": "HHG-999"}),
    ("find_related_transactions", "empty input", {"txn_id": "", "card_id": "", "customer_id": ""}),
    ("get_transaction", "empty input", {"txn_id": ""}),
]

print()
print("=" * 70)
print("B. LIVE EXECUTION WITH REAL DATA")
print("=" * 70)
for name, label, p in tests:
    r = call(name, p)
    results["execution"][f"{name} :: {label}"] = {
        "params": p, "http_status": r.get("http_status"), "ok": r.get("ok"),
        "elapsed_ms": r.get("elapsed_ms"), "error": r.get("error", ""),
        "result_structure": r.get("result_structure", {})}
    flag = "OK " if r.get("ok") else "ERR"
    print(f"  [{flag}] {name:26s} {label:24s} HTTP {r.get('http_status')} "
          f"{r.get('elapsed_ms'):>8}ms  {str(r.get('result_structure'))[:95]}")

print()
print("=" * 70)
print("C. ALL 20 BENCHMARK CASES (BenchmarkCase -TRIGGERS-> Transaction)")
print("=" * 70)
ok_ct = 0
for row in bench:
    cid = row["case_id"]
    r = call("benchmark_case_context", {"case_id": cid})
    st = r.get("result_structure", {})
    flagged = st.get("Flagged", 0) if isinstance(st.get("Flagged", 0), int) else 0
    good = bool(r.get("ok")) and flagged == 1
    ok_ct += 1 if good else 0
    results["benchmark"].append({
        "case_id": cid, "expected_flagged_txn": row["flagged_txn_id"],
        "expected_card_id": row["card_id"], "http_status": r.get("http_status"),
        "ok": bool(r.get("ok")), "flagged_count": flagged,
        "elapsed_ms": r.get("elapsed_ms"),
        "result_structure": st})
    print(f"  {cid} HTTP {r.get('http_status')} flagged={flagged} "
          f"cases: dev={st.get('RelatedViaDevice','-')} reg={st.get('RelatedViaRegion','-')} "
          f"card={st.get('RelatedViaCard','-')} hist={st.get('CardHistory','-')} "
          f"{r.get('elapsed_ms')}ms {'OK' if good else 'FAIL'}")

print()
print(f"  BENCHMARK PASS: {ok_ct}/20")

# determinism: run twice and compare
print()
print("=" * 70)
print("DETERMINISM (two identical runs)")
print("=" * 70)
a = call("get_transaction", {"txn_id": TXN})
b = call("get_transaction", {"txn_id": TXN})
det = a.get("result_structure") == b.get("result_structure")
results["determinism"] = {"run1": a.get("result_structure"),
                          "run2": b.get("result_structure"), "equivalent": det}
print(f"  equivalent = {det}")

results["inputs_used"] = {"txn_id": TXN, "card_id": CARD, "customer_id": CUST,
                          "device_profile_id": DEV, "domain": DOMAIN, "case_id": CASE}
results["benchmark_pass_count"] = ok_ct

os.makedirs(os.path.join(ROOT, "tigergraph", "validation"), exist_ok=True)
with open(os.path.join(ROOT, "tigergraph", "validation", "phase3a_execution_raw.json"),
          "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
print("\nWROTE tigergraph/validation/phase3a_execution_raw.json")
