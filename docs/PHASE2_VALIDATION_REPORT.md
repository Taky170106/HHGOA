# PHASE 2 — Validation Report

**Graph:** `hhg_fraud_graph` · **Instance:** `hhg-tigergraph` (`tigergraph/community:4.2.5`, Community Edition)
**Schema:** 8 vertex types, 11 edge types — `tigergraph/schema/schema.gsql` (reused from Phase 1, not modified)
**Machine-readable result:** `docs/phase2_validation.json`

---

## 0. Validation layers — read this first

Phase 2 was validated in **two separate layers**. They are never conflated.

| Layer | What it proves | How it was run | Server required | Evidence |
|-------|----------------|----------------|-----------------|----------|
| **1. File-level** | The graph-ready CSVs in `data/` are internally consistent and match the expected baseline | `tigergraph/scripts/16_file_integrity.py` — pure file scan, **no server involved** | No | `docs/phase2_file_integrity.json` |
| **2. Live TigerGraph** | The data is actually loaded into TigerGraph and is referentially sound *inside the graph* | `RUN QUERY count_all()` and `RUN QUERY phase2_validate()` executed **inside container `hhg-tigergraph`**; plus `RUN LOADING JOB` output for rejected rows | **Yes** | `tigergraph/validation/phase2_counts.json`, `tigergraph/validation/phase2_validate_result.json`, `tigergraph/validation/phase2_load.log` |

> File-level PASS alone is **not** sufficient evidence for Phase 2. Both layers had to
> pass independently. **Both layers PASS.**

Live instance verification before loading: `gadmin status` reported **16 / 16
services `Online` / `Running`**.

---

## 1. Vertex counts — expected vs actual

### 1a. File-level layer

| Vertex | Expected | File rows | Diff | Dup PK | Empty PK | Malformed | Status |
|--------|---------:|----------:|-----:|-------:|---------:|----------:|--------|
| Customer | 13,553 | 13,553 | 0 | 0 | 0 | 0 | PASS |
| Card | 13,553 | 13,553 | 0 | 0 | 0 | 0 | PASS |
| Transaction | 590,742 | 590,742 | 0 | 0 | 0 | 0 | PASS |
| DeviceProfile | 9,706 | 9,706 | 0 | 0 | 0 | 0 | PASS |
| EmailDomain | 60 | 60 | 0 | 0 | 0 | 0 | PASS |
| BillingRegion | 332 | 332 | 0 | 0 | 0 | 0 | PASS |
| ClosedCase | 5,565 | 5,565 | 0 | 0 | 0 | 0 | PASS |
| BenchmarkCase | 20 | 20 | 0 | 0 | 0 | 0 | PASS |

**Layer 1: 8 / 8 PASS.**

### 1b. Live TigerGraph layer — `RUN QUERY count_all()`

| Vertex | Expected | **Actual (live)** | Diff | Rejected rows | Status |
|--------|---------:|------------------:|-----:|--------------:|--------|
| Customer | 13,553 | **13,553** | 0 | 0 | PASS |
| Card | 13,553 | **13,553** | 0 | 0 | PASS |
| Transaction | 590,742 | **590,742** | 0 | 0 | PASS |
| DeviceProfile | 9,706 | **9,706** | 0 | 0 | PASS |
| EmailDomain | 60 | **60** | 0 | 0 | PASS |
| BillingRegion | 332 | **332** | 0 | 0 | PASS |
| ClosedCase | 5,565 | **5,565** | 0 | 0 | PASS |
| BenchmarkCase | 20 | **20** | 0 | 0 | PASS |

**Layer 2: 8 / 8 PASS.** Live actual = file rows = expected for every type.

---

## 2. Edge counts — expected vs actual

### 2a. File-level layer (both endpoints checked against vertex PK sets)

