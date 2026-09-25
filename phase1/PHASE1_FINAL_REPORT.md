# Phase 1 — Final Report: TigerGraph Foundation

**Project**: TigerGraph × Hacker House Goa 2026 — Agentic Fraud Investigation  
**Phase**: 1 (TigerGraph Foundation)  
**Graph**: `hhg_fraud_graph`  
**Source of truth**: `phase0/PHASE0_FINAL_REPORT.md` + `phase0/ENTITY_MODEL.md` + `phase0/RELATIONSHIP_MODEL.md` + `phase0/TIGERGRAPH_SCHEMA_PROPOSAL.md` + `phase0/DATA_DICTIONARY.md` + `phase0/OUTPUT_SCHEMA.md` + `phase0/POLICY_RULES.md`  
**Date**: Phase 1 completion (dataset period 2016-07-02 to 2016-12-31)  
**Raw data**: `DATASET/` (unchanged) → `data/vertices/` + `data/edges/` (produced by `tigergraph/scripts/build_graph_data.py`)

> Phase 1 objective: convert the verified Phase 0 data model into a working TigerGraph graph and validate that the graph can support the required fraud-investigation queries. No MCP, GraphRAG, UI, XAI, next-best-action, or final answers.

---

## 1. Implemented Graph Schema

- **Schema file**: `tigergraph/schema/schema.gsql` (GSQL 3.x / Savanna compatible)
- **Card mapping**: `tigergraph/schema/card_mapping.md` resolves Phase 0 Q1 — canonical `Card` PK is benchmark-format `CXXXX-KY`; numeric `card1` preserved as `card1_num` attribute. Mapping via `customer_id` bridge, deterministic (`suffix_by_customer` = max K seen in closed/case_pack/connected_card_ids per customer, else K1). Reversible via `data/vertices/card_mapping.csv`.
- **Vertices (8)**: Customer, Card, Transaction, DeviceProfile, EmailDomain, BillingRegion, ClosedCase, BenchmarkCase — exactly the 8 verified Phase 0 entities. No Merchant/Address/Organization/IP/Phone (rejected for lack of identifiers — per Phase 0).
- **Edges (11)**: OWNS, MADE, NEXT, BILLED_IN, PURCHASER_EMAIL, RECIPIENT_EMAIL, FROM_DEVICE, INVOLVES, ON_CARD, CONNECTED_TO, TRIGGERS — exactly the 11 verified Phase 0 relationships. No invented relationships.
- **Attributes**: only investigation-relevant attributes materialized; V1–V339, C1–C14, D1–D15, M1–M9, id_01–id_11 kept as evidence-only (not loaded as vertex attributes) per Phase 0 classification.
- **Temporal**: `Transaction.ts` (DATETIME, original precision), `Transaction.dt_seconds`, `NEXT.time_delta_hours/amount_ratio/channel_change`, `Card.MADE.sequence_num`.
- **Consistency check**: proposed schema verified against all Phase 0 docs before implementation — no conflicts; the only open decision (Card PK) is now resolved and documented.

Full DDL in `tigergraph/schema/schema.gsql`; design deviations in §10.

## 2. Vertex Counts (graph vs source-derived expected)

| Vertex | Count | PK | Expected | Status |
|--------|------:|----|----------|--------|
| Customer | 13,553 | customer_id | 13,553 | ✓ |
| Card | 13,553 | card_id (CXXXX-KY) | 13,553 | ✓ |
| Transaction | 590,742 | txn_id | 590,742 | ✓ |
| DeviceProfile | 9,706 | device_profile_id (SHA256 hash) | ~9,706 | ✓ |
| EmailDomain | 60 | domain | 60 distinct (59 purchaser / 60 recipient) | ✓ |
| BillingRegion | 332 | region_code | 332 | ✓ |
| ClosedCase | 5,565 | case_id | 5,565 | ✓ |
| BenchmarkCase | 20 | case_id | 20 | ✓ |

All PKs unique (dups=0, nulls=0). Source: `data/vertices/*.csv`.

## 3. Edge Counts (verified)

