# Graph Write Blocker

**Status: BLOCKED (Phase 3 requirement "case written to graph" not executed)**
**Recorded under the emergency submission protocol: Phase 2 is locked and must never be corrupted.**

---

## 1. The requirement

The hackathon answer format asks the agent to write each investigated case back
into the graph so that a later investigation can retrieve it as case memory
(`DATASET/README.md`, Part 1: *"It should be written into the graph so later
investigations can find it: a case that names a merchant or a device becomes
evidence for the next analyst."*).

Every answer file therefore has to carry a graph reference, and the machine
validator checks `case.written_to_graph`, `case.graph_case_id` and the
`graph_evidence` block.

## 2. What the repository actually supports (inspected, not assumed)

Source of truth: `tigergraph/schema/schema.gsql` — **8 vertices, 11 edges**,
the exact structure validated as PASS in Phase 2.

| Candidate write target | Exists? | Usable for a new case result? |
|---|---|---|
| `BenchmarkCase` vertex (HHG-XXX) | yes | **read-only**: it stores the *trigger* only (`opened_at`, `trigger_type`, `trigger_text`, `flagged_txn_id`, `card_id`, `customer_id`, `risk_score`). No field for verdict, probability, pattern, actions or SAR. |
| `ClosedCase` vertex (CC-XXXX) | yes | **semantically wrong**: it is the *historical analyst* case table (`outcome`, `analyst_notes`, `closed_at`). A benchmark case is not a historical closed case; inserting `HHG-XXX` there would corrupt the labeled history used to train the ML model and to retrieve `similar_prior_cases`. |
| New vertex (e.g. `CaseResult`) | **no** | Requires `CREATE VERTEX` + graph recreation → schema change. |
| New edge (e.g. `RESOLVED_AS BenchmarkCase → CaseResult`) | **no** | Requires `CREATE EDGE` → schema change. |
| New edge from `BenchmarkCase → ClosedCase` | **no** | No such edge type exists in the 11 validated edges. |

## 3. Why it is blocked rather than done

1. **Phase 2 is locked.** `docs/PHASE2_VALIDATION_REPORT.md` and
   `tigergraph/validation/*` record PASS on exact counts: **8/8 vertices,
   11/11 edges, 2,505,266 edges, 0 rejected, 0 orphan, 0 duplicate IDs,
   HHG-001…HHG-020 = 20/20 connected to trigger transactions.**
2. **Any insert changes those counts.** Adding 20 case-result vertices and
   their edges makes the stored Phase 2 evidence stale on the very numbers it
   passed on. Re-validating would require re-running the whole Phase 2
   validation pass — explicitly out of scope during the emergency window and
   explicitly forbidden ("never corrupt Phase 2").
3. **Any new vertex/edge type is a schema change**, which is also forbidden
   ("DO NOT modify the Phase 2 schema", "DO NOT invent new schema during this
   emergency implementation").
4. There is therefore **no write path that satisfies both requirements at
   once**, so the honest outcome is `GRAPH_WRITE_STATUS = BLOCKED`, not a
   silently mutated graph.

No graph mutation of any kind was performed. Phase 2 evidence files were not
touched.

## 4. What the answer files carry instead

Every `cases/HHG-XXX.json` contains the graph reference needed for submission:

- `graph_evidence.single_source_of_truth` — `TigerGraph hhg_fraud_graph`
- `graph_evidence.queries` — the live GSQL query name, parameters, HTTP status
  and latency used for this case
- `graph_evidence.entities` — the resolved vertex ids by type
  (`BenchmarkCase`, `Transaction`, `Card`, `Customer`, `DeviceProfile`,
  `BillingRegion`, `EmailDomain`, `ClosedCase`)
- `graph_evidence.edges` — the exact `(edge, from, to, from_type, to_type)`
  triples returned for this case
- `graph_evidence.graph_facts` vs `graph_evidence.investigation_interpretation`
  — the GRAPH FACT / INVESTIGATION INTERPRETATION split
- `case.written_to_graph = false`, `case.graph_case_id = ""`
- `graph_write.status = "BLOCKED"` with this document referenced

## 5. Ready-to-run write path (for an authorized post-submission phase)

Once Phase 2 is unlocked and re-validated, the write is a pure `upsert` of the
**existing** `BenchmarkCase` vertex — no schema change, no new vertex, no
`ClosedCase` contamination. Two options:

**Option A — extend `BenchmarkCase` with result attributes (minimal schema delta):**

```gsql
CREATE VERTEX BenchmarkCase (
  PRIMARY_ID case_id STRING,
  opened_at DATETIME,
  trigger_type STRING,
  trigger_text STRING,
  flagged_txn_id STRING,
  card_id STRING,
  customer_id STRING,
  risk_score DOUBLE,
  /* result fields added by the agent */
  verdict STRING,            -- fraud / legitimate / uncertain
  case_status STRING,        -- open / closed_fraud / closed_legitimate / escalated
  fraud_probability DOUBLE,
  pattern STRING,
  exposure_usd DOUBLE,
  sar_filed BOOL,
  graph_case_id STRING       -- id of the written case record
) WITH primary_id_as_attribute="true"
```

**Option B — no schema change at all (pure data write):**

Upsert the agent's decision onto the `TRIGGERS` edge, which already exists
`BenchmarkCase → Transaction` and already carries `trigger_type` and
`risk_score`. Edge attributes can be added with `CREATE EDGE` … which *is* a
schema change, so Option B is only available if TigerGraph's
`upsert`-with-known-attributes is restricted to the two attributes already
present. In practice Option A is the honest recommendation.

**The write statement (Option A), for the authorized phase:**

```gsql
CREATE UPDATESERT VERTEX BenchmarkCase SET
  verdict = $verdict,
  case_status = $status,
  fraud_probability = $p,
  pattern = $pattern,
  exposure_usd = $exposure,
  sar_filed = $sar,
  graph_case_id = $graph_case_id
WHERE case_id == $case_id;
```

Then re-run the Phase 2 validator and update
`tigergraph/validation/phase2_*.json` in the same commit.

## 6. Summary

| Question | Answer |
|---|---|
| Did the agent write the case to the graph? | **No** |
| Is the requirement satisfiable without touching Phase 2? | **No** |
| Was Phase 2 schema modified? | **No** |
| Was the Phase 2 graph mutated? | **No** — zero inserts, zero updates |
| Is the graph reference present in every answer file? | **Yes** — `graph_evidence` + `graph_write` blocks |
| Is a ready-to-run write statement provided? | **Yes** — section 5 |
| Graph write status | **BLOCKED** |