| Edge | Source → Target | Expected | File rows | Orphan src | Orphan tgt | Dup rels | Malformed | Status |
|------|-----------------|---------:|----------:|-----------:|-----------:|---------:|----------:|--------|
| OWNS | Customer → Card | 13,553 | 13,553 | 0 | 0 | 0 | 0 | PASS |
| MADE | Card → Transaction | 590,742 | 590,742 | 0 | 0 | 0 | 0 | PASS |
| NEXT | Transaction → Transaction | 577,189 | 577,189 | 0 | 0 | 0 | 0 | PASS |
| BILLED_IN | Transaction → BillingRegion | 525,003 | 525,003 | 0 | 0 | 0 | 0 | PASS |
| PURCHASER_EMAIL | Transaction → EmailDomain | 496,262 | 496,262 | 0 | 0 | 0 | 0 | PASS |
| RECIPIENT_EMAIL | Transaction → EmailDomain | 137,453 | 137,453 | 0 | 0 | 0 | 0 | PASS |
| FROM_DEVICE | Transaction → DeviceProfile | 144,432 | 144,432 | 0 | 0 | 0 | 0 | PASS |
| INVOLVES | ClosedCase → Transaction | 14,955 | 14,955 | 0 | 0 | 0 | 0 | PASS |
| ON_CARD | ClosedCase → Card | 5,565 | 5,565 | 0 | 0 | 0 | 0 | PASS |
| CONNECTED_TO | ClosedCase → Card | 92 | 92 | 0 | 0 | 0 | 0 | PASS |
| TRIGGERS | BenchmarkCase → Transaction | 20 | 20 | 0 | 0 | 0 | 0 | PASS |

**Layer 1: 11 / 11 PASS.**

### 2b. Live TigerGraph layer — `RUN QUERY count_all()` + `RUN QUERY phase2_validate()`

| Edge | Expected | **Actual (live)** | Diff | Distinct live sources | Distinct live targets | Rejected | Status |
|------|---------:|------------------:|-----:|----------------------:|----------------------:|---------:|--------|
| OWNS | 13,553 | **13,553** | 0 | 13,553 | 13,553 | 0 | PASS |
| MADE | 590,742 | **590,742** | 0 | 13,553 | 590,742 | 0 | PASS |
| NEXT | 577,189 | **577,189** | 0 | 577,189 | 577,189 | 0 | PASS |
| BILLED_IN | 525,003 | **525,003** | 0 | 525,003 | 332 | 0 | PASS |
| PURCHASER_EMAIL | 496,262 | **496,262** | 0 | (not separately counted) | 59 of 60 domains | 0 | PASS |
| RECIPIENT_EMAIL | 137,453 | **137,453** | 0 | (not separately counted) | 60 of 60 domains | 0 | PASS |
| FROM_DEVICE | 144,432 | **144,432** | 0 | 144,432 | 9,706 | 0 | PASS |
| INVOLVES | 14,955 | **14,955** | 0 | 5,565 | 14,955 | 0 | PASS |
| ON_CARD | 5,565 | **5,565** | 0 | 5,565 | 1,892 | 0 | PASS |
| CONNECTED_TO | 92 | **92** | 0 | 4 | 24 | 0 | PASS |
| TRIGGERS | 20 | **20** | 0 | 20 | 20 | 0 | PASS |

**Layer 2: 11 / 11 PASS.**

**Edge total: 2,505,266 actual = 2,505,266 expected.**

Notes on the distinct-endpoint column (these are coverage facts, *not* defects):

- `BILLED_IN` targets = 332 → **all** BillingRegion vertices are referenced.
- `FROM_DEVICE` targets = 9,706 → **all** DeviceProfile vertices are referenced.
- `OWNS` 13,553 / 13,553 → every Customer owns exactly one Card and every Card has an owner.
- `NEXT` sources = targets = 577,189 = edge count → each source transaction has exactly
  one successor (a well-formed chain, no branching).
- `ON_CARD` targets = 1,892 distinct cards over 5,565 cases → cards legitimately shared
  across historical cases.
- `CONNECTED_TO` sources = 4 → the source data contains 4 ring-hub cases
  (`CC-2649, CC-2971, CC-2985, CC-3035`) × 23 connected cards = 92 rows, 24 distinct
  target cards. Verified identical to `data/edges/connected_to.csv`.
- `PURCHASER_EMAIL` covers 59 of 60 domains (one domain occurs only as a recipient).

> **Why live edge counts prove no orphans exist:** `count_all` counts by *traversing*
> each edge type between its two vertex types. A traversal can only happen when both
> endpoints exist as vertices in the graph. Because every live edge count equals the
> CSV row count exactly, every CSV row became a valid edge between existing vertices —
> no row was dropped for a dangling endpoint. This is independently corroborated by the
> layer-1 endpoint check (0 orphans on both sides of all 11 edge types).

### 2c. Edge total correction

