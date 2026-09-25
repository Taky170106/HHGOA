# DATASET_DISCOVERY.md -- Phase 2A Repository and Dataset Discovery

**Phase:** 2A (discovery only -- no TigerGraph schema/loading/data modification)
**Date:** 2026-09-25
**Working directory:** `D:\HHG`
**Method:** read-only inspection; full-file scans (all rows of all graph CSVs, ~146 MB), plus read-only RESTPP/GSQL queries against the running container.
**Nothing was invented.** Every number below is produced by a command in this repository and is reproducible with the scripts listed in section 11.

---

## 1. Project directory structure (actual)

```
D:\HHG
|-- AGENTS.md                     (project instructions)
|-- .env.example                  (placeholders only -- no credentials committed)
|-- README.md                     ABSENT at repo root
|-- .env                          ABSENT (nothing to gitignore yet)
|
|-- DATASET/                      <- raw benchmark source (READ ONLY, never modified)
|   |-- README.md                 (the HHGoa 2026 spec: task, policy, answer format, 20 cases)
|   |-- transactions.csv          707,936,515 B
|   |-- identity.csv               26,716,154 B
|   |-- closed_cases_history.csv   2,706,417 B
|   `-- case_pack.csv                  3,548 B
|
|-- data/                         <- GRAPH-READY output of the ETL (authoritative)
|   |-- VALIDATION_REPORT.md
|   |-- validation/BENCHMARK_CONNECTIVITY.md
|   |-- vertices/   9 CSV,  74.7 MB
|   `-- edges/     11 CSV,  71.1 MB
|
|-- data_export/                  <- STALE copy (see D6) -- 8 vertex + 11 edge CSV
|   |-- vertices/   8 CSV,  74.4 MB   (card_mapping.csv missing)
|   `-- edges/     11 CSV,  71.1 MB
|
|-- tigergraph/                   <- schema, loading jobs, 9 queries, algorithms, validation
|   |-- schema/schema.gsql, schema/card_mapping.md
|   |-- loading/load_vertices.gsql, loading/load_edges.gsql
|   |-- queries/*.gsql            (9 investigation queries)
|   |-- algorithms/algorithms.gsql
|   |-- validation/count_all.gsql, validate_graph.py, GRAPH_VALIDATION_REPORT.md
|   `-- scripts/build_graph_data.py (the ETL) + diagnostic scripts
|
|-- mcp/                          <- Phase 2 controlled tool layer
|   |-- __init__.py, README.md, .env.example
|   |-- config/tool_policy.yaml
|   |-- schemas/tool_schemas.py
|   |-- tools/  (7 files), tests/ (4 files)
|
|-- phase0/  phase1/  phase2/     <- prior-phase reports
|-- validation/
|
|-- [stray artifacts, NOT project source]
|   |-- blobs/                    4,734.1 MB (16 files)  OCI image layout
|   |-- tigergraph-4.2.5-community/  2,014.0 MB (44 files) extracted installer
|   |-- index.json, manifest.json, oci-layout, repositories   OCI layout files
|   |-- DockerDesktopWSL/         (empty)
|   |-- phase0_analysis.py, validate_edges.py, validate_exposure.py,
|   |   validate_exposure2.py, validate_gsql_policy_schema.py
|   `-- .pytest_cache/
```

### Targeted location checks

| Target | Status | Evidence |
|---|---|---|
| `DATASET/` | **PRESENT** | 4 CSV + README.md, 737.4 MB |
| `data/` | **PRESENT** | vertices (9) + edges (11) + 2 reports |
| `cases/` | **ABSENT** | -- |
| `scripts/` | **ABSENT** | (ETL lives in `tigergraph/scripts/`) |
| `graph/GSQL files` | **PRESENT** | 14 `*.gsql` under `tigergraph/` |
| `existing MCP code` | **PRESENT** | `mcp/` (Phase 2 tool layer, 12 source files) |
| `existing TigerGraph config` | **PRESENT** | `mcp/config/tool_policy.yaml`, `mcp/.env.example`, `.env.example` |
| `README` (root) | **ABSENT** | root has `AGENTS.md` only; `tigergraph/README.md` + `mcp/README.md` + `DATASET/README.md` exist |
| `case_pack.csv` | **PRESENT** | `DATASET/case_pack.csv`, 3,548 B, 20 rows x 8 cols |

### Graph-ready CSV location (exact)

**Authoritative graph-ready set: `data/vertices/*.csv` (9 files) and `data/edges/*.csv` (11 files).**
`data_export/` is a stale staging copy and must not be used as a load source (discrepancy D6).

### GSQL file inventory (14)

`schema/schema.gsql`, `loading/load_vertices.gsql`, `loading/load_edges.gsql`,
`queries/{benchmark_case_context, calculate_exposure, find_device_connections, find_related_cases,
find_related_transactions, get_card_history, get_customer_history, get_transaction, temporal_chain}.gsql`,
`algorithms/algorithms.gsql`, `validation/count_all.gsql`.

---

## 2. Actual file inventory (exact filenames, sizes, rows)

### 2.1 Raw source (`DATASET/`)

| File | Bytes | Rows | Cols |
|---|---:|---:|---:|
| `transactions.csv` | 707,936,515 | 590,742 | 397 |
| `identity.csv` | 26,716,154 | 144,432 | 41 |
| `closed_cases_history.csv` | 2,706,417 | 5,565 | 15 |
| `case_pack.csv` | 3,548 | 20 | 8 |

397 = 393 original Vesta columns + `customer_id`, `ts`, `channel`, `risk_score` (matches `DATASET/README.md`, "Files in this folder": *"all 393 original Vesta columns plus `customer_id`, `ts`, `channel`, `risk_score`"*).
41 = all 41 identity columns as stated by `DATASET/README.md` (*"144,432 identity records, all 41 original columns"*): `TransactionID`, `id_01`..`id_38`, `DeviceType`, `DeviceInfo`. Joins `transactions.csv` on `TransactionID`.

### 2.2 Graph-ready vertices (`data/vertices/`, 9 files)

| File | Rows | Cols | Primary key |
|---|---:|---:|---|
| `benchmark_case.csv` | 20 | 8 | `case_id` (HHG-001..HHG-020) |
| `billing_region.csv` | 332 | 6 | `region_code` |
| `card.csv` | 13,553 | 8 | `card_id` (CXXXX-KY) |
| `card_mapping.csv` | 13,553 | 3 | `card_id` (mapping table, **not** a graph vertex) |
| `closed_case.csv` | 5,565 | 15 | `case_id` (CC-0001..CC-5565) |
| `customer.csv` | 13,553 | 9 | `customer_id` (C00001..C13553) |
| `device_profile.csv` | 9,706 | 10 | `device_profile_id` |
| `email_domain.csv` | 60 | 5 | `domain` |
| `transaction.csv` | 590,742 | 17 | `txn_id` (string of `TransactionID`) |

**PK uniqueness: all 9 files -> duplicate PK = 0** (full-file scan).

### 2.3 Graph-ready edges (`data/edges/`, 11 files)

| File | Rows | Cols | Endpoints | Orphans |
|---|---:|---:|---|---:|
| `billed_in.csv` | 525,003 | 4 | txn -> region | 0 |
| `connected_to.csv` | 92 | 3 | case -> card | 0 |
| `from_device.csv` | 144,432 | 6 | txn -> device | 0 |
| `involves.csv` | 14,955 | 4 | case -> txn | 0 |
| `made.csv` | 590,742 | 3 | card -> txn | 0 |
| `next.csv` | 577,189 | 5 | txn -> txn | 0 |
| `on_card.csv` | 5,565 | 2 | case -> card | **37** |
| `owns.csv` | 13,553 | 2 | customer -> card | 0 |
| `purchaser_email.csv` | 496,262 | 2 | txn -> domain | 0 |
| `recipient_email.csv` | 137,453 | 2 | txn -> domain | 0 |
| `triggers.csv` | 20 | 4 | case -> txn | 0 |
| **SUM** | **2,505,266** | | | **37** |

### 2.4 CSV totals by directory

| Directory | Files | Size |
|---|---:|---:|
| `DATASET` | 4 | 737.4 MB |
| `data/vertices` | 9 | 74.7 MB |
| `data/edges` | 11 | 71.1 MB |
| `data_export/vertices` | 8 | 74.4 MB |
| `data_export/edges` | 11 | 71.1 MB |
| **Total** | **43 CSV** | |

---

## 3. Actual schemas (full-file scan, every row)

Types below are inferred from **all** rows: `int` = pure integer string, `float` = contains a decimal point, `str` = non-numeric, `empty` = blank cell count.

### 3.1 Vertices

**`benchmark_case.csv` (20 x 8)**
`case_id` str, `opened_at` datetime `YYYY-MM-DD HH:MM:SS`, `trigger_type` str (`risk_score`=11, `customer_report`=8, `analyst_request`=1), `trigger_text` str, `flagged_txn_id` str(int), `card_id` str, `customer_id` str, `risk_score` float (`-1.0` sentinel for the 9 non-model triggers).
**11 rows contain a comma inside `trigger_text`, which is quoted per RFC-4180.**

**`billing_region.csv` (332 x 6)**
`region_code` str (`100.0` style -- consistent across all three region files), `country_code` str, `is_home_region` bool (`True`/`False`), `customer_count` int, `card_count` int, `txn_count` int. Nulls: none.

**`card.csv` (13,553 x 8)**
`card_id` str, `card1_num` **int (100%)**, `customer_id` str, `card4` str (20 empty), `card6` str (11 empty),
`card2` **float-like in 13,240 rows**, empty in 313;
`card3` **float-like in 13,543 rows**, empty in 10;
`card5` **float-like in 13,423 rows**, empty in 130.
=> 13,543 of 13,553 rows carry at least one `189.0`-style value in a column the schema declares `UINT`.

**`card_mapping.csv` (13,553 x 3)** `card_id`, `card1_num`, `customer_id` -- join helper, not loaded as a vertex.

**`closed_case.csv` (5,565 x 15)**
`case_id` str, `customer_id` str, `card_id` str, `opened_at`/`closed_at` datetime, `outcome` str (`confirmed_fraud` 4,665 / `cleared` 900), `pattern` str, `first_fraud_txn_id` str (**900 empty**), `txn_ids` str (pipe-joined), `n_txns` int, `exposure_usd` float, `connected_card_ids` str (**5,561 empty**), `actions_taken` str (pipe-joined), `report_filed` bool, `analyst_notes` str.
**`analyst_notes` is column 15 of 15 (last) and contains a comma in 2,324 rows.** No column is float-in-UINT.

**`customer.csv` (13,553 x 9)**
`customer_id` str, `total_txns`/`online_txns`/`in_person_txns`/`region_count` int, `avg_amount`/`max_amount` float, `first_ts`/`last_ts` datetime. Nulls: none.

**`device_profile.csv` (9,706 x 10)**
`device_profile_id` str, `device_type` str, `device_info` str (270 empty), `os` str (4,294 empty), `browser` str (61 empty), `screen` str (4,631 empty), `customer_count`/`card_count`/`txn_count` int, `specificity` float.

**`email_domain.csv` (60 x 5)**
`domain` str, `domain_type` str, `customer_count`/`card_count`/`txn_count` int. Nulls: none.

**`transaction.csv` (590,742 x 17)**
`txn_id` str, `txn_num` int, `customer_id` str, `card_id` str, `card1_num` int, `ts` datetime, `dt_seconds` int, `amount` float, `product_cd` str, `channel` str, `risk_score` float, `addr1` str (**65,739 empty**), `addr2` str (65,739 empty), `dist1` float (352,473 empty), `dist2` float (553,086 empty), `p_emaildomain` str (94,480 empty), `r_emaildomain` str (453,289 empty).

### 3.2 Edges

All 11 edge CSVs are fully typed; declared-`UINT` columns were scanned:
`made.sequence_num` (590,742) -- 0 float-like, 0 empty; `involves.sequence_in_case` (14,955) -- 0 float-like, 0 empty.
Booleans appear as `True`/`False` (`next.channel_change`, `billed_in.is_home_country`, `involves.is_first_fraud`).
**No edge CSV contains a comma in any column.**

### 3.3 Line endings (latent risk, measured)

**Every graph CSV is CRLF** (`\r\n`), e.g. `transaction.csv` 1,772 CRLF in the first 200 KB, `benchmark_case.csv` 21 CRLF / 21 LF. This is `pandas.to_csv` on Windows. Measured effect: **none** -- see D7.

---

## 4. Relationships between entities (actual, verified)

```
Customer 1 -- 1 Card              OWNS             13,553   (0 orphans)
Card     1 -- * Transaction       MADE            590,742   (0 orphans)
Card     1 -- * Transaction       NEXT            577,189   (0 orphans, per-card temporal chain)
Transaction * -- 1 BillingRegion  BILLED_IN       525,003   (0 orphans)
Transaction * -- 1 EmailDomain    PURCHASER_EMAIL 496,262   (0 orphans)
Transaction * -- 1 EmailDomain    RECIPIENT_EMAIL 137,453   (0 orphans)
Transaction * -- 1 DeviceProfile  FROM_DEVICE     144,432   (0 orphans, online only)
ClosedCase * -- * Transaction     INVOLVES         14,955   (0 orphans)
ClosedCase * -- 1 Card            ON_CARD           5,565   (37 ORPHANS -> D5)
ClosedCase * -- * Card            CONNECTED_TO        92   (0 orphans)
BenchmarkCase * -- 1 Transaction  TRIGGERS           20   (0 orphans)
```

Referential integrity, full-file scan of every endpoint against its target PK set:

- **Only `on_card.to_card_id` has orphans: 37 rows, 21 distinct `card_id` values, 37 distinct `ClosedCase`.**
- All 20 `BenchmarkCase` rows have **0 broken references** (card, customer and flagged txn all resolve).
- `triggers.csv`: 0 orphan `from_case_id`, 0 orphan `to_txn_id`.
- 37 `closed_case.card_id` *attribute* values are the same dangling cards (sample `CC-0338 -> C02231-K1`).

---

## 5. Proposed vertex mapping (source -> graph)

| Vertex | PK | Source file | Source key | Derivation | Load result (observed) |
|---|---|---|---|---|---|
| `Customer` | `customer_id` | `transactions.csv` | `customer_id` (added col) | groupby aggregate | 13,553 / 13,553 OK |
| `Card` | `card_id` | `transactions.csv` + `closed_cases_history.csv` + `case_pack.csv` | `card1` + `customer_id` + suffix | canonical CXXXX-KY (max K per customer, see `card_mapping.md`) | **10 / 13,553** (D2) |
| `Transaction` | `txn_id` | `transactions.csv` | `TransactionID` | direct + card join via `customer_id` | 590,742 / 590,742 OK |
| `DeviceProfile` | `device_profile_id` | `identity.csv` | `DeviceInfo`,`id_30`,`id_31`,`id_33` | SHA256 composite[:16] | 9,706 / 9,706 OK |
| `EmailDomain` | `domain` | `transactions.csv` | `P_emaildomain`,`R_emaildomain` | distinct + counts | 60 / 60 OK |
| `BillingRegion` | `region_code` | `transactions.csv` | `addr1` | distinct + mode `addr2` | 332 / 332 OK |
| `ClosedCase` | `case_id` | `closed_cases_history.csv` | `case_id` | direct (values only; `txn_ids`/`connected_card_ids` split to edges) | 5,565 / 5,565 loaded, but `analyst_notes` **silently truncated** (D4) |
| `BenchmarkCase` | `case_id` | `case_pack.csv` | `case_id` | direct | **9 / 20** (D3) |

`card_mapping.csv` is a join helper only -- it is **not** one of the 8 vertex types and is correctly excluded from loading.

## 6. Proposed edge mapping (source -> graph)

| Edge | FROM -> TO | Source | Derivation |
|---|---|---|---|
| `OWNS` | Customer -> Card | `transactions.csv` (aggregated) | one owner per canonical card |
| `MADE` | Card -> Transaction | `transactions.csv` | per-card chronological `sequence_num` |
| `NEXT` | Transaction -> Transaction | `transactions.csv` | next txn on same card; `time_delta_hours`, `amount_ratio`, `channel_change` |
| `BILLED_IN` | Transaction -> BillingRegion | `transactions.csv.addr1` | `addr1` present and non-NaN only; `is_home_country` = `addr2 == 87` |
| `PURCHASER_EMAIL` | Transaction -> EmailDomain | `transactions.csv.P_emaildomain` | non-empty only |
| `RECIPIENT_EMAIL` | Transaction -> EmailDomain | `transactions.csv.R_emaildomain` | non-empty only |
| `FROM_DEVICE` | Transaction -> DeviceProfile | `identity.csv` | online txns with identity record (144,432; 6,640 online txns legitimately have none) |
| `INVOLVES` | ClosedCase -> Transaction | `closed_cases_history.csv.txn_ids` | pipe-split; `is_first_fraud` marks `first_fraud_txn_id`; `sequence_in_case` |
| `ON_CARD` | ClosedCase -> Card | `closed_cases_history.csv.card_id` | direct |
| `CONNECTED_TO` | ClosedCase -> Card | `closed_cases_history.csv.connected_card_ids` | pipe-split (92 rows; 4 cases, 24 cards) |
| `TRIGGERS` | BenchmarkCase -> Transaction | `case_pack.csv.flagged_txn_id` | carries `trigger_type`, `risk_score` |

### Comparison with the spec's "Suggested graph schema" (`DATASET/README.md`)

Spec lists **7 vertices** (`Customer`, `Card`, `Transaction`, `DeviceProfile`, `EmailDomain`, `BillingRegion`, `ClosedCase`) and **8 edges** (`OWNS`, `MADE`, `FROM_DEVICE`, `PURCHASER_EMAIL`, `BILLED_IN`, `NEXT`, `INVOLVES`, `ON_CARD`, `CONNECTED_TO`).

Our 8 vertices / 11 edges is a **superset**:
+ `BenchmarkCase` vertex (required -- the 20 exam cases and their triggers must live in the graph),
+ `RECIPIENT_EMAIL` (from `R_emaildomain`),
+ `TRIGGERS` (BenchmarkCase -> Transaction, carries the trigger that starts every investigation).
No entity or relationship was removed, renamed or invented.

---

## 7. What `data/VALIDATION_REPORT.md` actually validates

**It does validate (evidence in the file):**
- Raw source counts: `transactions` 590,742 x 397, `identity` 144,432, `closed` 5,565, `pack` 20.
- Expected vertex counts (8 types) and expected edge counts (11 types).
- `Duplicate TransactionIDs: PASS (0)`; `Missing PKs (customer_id/card1): PASS`.
- `Invalid timestamps: PASS`; `Invalid categories (ProductCD): PASS`.
- `Orphan identity records: 0` (and explains 6,640 online txns without identity are valid).
- `customer_id <-> card1 1:1: PASS (13,553 each)`.
- `Orphan edges in produced graph: PASS (0)`.
- Null/timestamp/numeric/encoding handling notes, and a **provenance table** (graph object -> source file -> source identifier -> transformation).

**It does NOT validate (gaps confirmed in this discovery):**
1. **GSQL type conformity.** It never checks whether a declared `UINT` column contains `189.0`. That is D2 and it silently rejects 13,543 Card rows.
2. **Delimiter/quoting safety.** It never checks whether a value contains the separator inside a non-last column. That is D3/D4.
3. **All edges.** `check_orphans()` in `tigergraph/scripts/build_graph_data.py:363-390` only tests `MADE` (both ends), `INVOLVES.to_txn`, `CONNECTED_TO.to_card`, `FROM_DEVICE.to_profile`. It never tests `ON_CARD`, `OWNS`, `NEXT`, `BILLED_IN`, `PURCHASER_EMAIL`, `RECIPIENT_EMAIL`, `TRIGGERS`. Hence the `PASS (0)` claim while `ON_CARD` has 37 orphans (D5).
4. **The loaded graph.** It validates CSV files only, never the counts inside TigerGraph.
5. **Cross-copy freshness.** It says nothing about `data_export/` (D6).
6. **Total edge arithmetic.** Per-type edge counts are correct; the printed total is not (D1).

---

## 8. Expected vs actual

### 8.1 Vertex types

| Vertex | Expected | CSV rows (actual) | In `schema.gsql` | Loaded in graph (observed) |
|---|---:|---:|:-:|---:|
| Customer | 13,553 | 13,553 | YES | 13,553 |
| Card | 13,553 | 13,553 | YES | **10** |
| Transaction | 590,742 | 590,742 | YES | 590,742 |
| DeviceProfile | 9,706 | 9,706 | YES | 9,706 |
| EmailDomain | 60 | 60 | YES | 60 |
| BillingRegion | 332 | 332 | YES | 332 |
| ClosedCase | 5,565 | 5,565 | YES | 5,565 |
| BenchmarkCase | 20 | 20 | YES | **9** |

**8/8 vertex types present; all 8 expected CSV counts match exactly.**

### 8.2 Edge types

| Edge | Expected | CSV rows (actual) | In `schema.gsql` | Loaded in graph |
|---|---:|---:|:-:|---:|
| OWNS | 13,553 | 13,553 | YES | 0 |
| MADE | 590,742 | 590,742 | YES | 0 |
| NEXT | 577,189 | 577,189 | YES | 0 |
| BILLED_IN | 525,003 | 525,003 | YES | 0 |
| PURCHASER_EMAIL | 496,262 | 496,262 | YES | 0 |
| RECIPIENT_EMAIL | 137,453 | 137,453 | YES | 0 |
| FROM_DEVICE | 144,432 | 144,432 | YES | 0 |
| INVOLVES | 14,955 | 14,955 | YES | 0 |
| ON_CARD | 5,565 | 5,565 | YES | 0 |
| CONNECTED_TO | 92 | 92 | YES | 0 |
| TRIGGERS | 20 | 20 | YES | 0 |
| **SUM** | **2,499,760 (docs)** | **2,505,266** | 11/11 | **0** |

**11/11 edge types present; every per-type row count matches the documented expectation exactly.**
Edge loading jobs have **not been created yet** -- hence 0 edges in the graph (by design; loading is a later phase).

---

## 9. Live TigerGraph state (observed only -- NOT modified in Phase 2A)

| Check | Result |
|---|---|
| Container | `hhg-tigergraph`, image `tigergraph/community:4.2.5`, **Up** |
| Ports | `0.0.0.0:9000->9000` (RESTPP), `14240->14240` (GraphStudio), `14022->22` (SSH) |
| RESTPP | `GET /echo` -> 200 `{"error":false,"message":"Hello GSQL"}` |
| GraphStudio | `GET /` -> 200 |
| gsql | `GSQL version 4.2.5`, Edition **Community**, commit `b7e492bd40b45153ee2a8758b03183b50ebb6eca` (2026-08-18) |
| Graph catalog | `hhg_fraud_graph`: **8 vertex types + 11 edge types** (matches `schema.gsql`) |
| Loading jobs created | 8 vertex jobs (`load_customer`, `load_card`, `load_transaction`, `load_device_profile`, `load_email_domain`, `load_billing_region`, `load_closed_case`, `load_benchmark_case`). **Edge jobs: 0 -- not created yet.** |
| Validation query | `count_all()` installed and run (read-only) |
| Credentials | gsql authenticates as local `tigergraph` inside the container; **no credential is committed anywhere in the repo** (`.env` absent, `.env.example` holds placeholders only) |

`count_all()` result (observed):

```json
{"@@c_customer":13553,"@@c_card":10,"@@c_txn":590742,"@@c_device":9706,
 "@@c_email":60,"@@c_region":332,"@@c_closed":5565,"@@c_bench":9}
{"@@e_owns":0,"@@e_made":0,"@@e_next":0,"@@e_billed":0,"@@e_purch":0,
 "@@e_recip":0,"@@e_dev":0,"@@e_inv":0,"@@e_oncard":0,"@@e_conn":0,"@@e_trig":0}
```

Loader `summary` files (`/home/tigergraph/tigergraph/log/fileLoader/*/summary`):

| Job | Tokenized | Invalid Attributes | Valid Object |
|---|---:|---:|---:|
| `load_billing_region` | 332 | 0 | 332 |
| `load_closed_case` | 5,565 | 0 | 5,565 |
| `load_card` | 13,553 | **13,543** | **10** |
| `load_benchmark_case` | 20 | **11** | **9** |
| `load_email_domain` | 60 | 0 | 60 |
| `load_customer` | 13,553 | 0 | 13,553 |
| `load_device_profile` | 9,706 | 0 | 9,706 |
| `load_transaction` | 590,742 | 0 | 590,742 |

---

## 10. Discrepancies (exact evidence)

### D1 -- Documented total edge count is wrong (arithmetic error)
Per-type counts in `phase1/PHASE1_FINAL_REPORT.md:56,193`, `tigergraph/validation/GRAPH_VALIDATION_REPORT.md:37`, `phase2/PHASE2_FINAL_REPORT.md:4`, `mcp/validation/MCP_VALIDATION_REPORT.md:4` say **2,499,760**. The 11 individual counts they list sum to **2,505,266**. Every individual count matches the actual file. Diff = **5,506**.
**The CSVs are right; the published total is wrong.**

### D2 -- `card.csv`: float values in `UINT` columns -> 13,543 of 13,553 Card rows rejected
- Schema (`schema.gsql:28-30`): `card2 UINT, card3 UINT, card5 UINT`.
- Actual: `card2` float-like 13,240, `card3` float-like 13,543, `card5` float-like 13,423; **rows with at least one float-like = 13,543**.
- Loader reported `Invalid Attributes: 13543`, `Valid Object: 10`.
- **Exact match.** Root cause is upstream: in `DATASET/transactions.csv` these columns are float64 (`card2` float 581,806 / `card3` 589,177 / `card5` 586,483 of 590,742 rows) because of NaNs, so pandas wrote `189.0`.
- Verified against the live graph: the 10 loaded `Card` IDs are **exactly** the 10 CSV rows where all three numerics are empty (`C01675-K1, C02026-K1, C03544-K1, C03883-K1, C05947-K1, C06707-K1, C09866-K1, C11774-K1, C11971-K1, C13531-K1`) -- `EXACT MATCH: True`.

### D3 -- `benchmark_case.csv`: comma inside a non-last column -> 11 of 20 cases rejected
- `trigger_text` is column **index 3 of 8** and contains `,` in **11 rows**, quoted per RFC-4180 (raw bytes confirmed: `HHG-001,...,"Real-time model scored transaction 3514030 ($77.07, in billing region 444.0) at 0.61. ...",3514030,...`).
- The loader aligned the columns positionally **without honouring the quotes**, so `risk_score` received `C12382` instead of `0.61` -> "Invalid Attribute" on `risk_score`.
- Loader reported `Invalid Attributes: 11`; rows containing `,` = **11**. Exact match.
- Verified against the live graph: loaded set = `{HHG-003, HHG-004, HHG-006, HHG-008, HHG-009, HHG-011, HHG-014, HHG-016, HHG-018}` = exactly the 9 rows **without** a comma; `HHG-001` absent. Prediction and observation are identical.

### D4 -- `closed_case.analyst_notes` is SILENTLY TRUNCATED (worse than D3: no error)
- `analyst_notes` is the **last** column (index 14 of 15) and contains `,` in **2,324 rows**.
- Same quote-ignoring behaviour, but because it is the last column the overflow falls past the mapped fields instead of shifting types -> **no error is raised**, the value is simply cut at the first comma.
- Evidence (`CC-0002`): CSV length **335** chars, graph length **247** chars. CSV tail `...had no history in, while the cardholder retained the card. Card blocked and reissued. Customer reimbursed.` Graph tail `...had no history in`.
- Silent loss of analyst narrative on 2,324 of 5,565 closed cases -- these narratives are the investigation evidence GraphRAG is supposed to retrieve.

### D5 -- `on_card.csv`: 37 orphan endpoints (21 distinct cards) + 37 dangling `ClosedCase.card_id`
- `on_card.to_card_id` not in `card.csv`: **37 rows, 21 distinct cards** (e.g. `C02231-K1` x16, `C03773-K1` x2, 19 others x1), across 37 `ClosedCase`.
- Cause: the canonical-card rule materialises only the **max suffix** per customer (e.g. customer `C02231` -> only `C02231-K2` exists), while `closed_cases_history.card_id` keeps the original `K1`/`K2` per case. Those customers **do** exist in `customer.csv` (0 missing), and their transactions all exist.
- The same 37 `closed_case.card_id` attribute values are dangling.
- `data/VALIDATION_REPORT.md` claims `Orphan edges in produced graph: PASS (0)` because `check_orphans()` never tests `ON_CARD` (see section 7.3).

### D6 -- `data_export/` is stale and incomplete
Hash comparison vs `data/`:
- `vertices/closed_case.csv` **DIFFER**, `edges/involves.csv` **DIFFER** (both are pre-fix copies),
- `vertices/card_mapping.csv` **MISSING**,
- other 17 files identical.
`data_export/` must not be used as a load source.

### D7 -- CRLF line endings in every graph CSV (measured: harmless)
All 20 graph CSVs use `\r\n` (pandas on Windows). The loading jobs use `EOL="\n"`.
Measured effect: **none** -- `Customer.last_ts` (last column, `DATETIME`) loaded as `2016-07-22 13:29:56` for 13,553/13,553 rows, and a transaction whose last column `r_emaildomain` is non-empty round-trips exactly (`anonymous.com`, no `\r` artefact). Recorded as a portability risk, not a current defect.

### D8 -- GSQL files were silently non-executable until normalized (fixed before Phase 2A)
TigerGraph CE 4.2.5 `gsql` **file mode executes nothing at all -- no output, exit 0, no graph** -- when any non-ASCII byte appears anywhere in the file, including inside `//` comments. 13 of 14 `.gsql` files contained em-dashes (`U+2014`). `tigergraph/scripts/ascii_normalize_gsql.py` rewrote comment text only (statements untouched); all `.gsql` files are now ASCII-only. This was a **comment-only** change with no semantic effect.

