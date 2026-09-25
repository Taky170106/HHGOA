"""Q1 definitive read-only live check: is each query INSTALLED (callable by RESTPP)
or merely present in the catalogue as a draft?

Method: GET /query/<graph>/<name> with no parameters.
  404 -> query not installed (cannot be called)   = the Q1 condition
  400 -> installed, rejected for missing parameters
  401 -> auth required
  200 -> executed (all target queries require parameters, so this would be unexpected)

Nothing is created, dropped, installed or modified.
"""
import io, sys, json
from urllib import request as urlreq
from urllib import error as urlerr
import base64

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GRAPH = "hhg_fraud_graph"
BASE = "http://localhost:9000/query/" + GRAPH
AUTH = base64.b64encode(b"tigergraph:tigergraph").decode()

INVESTIGATION = [
    "benchmark_case_context",
    "calculate_exposure",
    "calculate_exposure_list",
    "find_device_connections",
    "find_related_cases",
    "find_related_transactions",
    "get_card_history",
    "get_customer_history",
    "get_transaction",
    "temporal_chain",
]
PHASE2 = ["count_all", "phase2_validate"]

installed, not_installed = [], []


def probe(name):
    req = urlreq.Request(BASE + "/" + name, method="GET")
    req.add_header("Authorization", "Basic " + AUTH)
    try:
        with urlreq.urlopen(req, timeout=30) as r:
            return r.status, r.read()[:120]
    except urlerr.HTTPError as e:
        return e.code, e.read()[:120]
    except Exception as e:  # noqa: BLE001
        return None, str(e)


print("=" * 76)
print("Phase 2 validation queries (control group - known installed)")
for n in PHASE2:
    code, body = probe(n)
    tag = "INSTALLED" if code not in (404, None) else "NOT_INSTALLED"
    print("  %-20s HTTP %s -> %s" % (n, code, tag))
    (installed if tag == "INSTALLED" else not_installed).append(n)

print()
print("Investigation queries (subject of Q1)")
for n in INVESTIGATION:
    code, body = probe(n)
    tag = "INSTALLED" if code not in (404, None) else "NOT_INSTALLED"
    print("  %-28s HTTP %s -> %s" % (n, code, tag))
    (installed if tag == "INSTALLED" else not_installed).append(n)

print()
print("=" * 76)
print("investigation queries INSTALLED     : %d / %d" % (
    len([n for n in installed if n in INVESTIGATION]), len(INVESTIGATION)))
print("investigation queries NOT installed : %s" %
      [n for n in not_installed if n in INVESTIGATION])
print("missing live check answered: "
      "yes - current RESTPP install state verified" if not_installed else
      "missing live check answered: all installed")

json.dump({
    "installed": installed,
    "not_installed": not_installed,
    "investigation_installed": [n for n in installed if n in INVESTIGATION],
    "investigation_not_installed": [n for n in not_installed if n in INVESTIGATION],
}, open("tigergraph/validation/q1_live_install_state.json", "w", encoding="utf-8"), indent=2)
print("wrote tigergraph/validation/q1_live_install_state.json")