| Value | Count |
|-------|------:|
| Previously published in `phase1/PHASE1_FINAL_REPORT.md`, `phase2/PHASE2_FINAL_REPORT.md`, `tigergraph/validation/GRAPH_VALIDATION_REPORT.md`, `mcp/validation/MCP_VALIDATION_REPORT.md` | 2,499,760 |
| Actual sum of the 11 edge files **and** live TigerGraph total | **2,505,266** |
| Difference | +5,506 |

The published figure was a stale arithmetic total. All 11 individual per-type counts in
those documents were already correct; only their sum was wrong. Corrected during
Phase 2 and recorded in `docs/phase2_validation.json` as `edge_total_correction`.

---

## 3. Rejected rows

Parsed from all 19 `RUN LOADING JOB` summaries in `tigergraph/validation/phase2_load.log`:

| Metric | Value |
|--------|------:|
| Loading jobs executed | 19 |
| Loading jobs reporting `LOAD SUCCESSFUL` | 19 |
| Total lines read | 3,138,797 |
| Total objects written | 3,138,797 |
| **Total rejected rows** | **0** |
| Files with `ERRORS > 0` | **none** |

**Rejected rows by file (all 19): 0.** Per-file breakdown is in
`docs/phase2_validation.json` → `integrity.rejected_rows_by_file`.

**Cross-layer reconciliation** (`tigergraph/scripts/25_verify_totals.py`):

| Source | Total rows |
|--------|-----------:|
| Loader log — sum of `LINES` across the 19 jobs | **3,138,797** |
| Loader log — sum of `OBJECTS` across the 19 jobs | **3,138,797** |
| File-level scan — 8 vertex CSVs + 11 edge CSVs | **3,138,797** |

`loader total == file-level total` → **every row in every graph CSV reached TigerGraph**.
(Vertex rows 633,531 + edge rows 2,505,266 = 3,138,797.)

---

## 4. Orphan counts

| Check | Layer 1 (file) | Layer 2 (live) | Status |
|-------|---------------:|---------------:|--------|
| Orphan edge endpoints — source side (all 11 types) | 0 | 0 | PASS |
| Orphan edge endpoints — target side (all 11 types) | 0 | 0 | PASS |
| **Total orphan edges** | **0** | **0** | PASS |
| `ClosedCase.card_id` values with no matching `Card` vertex | 0 | 0 | PASS |
| `ClosedCase.card_id` attribute ≠ its `ON_CARD` edge target | n/a | **0 of 5,565** | PASS |
| Transactions referenced by `TRIGGERS` that do not exist | 0 | 0 | PASS |

Orphan breakdown per edge type: `docs/phase2_validation.json` →
`integrity.orphan_edges_by_type` (all 11 entries = 0).

---

## 5. Duplicate IDs

| Check | Count | Status |
|-------|------:|--------|
| Duplicate primary identifiers across all 8 vertex types | **0** | PASS |
| Empty / missing primary identifiers | **0** | PASS |
| Malformed records (column count ≠ header) | **0** | PASS |
| Duplicate `from`/`to` relationships within any edge type | **0** | PASS |
| Invalid foreign identifiers | **0** | PASS |

Verified independently on both layers (layer 1 scans the files; layer 2 confirms the
graph holds exactly the same distinct counts).

---

## 6. Benchmark case connectivity (HHG-001 … HHG-020)

### 6a. File-level layer

For each case: does the `BenchmarkCase` vertex exist, does its `flagged_txn_id` exist
in `transaction.csv`, and does a `TRIGGERS` edge join them?

**20 / 20 connected.**

### 6b. Live TigerGraph layer — `RUN QUERY phase2_validate()`

| Metric | Expected | Actual (live) |
|--------|---------:|--------------:|
| `BenchmarkCase` vertices | 20 | **20** |
| `TRIGGERS` edges | 20 | **20** |
| Distinct `BenchmarkCase` sources with a `TRIGGERS` edge | 20 | **20** |
| Distinct `Transaction` targets of `TRIGGERS` | 20 | **20** |
| Cases whose triggered `Transaction.txn_id == BenchmarkCase.flagged_txn_id` | 20 | **20** |
| **Cases with NO correct trigger transaction** | **0** | **0** |

**20 / 20 connected in the live graph, 0 unmatched.**