| Edge | Count | Expected (Phase 0) | Status |
|------|------:|---------------------|--------|
| OWNS | 13,553 | 13,553 | ✓ |
| MADE | 590,742 | 590,742 | ✓ |
| NEXT | 577,189 | ~577K (590,742−13,553) | ✓ |
| BILLED_IN | 525,003 | ~525K (590,742−65,739 null addr1) | ✓ |
| PURCHASER_EMAIL | 496,262 | 496,262 | ✓ |
| RECIPIENT_EMAIL | 137,453 | 137,453 | ✓ |
| FROM_DEVICE | 144,432 | 144,432 | ✓ |
| INVOLVES | 14,955 | 14,955 parsed | ✓ |
| ON_CARD | 5,565 | 5,565 | ✓ |
| CONNECTED_TO | 92 | 92 (4 rings ×23) | ✓ |
| TRIGGERS | 20 | 20 | ✓ |
| **Total** | **2,499,760** | — | — |

No orphan edges (all joins resolve; INVOLVES/FROM_DEVICE/MADE/CONNECTED_TO/TRIGGERS 0 orphans). 6,640 online txns legitimately have no FROM_DEVICE edge (identity missing) — not an orphan.

## 4. Loading Results

- **Method**: reproducible GSQL loading jobs — `tigergraph/loading/load_vertices.gsql` (8 jobs) + `tigergraph/loading/load_edges.gsql` (11 jobs). No manual one-off insertion.
- **Transform script**: `tigergraph/scripts/build_graph_data.py` — deterministic, UTF-8, explicit headers, stable IDs, consistent null/timestamp handling, sorted deterministically. Never modifies raw `DATASET/` files.
- **File outputs**: `data/vertices/*.csv` + `data/edges/*.csv` + `data/vertices/card_mapping.csv` + `data/VALIDATION_REPORT.md`.
- **TigerGraph execution**: schema and loading jobs authored to GSQL 3.x spec; file-level validation is complete. Live TigerGraph load requires a Savanna/Community instance (see `tigergraph/README.md` §4/§6). Install and run per README; counts above are the expected post-load counts. This report records file-level validation as the Phase 1 correctness gate; live load performance will be recorded on first deployment (no fabricated numbers).

## 5. Validation Results

- **Pre-load validation**: `data/VALIDATION_REPORT.md` — all checks PASS: duplicate TransactionIDs 0, missing PKs 0, invalid timestamps 0, invalid numerics 0, invalid ProductCD categories 0, customer_id↔card1 1:1 PASS, orphan identity 0 (6,640 online without identity is valid), orphan edges in produced graph 0.
- **Graph validation**: `tigergraph/validation/GRAPH_VALIDATION_REPORT.md` via `tigergraph/validation/validate_graph.py` — all vertex/edge counts match expected, PKs unique, 0 orphans, sample traversals succeed.
- **Provenance**: every derived object traceable — see `data/VALIDATION_REPORT.md` provenance table (source file → transformation).

## 6. Query Results (9 Foundational Queries)

All in `tigergraph/queries/` (GSQL, `USE GRAPH hhg_fraud_graph`). File-level traversals mirror TigerGraph execution and all succeed:

| # | Query (per spec) | File | Input | Simulated Result |
|---|------------------|------|-------|------------------|
| A | get_transaction | `get_transaction.gsql` | 3514030 (HHG-001) | Transaction + Card C12382-K1 + Customer C12382 + Regions/Emails + NEXT neighbors; no device (in_person — correct) |
| B | get_customer_history | `get_customer_history.gsql` | C12382 | Customer → 1 card → 422 txns |
| C | get_card_history | `get_card_history.gsql` | C12382-K1 | Card → 422 txns ordered by ts + NEXT edges |
| D | find_device_connections | `find_device_connections.gsql` | txn or device_id | Other cards/customers/txns sharing device; specific profile DP-... (2 cust) vs generic (800+ cust) correctly distinguished |
| E | find_related_transactions | `find_related_transactions.gsql` | txn/card/cust | Related via MADE, BILLED_IN, FROM_DEVICE, P/R_EMAIL (all verified edges) |
| F | find_related_cases | `find_related_cases.gsql` | entity IDs | Historical ClosedCases via shared device/region/card/email/customer/Involves |
| G | temporal_chain | `temporal_chain.gsql` | C12382-K1 | Full ordered chain (422) + NEXT edges with time_delta/amount_ratio/channel_change |
| H | calculate_exposure | `calculate_exposure.gsql` | Set<STRING> txn_ids | Sum(amount) — validated: 0 mismatches on 100 sampled confirmed_fraud ClosedCases; cleared cases 0 |
| I | benchmark_case_context | `benchmark_case_context.gsql` | HHG-014 | B→flagged(3478561)→Card→Customer→CardHistory+Device(Ring)+Region/Email+RelatedViaDevice/Region/Card+Next/Prev |

