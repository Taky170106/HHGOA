# Demo Script — HHG-001 (live, reproducible)

A single command runs one real benchmark case end to end and prints every step
the agent takes. No LLM is faked, no numbers are hard-coded: every value in the
output is produced by that run.

---

## Prerequisites

1. TigerGraph container `hhg-tigergraph` running (Community Edition 4.2.5),
   graph `hhg_fraud_graph` loaded and the 10 Phase 3 GSQL queries installed.
2. Python deps: `pandas`, `numpy`, `scikit-learn`, `shap`, `langgraph`.
3. Model artifacts present: `models/fraud_model.pkl`, `models/features.json`,
   `models/evidence_weights.json`.

Check the graph is reachable:

```powershell
# should return HTTP 200 with a JSON body, not 404
Invoke-WebRequest -Uri "http://localhost:9000/query/hhg_fraud_graph/get_transaction?txn_id=3514030" `
  -Headers @{Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("tigergraph:tigergraph"))}
```

## The command

```powershell
cd D:\HHG
python scripts\demo_hhg001.py
```

Runtime: about 10 seconds (data load ~13 s, then the live queries and SHAP).

## What you will see

| Step | Title | What it proves |
|---|---|---|
| 1 | **CASE** | The agent receives HHG-001 exactly as it appears in `DATASET/case_pack.csv` (trigger, flagged txn `3514030`, card `C12382-K1`, customer `C12382`). |
| 2 | **GRAPH EVIDENCE** | Four **live, read-only** GSQL queries hit TigerGraph over RESTPP: `benchmark_case_context`, `get_transaction`, `find_related_cases`, `find_device_connections`. HTTP status and latency are printed for each. |
| 3 | **RELATIONSHIPS** | The relationships the graph actually returned — card owners, customer, device, billing region, prev/next transactions, related closed cases. Nothing is asserted that the graph did not return. |
| 4 | **RISK SCORE** | Model probability from `models/fraud_model.pkl` (32 graph/transaction features, `risk_score` excluded as leakage), then the calibrated probability from weights learned off the labeled closed-case history. Signals present/absent are listed. |
| 5 | **XAI** | SHAP `TreeExplainer` contributions for the flagged transaction, printed under **MODEL EXPLANATION**, followed separately by **GRAPH EVIDENCE**, with an explicit note that SHAP explains the model, not the graph. |
| 6 | **FINDINGS + SUMMARY** | Every evidence item with its id, class (`direct` / `derived_graph` / `model_analytical`) and claim, then pattern, verdict, probability before/after and exposure. |
| 7 | **POLICY → NEXT BEST ACTION** | `next_best_actions.initial` and `.final`, the assumed response if evidence was requested, `what_changed`, SAR required or not, and the approval route of each action. |
| 8 | **CASE RESULT** | Where the answer file landed, the graph-write status, and total wall clock. |

## Artifacts produced

```
validation/phase3_e2e.json     machine-readable record of this run
cases/HHG-001.json             the case answer for the benchmark
```

`validation/phase3_e2e.json` contains the step list, every live GSQL call with
its HTTP status and latency, the evidence ids, the model/calibrated
probabilities, both action stages, the approval routes and the graph-write
status.

## Regenerating all 20 cases

```powershell
python scripts\calibrate_evidence.py     # learn evidence weights from labels
python scripts\build_cases.py            # write all 20 answer files
python scripts\validate_cases.py         # machine validation -> cases/validation_report.json
```

## Notes

- **Read-only.** The demo never writes to TigerGraph. See
  `docs/GRAPH_WRITE_BLOCKER.md` for why the "write the case back to the graph"
  requirement is recorded as BLOCKED rather than performed.
- **No LLM is called.** There is no API key in this environment, so `tokens` is
  reported as `0` rather than invented. The reasoning steps are deterministic
  and re-runnable, which is what makes the demo reproducible.
- **Phase 2 is untouched.** The graph, schema and `DATASET/` are exactly as
  validated in Phase 2 (8 vertices, 11 edges, 2,505,266 edges).