The live check is a predicate match, not merely an edge-count match: it verifies that
each case's `TRIGGERS` edge terminates on the transaction whose `txn_id` equals that
case's own `flagged_txn_id`. Per-case detail (trigger transaction ID for each of
HHG-001…HHG-020) is in `docs/phase2_validation.json` → `benchmark_cases.cases`.

---

## 7. Integrity results

| Integrity check | Result | Status |
|-----------------|--------|--------|
| Vertex counts = expected (live) | 8 / 8 exact | PASS |
| Edge counts = expected (live) | 11 / 11 exact | PASS |
| Edge total = expected (live) | 2,505,266 = 2,505,266 | PASS |
| Rejected rows | 0 of 3,138,797 lines | PASS |
| Orphan edges | 0 | PASS |
| Duplicate IDs | 0 | PASS |
| Empty identifiers | 0 | PASS |
| Malformed records | 0 | PASS |
| Duplicate relationships | 0 | PASS |
| Count mismatches (live vs expected) | none | PASS |
| ClosedCase ↔ Card referential agreement (live) | 5,565 / 5,565 | PASS |
| All Customers own a Card (live) | 13,553 / 13,553 | PASS |
| All Cards have an owner (live) | 13,553 / 13,553 | PASS |
| All Cards have `MADE` edges (live) | 13,553 / 13,553 | PASS |
| All Transactions have a `MADE` edge (live) | 590,742 / 590,742 | PASS |
| All ClosedCases have `INVOLVES` edges (live) | 5,565 / 5,565 | PASS |
| All ClosedCases have `ON_CARD` edges (live) | 5,565 / 5,565 | PASS |
| All 20 benchmark cases connected (live) | 20 / 20 | PASS |
| `DATASET/*` raw files unmodified | SHA-256 verified; 17 / 20 graph CSVs byte-identical | PASS |
| Schema unchanged (8 vertices / 11 edges) | verified against `tigergraph/schema/schema.gsql` | PASS |
| Loading job ↔ schema ↔ CSV header alignment | 19 / 19 | PASS |

**No unexplained integrity failures.**

### 7.1 MCP layer (reported, not part of the PASS criteria)

| Mode | Result | Note |
|------|--------|------|
| `file_fallback` | **33 / 33 tests pass** | baseline; `mcp/tests/test_connection.py` → `Status: PASS (file-fallback)` |
| `tigergraph_live` connection test | **`Status: PASS (live)**` — Vertices 8/8, Edges 11/11 | `mcp/tests/test_connection.py` with `TG_HOST` set |
| `tigergraph_live` tool tests | 19 passed / 14 failed | **BLOCKER Q1**, see §8 — pre-existing, out of Phase 2 scope |

File-fallback and live results are reported separately and are never presented as one
number. MCP source files were **not** modified by Phase 2.

---

## 8. Blockers

### 8.1 Resolved in Phase 2

| ID | Blocker | Evidence before | Fix | Result |
|----|---------|-----------------|-----|--------|
| **B1** | `card2`/`card3`/`card5` = `189.0` vs schema `UINT` | 13,543 of 13,553 Cards rejected (`Valid Object: 10`) | ETL strips the float64 serialization artifact; **100 % of raw values verified integral across 590,742 rows**; schema `UINT` kept (model not changed) | Card **13,553 / 13,553**, 0 rejected |
| **B2** | `benchmark_case.trigger_text` embedded commas ignored | 11 of 20 rows rejected (column shift) | `QUOTE="double"` on loading jobs; **no data modified** | BenchmarkCase **20 / 20**, 0 rejected |
| **B3** | `closed_case.analyst_notes` truncated at first comma | 2,324 silent truncations, zero errors | `QUOTE="double"` on loading jobs; **no data modified** | ClosedCase **5,565 / 5,565**, untruncated, 0 rejected |
| **D5** | 37 `ON_CARD` orphans / 21 distinct cards | ETL never applied the documented canonical Card map | `canonical_card_id()` per `schema/card_mapping.md`; ETL reported **37 resolutions** | ON_CARD **5,565 / 5,565**, 0 orphans; live confirms 5,565 / 5,565 attribute↔edge agreement |
| **D6** | Published edge total 2,499,760 wrong | 11 individual counts summed to 2,505,266 | Recomputed and verified against live graph | **2,505,266** |

### 8.2 Open — reported, deliberately not fixed (outside Phase 2 scope)