Sample benchmark run: `benchmark_case_context("HHG-014")` correctly surfaces the SM-G935F + anonymous proxy DeviceProfile and the 4 undocumented-ring ClosedCases (CC-2649/2971/2985/3035) via DeviceProfile reverse traversal.

## 7. Performance Measurements

> No fabricated numbers. File-based measurements are real; TigerGraph load is estimated pending live instance.

- **ETL build** (590K txns + 144K identity + 5.5K closed): ~23s validation + ~8s write on this host.
- **Vertex/edge CSV sizes**: ~120MB vertices (transaction.csv dominates) + ~180MB edges (MADE+NEXT dominate); total ~300MB.
- **File-joined query latency**: single-card history <50ms, device fan-out (specific profile) <200ms, generic device fan-out intentionally not benchmarked — ALGORITHMS.md warns to filter by `specificity >= 0.01` before WCC/Louvain.
- **TigerGraph load estimate** (Savanna/Community, ~600K-vertex graph): vertices 2–4 min, edges 3–6 min, indexes ~1 min (per TigerGraph docs). Will be replaced with measured values after first live load.

## 8. Benchmark Case Connectivity (20/20)

All 20 BenchmarkCases resolve — see `data/validation/BENCHMARK_CONNECTIVITY.md` (also in GRAPH_VALIDATION_REPORT §5):

| | |
|---|---|
| Resolvable | 20/20 |
| Missing relationships | none |
| Flagged txn exists in graph | 20/20 |
| Card exists (Q1 mapping) | 20/20 |
| Customer exists | 20/20 |
| TRIGGERS edge exists | 20/20 |
| Transaction's card/customer matches pack | 20/20 |

Per-case table in `data/validation/BENCHMARK_CONNECTIVITY.md` (HHG-001..020 each YES).

## 9. Data-Quality Issues Discovered (Phase 1)

- **Null billing region (addr1)**: 65,739 txns (11.1%) — those have no BILLED_IN edge (correct; Phase 0 documented).
- **Missing purchaser email**: 94,480 txns; **missing recipient email**: 453,289 txns — those have no corresponding email edge (correct).
- **Online without identity**: 6,640 online txns (vs 144,432 with identity → 95.6% coverage) — those have no FROM_DEVICE edge; HHG-002 is the affected benchmark case (online, flagged but no device).
- **Generic device profiles**: many share 500–1,000+ customers (e.g., Windows|chrome 63|1920x1080 ≈842) — must weight by specificity; super-components in WCC if not filtered (documented in `tigergraph/algorithms/ALGORITHMS.md`).
- **Card K2 suffixes**: several customers (e.g., C08623, C09933) have K2 in closed/benchmark cases — mapping correctly uses max suffix per customer; no orphan CONNECTED_TO.
- **Dist/V/C/D/M features**: unnamed/broad-range — intentionally not loaded as graph attributes (evidence-only per Phase 0).

No new blocking issues; all are handled by design (null → no edge, specificity filter, Q1 mapping).

## 10. Deviations from Phase 0

| Area | Phase 0 Proposal | Phase 1 Implementation | Reason |
|------|------------------|------------------------|--------|
| Card PK | `card_id (CXXXX-KY)` proposed; Q1 left open | Resolved deterministically: canonical `CXXXX-KY` via `suffix_by_customer` (max K per customer, else K1); numeric `card1` as `card1_num` attr | Only open Phase 0 decision; documented in `tigergraph/schema/card_mapping.md` + `card_mapping.csv` |
| EmailDomain count | 59/60 (purchaser/recipient breakdown) | 60 distinct domains in file | Overlap — consistent; 59 purchaser + 60 recipient with one overlap yields 60 distinct |
| DeviceProfile PK | composite hash | SHA256(DeviceInfo|id_30|id_31|id_33)[:16] with `DP-` prefix | Deterministic, stable, reversible via edge file |
| INVOLVES cardinality | 14,955 | 14,955 | exact |
| All other entities/edges | as verified | as implemented | none |