### D9 -- `first_fraud_txn_id` float artifact (already corrected before Phase 2A)
The source column is float64 (900 NaN), so `closed_case.first_fraud_txn_id` was written as `3000120.0` while `Transaction.txn_id` is `3000120` -- an impossible join, and it left `involves.is_first_fraud` `False` on all 14,955 rows. The ETL (`build_graph_data.py`) was corrected and re-run; hash comparison proved **exactly 2 files changed** (`vertices/closed_case.csv`, `edges/involves.csv`) and 18 of 20 byte-identical. Post-fix: `is_first_fraud` = `True` 4,665 / `False` 10,290, matching the 4,665 `confirmed_fraud` cases; all row counts unchanged. **This is why `data_export/` is stale (D6).**

---

## 11. Reproduction

| Evidence | Command |
|---|---|
| Structure / CSV inventory / target checks | PowerShell `Get-ChildItem`, Python `os.walk` counts |
| Row counts, PK uniqueness, FK orphans, types | `python tigergraph/scripts/discover_scan.py` -> `tigergraph/validation/discovery_scan.json` |
| Float-in-`UINT` diagnosis | `python tigergraph/scripts/09_diagnose_invalid_attrs.py` |
| Comma column position | `python tigergraph/scripts/11_comma_position.py` |
| GSQL ASCII normalization | `python tigergraph/scripts/ascii_normalize_gsql.py` |
| File hashes / staleness | `python tigergraph/scripts/hash_data.py` |
| Loader valid/invalid counts | `docker exec hhg-tigergraph bash /tmp/10.sh` (`10_loader_summaries.sh`) |
| Live graph counts | `docker exec hhg-tigergraph bash /tmp/07b.sh` (`count_all()`, read-only) |
| Live vertex round-trip | `GET http://localhost:9000/graph/hhg_fraud_graph/vertices/...` (read-only) |