| ID | Item | Status |
|----|------|--------|
| **Q1** | 5 of 9 files in `tigergraph/queries/*.gsql` fail to compile under TigerGraph 4.2.5: `benchmark_case_context` (line 12 col 42, syntax), `find_device_connections` (line 24 col 29, TYP-152), `find_related_cases` (line 17 col 23, TYP-111), `find_related_transactions` (line 31 col 27, syntax), `get_transaction` (line 32 col 43, syntax). **5 of 10 investigation query definitions installed** (7 queries installed in the graph in total: those 5 plus `count_all` and `phase2_validate`). | **PENDING_LIVE_EXECUTION** — these are *investigation* queries; repairing them means writing investigation logic, which the Phase 2 stop condition forbids. Exact error locations recorded in `tigergraph/scripts/23_query_errors.py` output. **Live install-state check performed** (`tigergraph/scripts/28_q1_install_state.py`, read-only RESTPP `GET /query/hhg_fraud_graph/<name>`): the same 5 return HTTP 404 = not installed, the other 5 return HTTP 200/400 = installed — evidence `tigergraph/validation/q1_live_install_state.json`. The Phase 2 live validation evidence (`count_all`, `phase2_validate`) is orthogonal and does **not** satisfy Q1. For Phase 3. |
| — | Investigation queries are not installed as a complete set; MCP live tool tests consequently report 19 passed / 14 failed. | **PENDING_LIVE_EXECUTION** — Phase 2 MCP baseline remains `file_fallback` 33/33, and the live *connection* test is `PASS (live)`. |

No blocker in §8.2 affects any Phase 2 PASS criterion (vertex counts, edge counts,
rejected rows, orphans, duplicates, benchmark connectivity, integrity).

---

## 9. Evidence index

| Evidence | Path |
|----------|------|
| Machine-readable result | `docs/phase2_validation.json` |
| File-level scan | `docs/phase2_file_integrity.json` |
| Live vertex/edge counts (`count_all`) | `tigergraph/validation/phase2_counts.json` |
| Live integrity + connectivity (`phase2_validate`) | `tigergraph/validation/phase2_validate_result.json` |
| Loader summaries (LINES / OBJECTS / ERRORS ×19) | `tigergraph/validation/phase2_load.log` |
| Change-scope hashes (before / after) | `tigergraph/validation/data_hashes_phase2_before.json`, `..._after.json` |
| Load narrative, blockers, reproduction | `docs/PHASE2_TIGERGRAPH_LOAD.md` |
| Repository map, files created/modified | `docs/PHASE2_REPOSITORY_MAP.md` |
| Phase 2A discovery (superseded readiness notes) | `docs/DATASET_DISCOVERY.md` |
| Pre-load schema/job/CSV alignment check | `tigergraph/scripts/14_schema_alignment.py` |
| File-level integrity scanner | `tigergraph/scripts/16_file_integrity.py` |
| Loader invocation (dependency order) | `tigergraph/scripts/17_phase2_load.sh` |

---

## 10. Final status

| Criterion | Result |
|-----------|--------|
| Repository verified | **PASS** |
| Schema verified (8 / 11, unchanged) | **PASS** |
| Data loaded into TigerGraph (19 / 19 jobs, live) | **PASS** |
| Vertex counts validated (8 / 8 exact, live) | **PASS** |
| Edge relationships validated (11 / 11 exact, live) | **PASS** |
| Benchmark cases connected (20 / 20, live) | **PASS** |
| Rejected rows | **0** |
| Orphan edges | **0** |
| Duplicate IDs | **0** |
| Unexplained integrity failures | **none** |
| File-level validation | **PASS** |
| Live TigerGraph validation | **PASS** |

`PHASE_2_STATUS = PASS`

### What Phase 3 may begin

The graph foundation is deployed and validated, so the next phase may start:

- repairing and installing the 5 failing investigation query files (**BLOCKER Q1**),
  after which the MCP layer can be re-run in `tigergraph_live` mode and re-validated
  against the current 33 / 33 file-fallback baseline
- the MCP tool layer working **live** against `hhg_fraud_graph` (interface already
  proven: `get_card_history` over RESTPP returns real vertex data)

Phase 3 may **not** be assumed to start GraphRAG, XAI, ML, counterfactual, policy or
Next-Best-Action work — those remain later phases per the master architecture.