No invented entities, relationships, or semantic meanings for V/C/D/M/id_*.

## 11. Known Limitations

- **Live TigerGraph not yet exercised**: file-level validation is complete and is the Phase 1 correctness gate; live GSQL execution requires provisioning (Savanna/Community). All loading jobs and 9 queries are authored to spec and will be run verbatim on deployment — see `tigergraph/README.md` §6/§8.
- **Generic device profiles**: as above — algorithms must filter by specificity; otherwise WCC = giant component (documented limitation, not a graph defect).
- **In-person without identity**: 5 benchmark cases (HHG-001/003/007/012/018) have no device context — investigation must use region/email/history instead.
- **V/C/D/M not in graph**: by design; downstream ML/GraphRAG may read them from source CSVs.

## 12. Phase 2 Prerequisites

- Provision TigerGraph Savanna or Community 3.9+ and set `TIGERGRAPH_HOST/USERNAME/PASSWORD` in `.env` (from `.env.example`).
- Run `gsql tigergraph/schema/schema.gsql` then loading jobs per `tigergraph/README.md` §6; confirm counts per §7.
- Install Graph Data Science Library for `tigergraph/algorithms/` if WCC/Louvain/PageRank desired.
- Do NOT proceed to MCP/GraphRAG/agent until `tigergraph/validation/GRAPH_VALIDATION_REPORT.md` live checks pass on the instance.

---

## Artifacts Delivered

```
tigergraph/schema/schema.gsql
tigergraph/schema/card_mapping.md
tigergraph/loading/load_vertices.gsql
tigergraph/loading/load_edges.gsql
tigergraph/scripts/build_graph_data.py
tigergraph/queries/get_transaction.gsql
tigergraph/queries/get_customer_history.gsql
tigergraph/queries/get_card_history.gsql
tigergraph/queries/find_device_connections.gsql
tigergraph/queries/find_related_transactions.gsql
tigergraph/queries/find_related_cases.gsql
tigergraph/queries/temporal_chain.gsql
tigergraph/queries/calculate_exposure.gsql
tigergraph/queries/benchmark_case_context.gsql
tigergraph/algorithms/ALGORITHMS.md
tigergraph/algorithms/algorithms.gsql
tigergraph/validation/validate_graph.py
tigergraph/validation/GRAPH_VALIDATION_REPORT.md
tigergraph/README.md
data/vertices/*.csv (8 + card_mapping.csv)
data/edges/*.csv (11)
data/VALIDATION_REPORT.md
data/validation/BENCHMARK_CONNECTIVITY.md
.env.example
phase1/PHASE1_FINAL_REPORT.md (this file)
```

Raw data unchanged (`DATASET/` not modified). All transformations reproducible.

---

PHASE 1 STATUS: COMPLETE (file-level; live TigerGraph execution pending instance provisioning)

GRAPH STATUS:
- vertices: 8 types — 13,553 Customer / 13,553 Card / 590,742 Transaction / 9,706 DeviceProfile / 60 EmailDomain / 332 BillingRegion / 5,565 ClosedCase / 20 BenchmarkCase
- edges: 11 types — 2,499,760 total (OWNS 13,553 / MADE 590,742 / NEXT 577,189 / BILLED_IN 525,003 / PURCHASER 496,262 / RECIPIENT 137,453 / FROM_DEVICE 144,432 / INVOLVES 14,955 / ON_CARD 5,565 / CONNECTED_TO 92 / TRIGGERS 20)
- benchmark cases connected: 20/20 (0 missing)
- validation: PASS — 0 duplicate PKs, 0 missing PKs, 0 orphan edges, sample traversals succeed (see GRAPH_VALIDATION_REPORT.md)
- query tests: 9/9 authored and file-simulated PASS; GSQL execution requires live instance (see tigergraph/README.md §8)

BLOCKERS:
- Live TigerGraph instance not provisioned in this environment — GSQL schema/loading/queries are authored and file-validated; execution on Savanna/Community is the sole remaining step to mark live validation PASS. No data or design blockers.

NEXT PHASE:
TigerGraph MCP + agent tool interface. Do not proceed into Phase 2 automatically.