**Files created during Phase 2A (all read-only diagnostics):**
`docs/DATASET_DISCOVERY.md`, `tigergraph/scripts/09_diagnose_invalid_attrs.py`,
`tigergraph/scripts/10_loader_summaries.sh`, `tigergraph/scripts/11_comma_position.py`.

**Files NOT modified in Phase 2A:** no CSV, no `.gsql`, no schema, no loading job, no MCP code, nothing in `DATASET/`.

---

## 12. DISCOVERY_STATUS

### DISCOVERY_STATUS = **PASS**

**Why PASS:**
1. All 9 discovery tasks were executed end to end: structure, CSV inventory, target-location checks, graph-ready identification, header + row previews, type/PK/FK derivation by **full-file scan of every row** (~146 MB), validation-report analysis, expected-vs-actual comparison, and this report.
2. The authoritative graph-ready set was identified unambiguously (`data/vertices` + `data/edges`), and `data_export/` was proven stale by hash.
3. All **8 vertex types** and **all 11 edge types** exist, and **every documented per-type count matches the actual files exactly** (13,553 / 13,553 / 590,742 / 9,706 / 60 / 332 / 5,565 / 20 and the 11 edge counts).
4. Every discrepancy is documented with reproducible, file-level evidence rather than assertion: 9 discrepancies (D1-D9), each traced to a measured root cause, including two exact numeric matches (13,543 and 11) and an exact set match (the 9 surviving `BenchmarkCase` IDs).
5. Nothing was invented: no schema, column, type, relationship, path or credential was assumed -- every claim above comes from reading the actual files or the actual running instance.
6. No implementation was performed: no schema/loading/data modification in this phase.

**Why it is not a clean bill of health (separate gate):**

### GRAPH_LOAD_READINESS = **FAIL** (3 blockers)

- **B1 (D2):** 13,543 of 13,553 `Card` rows cannot load as declared -- `UINT` columns hold `189.0`. Only 10 Card vertices exist.
- **B2 (D3):** 11 of 20 `BenchmarkCase` rows cannot load -- a comma inside non-last `trigger_text` shifts columns because the loader ignores RFC-4180 quotes. Only 9 exam cases exist in the graph.
- **B3 (D4):** `analyst_notes` is silently truncated at the first comma on 2,324 closed cases -- undetected evidence loss.
- Secondary: 37 `ON_CARD` orphans (D5) will be rejected or dangle once edges are loaded; published edge total must be corrected to 2,505,266 (D1); `data_export/` must be re-synced or ignored (D6).

**Discovery is complete. Implementation must not start until B1-B3 are dispositioned (schema type decision + delimiter/quoting decision + orphan-card policy), because each requires a design choice that affects `schema.gsql`, the loading jobs and the ETL.**
