# PHASE 2 — TigerGraph Deployment & Load

Phase 2 implements **only** the TigerGraph graph foundation: environment verification,
schema verification, deterministic loading of `data/vertices/` + `data/edges/`, and
live validation. No investigation logic, ML, GraphRAG, XAI, counterfactuals, policy,
Next Best Action, FastAPI or Next.js work is included here.

---

## 1. Target instance

| Item | Value |
|------|-------|
| Container | `hhg-tigergraph` |
| Image | `tigergraph/community:4.2.5` |
| Edition | Community Edition |
| GSQL client | `b7e492bd40b45153ee2a8758b03183b50ebb6eca` |
| Ports | 14022 (ssh), 9000 (RESTPP), 14240 (GraphStudio / GSQL) |
| Graph | `hhg_fraud_graph` |
| Data mount | `/home/tigergraph/data` → `/home/tigergraph/tigergraph/data/files/data` |

### 1.1 Environment problems found and how they were handled

| Finding | Evidence | Action |
|---------|----------|--------|
| Docker daemon not running | `docker version` failed with `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`; no `Docker Desktop` / `com.docker.backend` / `dockerd` processes; stale `backend.lock` and `frontend.lock` under `%LOCALAPPDATA%\Docker` | Started the existing Docker Desktop install once (evidence-based daemon start, not a container restart) |
| Container exited | `docker ps -a` → `hhg-tigergraph ... Exited (255)` | `docker start hhg-tigergraph` — the existing container was started, **never recreated** |
| Service health before loading | `gadmin status` | **16 / 16 services `Online` / `Running`**: ADMIN, CTRL, DICT, ETCD, EXE, GPE, GSE, GSQL, GUI, IFM, KAFKA, KAFKACONN, KAFKASTRM-LL, NGINX, RESTPP, ZK |
| Data survived the restart | `RUN QUERY count_all()` immediately after start | All 8 vertex counts identical to pre-restart values; all edge counts `0` (edges not yet loaded) |

No container was restarted more than once, and no container was recreated.

---

## 2. Schema verification

`tigergraph/schema/schema.gsql` already existed from Phase 1 and was **used as-is —
not recreated, not redesigned**.

| Verified | Count |
|----------|-------|
| Vertex types | 8 — `Customer, Card, Transaction, DeviceProfile, EmailDomain, BillingRegion, ClosedCase, BenchmarkCase` |
| Edge types | 11 — `OWNS, MADE, NEXT, BILLED_IN, PURCHASER_EMAIL, RECIPIENT_EMAIL, FROM_DEVICE, INVOLVES, ON_CARD, CONNECTED_TO, TRIGGERS` |

Phase 2 added, removed, renamed or retyped **zero** vertex types, edge types,
attributes and primary keys. Blocker B1 was resolved by correcting the data
serialization, not by changing the model (§4.1).

---

## 3. Source → graph mapping

Authoritative load source: `data/vertices/` (9 CSV files) and `data/edges/` (11 CSV
files), produced deterministically by `tigergraph/scripts/build_graph_data.py` from
the raw `DATASET/` files. `data_export/` is stale and was **not** loaded.
`data/vertices/card_mapping.csv` is a lookup artifact and is **not** loaded into the
graph.

All 19 loading jobs were verified against the schema and the CSV headers by
`tigergraph/scripts/14_schema_alignment.py`:

- every `$"column"` referenced by a job exists in that CSV's header
- every job declares `HEADER="true"` (name-based, not position-based, mapping)
- the number of `VALUES` expressions equals the number of schema attributes
  (2 endpoint expressions + N attributes for edges)

Result: **19 / 19 jobs align 1:1 with schema + CSV headers.**

### 3.1 Loading jobs (19)

| Order | Job | Target | CSV | Rows |
|-------|-----|--------|-----|------|
| 1 | `load_customer` | Customer | `vertices/customer.csv` | 13,553 |
| 2 | `load_card` | Card | `vertices/card.csv` | 13,553 |
| 3 | `load_transaction` | Transaction | `vertices/transaction.csv` | 590,742 |
| 4 | `load_device_profile` | DeviceProfile | `vertices/device_profile.csv` | 9,706 |
| 5 | `load_email_domain` | EmailDomain | `vertices/email_domain.csv` | 60 |
| 6 | `load_billing_region` | BillingRegion | `vertices/billing_region.csv` | 332 |
| 7 | `load_closed_case` | ClosedCase | `vertices/closed_case.csv` | 5,565 |
| 8 | `load_benchmark_case` | BenchmarkCase | `vertices/benchmark_case.csv` | 20 |
| 9 | `load_owns` | OWNS | `edges/owns.csv` | 13,553 |
| 10 | `load_made` | MADE | `edges/made.csv` | 590,742 |
| 11 | `load_next` | NEXT | `edges/next.csv` | 577,189 |
| 12 | `load_billed_in` | BILLED_IN | `edges/billed_in.csv` | 525,003 |
| 13 | `load_purchaser_email` | PURCHASER_EMAIL | `edges/purchaser_email.csv` | 496,262 |
| 14 | `load_recipient_email` | RECIPIENT_EMAIL | `edges/recipient_email.csv` | 137,453 |
| 15 | `load_from_device` | FROM_DEVICE | `edges/from_device.csv` | 144,432 |
| 16 | `load_involves` | INVOLVES | `edges/involves.csv` | 14,955 |
| 17 | `load_on_card` | ON_CARD | `edges/on_card.csv` | 5,565 |
| 18 | `load_connected_to` | CONNECTED_TO | `edges/connected_to.csv` | 92 |
| 19 | `load_triggers` | TRIGGERS | `edges/triggers.csv` | 20 |

Dependency-safe order enforced by `tigergraph/scripts/17_phase2_load.sh`:
**vertices first (1–8), then edges (9–19)**.

All 19 jobs are present in the graph catalogue as `# ENABLED`, each with
`USING SEPARATOR=",", HEADER="true", EOL="\n", QUOTE="double"`.

---

## 4. Problems found during loading

Four discrepancies were found. Each was diagnosed with evidence, reported, and
fixed at the narrowest point that did **not** change the approved model.

### 4.1 B1 — `card2` / `card3` / `card5` serialized as `189.0` against schema type `UINT`

- **Symptom:** `card.csv` loader reported `Invalid Attributes: 13543`, `Valid Object: 10`.
- **Evidence:** `DATASET/transactions.csv` was scanned across all 590,742 rows.
  Every non-empty `card2`, `card3`, `card5` value matches `^\d+\.0*$`:
  `card2` 581,806 integral / 8,936 empty; `card3` 589,177 / 1,565; `card5` 586,483 / 4,259.
  **Zero non-integral values exist anywhere in the raw source.**
  `phase0/ENTITY_MODEL.md:34` defines them as *issuer codes* (integers);
  `phase0/DATA_DICTIONARY.md:19` types them `mixed`.
- **Root cause:** the raw source is float64 (NaN present), so pandas serializes
  `189.0`. The `.0` is a serialization artifact, not a value.
- **Resolution chosen:** normalize in the ETL (`build_graph_data.py`), keeping the
  schema type `UINT`. Changing the schema to `DOUBLE` would have altered the approved
  model to match a file-format artifact, and rewriting identifiers was explicitly
  out of bounds.
- **Result:** `Card` loads **13,553 / 13,553, 0 rejected rows.**
- **Live confirmation:** `get_card_history("C12382-K1")` over RESTPP returns
  `"card2": 242, "card3": 150, "card5": 166` — integers in the live graph.

### 4.2 B2 — `benchmark_case.trigger_text` rejected (11 rows)

- **Symptom:** `BenchmarkCase` loaded **9 / 20**, 11 rows rejected.
- **Evidence:** exactly the 11 rows whose quoted `trigger_text` contains an embedded
  comma were rejected; the 9 comma-free rows loaded. `DATASET/case_pack.csv` contains
  22 double-quote bytes over 11 rows — the graph-ready file is byte-identical to source.
- **Root cause:** TigerGraph's default loader treats `,` as a column separator and
  does **not** honour RFC-4180 quoting, so those rows shifted columns.
- **Resolution:** `QUOTE="double"` added to the loading jobs — a documented TigerGraph
  4.2.5 `USING` option. **No data was modified.**
- **Result:** `BenchmarkCase` loads **20 / 20, 0 rejected rows.**

### 4.3 B3 — `closed_case.analyst_notes` silently truncated (2,324 rows)

- **Symptom:** no loader error at all; `CC-0002.analyst_notes` was 335 characters in
  the CSV but 247 characters in the graph, cutting exactly at the first comma inside
  the quoted field (`... had no history in`).
- **Evidence:** 2,324 of 5,565 rows affected; `DATASET/closed_cases_history.csv`
  contains 4,648 double-quote bytes over 2,324 rows. This was the more dangerous half
  of the quoting defect because it produced **silent data loss with zero errors**.
- **Resolution:** same `QUOTE="double"` fix. **No data was modified.**
- **Result:** `ClosedCase` loads **5,565 / 5,565** with untruncated text, 0 rejected rows.

### 4.4 D5 — 37 `ON_CARD` orphans over 21 distinct cards

- **Symptom:** 37 of 5,565 `on_card.csv` rows targeted a `card_id` that does not exist
  in `card.csv` (21 distinct IDs, all of the lower-suffix form, e.g. `C02231-K1`).
  `build_graph_data.py::check_orphans()` did not check `ON_CARD` at all — the gap
  recorded as D5 in `docs/DATASET_DISCOVERY.md`.
- **Evidence:** `tigergraph/schema/card_mapping.md` (Phase 1 decision record) states
  the canonical Card PK is one vertex per customer at the **maximum** suffix seen, and
  that *every* edge references `card_id` through that map. The ETL applied the map to
  `OWNS`, `MADE`, `Transaction.card_id` and `CONNECTED_TO`, but never to
  `on_card.to_card_id` or `closed_case.card_id`. It is an ETL bug against documented
  design, not a model discrepancy.
- **Resolution:** `canonical_card_id()` implemented in the ETL and applied to
  `ClosedCase.card_id` and the `ON_CARD` endpoint. The ETL reported
  **`canonical card_id resolutions applied: 37`** — exactly the orphan count.
- **Result:** `ON_CARD` **5,565 / 5,565, 0 orphans.**

### 4.5 Scope note — investigation queries not fixed here

Deploying the pre-existing `tigergraph/queries/*.gsql` surfaced **5 of 9 files with
pre-existing GSQL compile errors under 4.2.5** (`benchmark_case_context`,
`find_device_connections`, `find_related_cases`, `find_related_transactions`,
`get_transaction`). **5 of 10 query definitions installed successfully** (7 queries
installed in the graph in total: those 5 plus `count_all` and `phase2_validate`).

These are investigation queries. Fixing them would mean writing investigation logic,
which is outside Phase 2. They are recorded as **BLOCKER Q1 / PENDING_LIVE_EXECUTION**
in `docs/PHASE2_VALIDATION_REPORT.md` for Phase 3 sign-off. No investigation query was
modified, and no new GSQL investigation logic was written.

---

## 5. Determinism and change scope

Loading is deterministic and idempotent: every job upserts by primary key, so
re-running `tigergraph/scripts/17_phase2_load.sh` from the same `data/` files
reproduces the same graph state.

SHA-256 of all 20 graph CSVs was captured before and after the fixes
(`tigergraph/validation/data_hashes_phase2_before.json` / `_after.json`):

| Changed | Reason |
|---------|--------|
| `data/vertices/card.csv` | B1 issuer-code normalization |
| `data/vertices/closed_case.csv` | D5 canonical `card_id` (37 values) |
| `data/edges/on_card.csv` | D5 canonical endpoint (37 values) |

**17 of 20 files are byte-identical.** `DATASET/*` was never opened for writing.

---

## 6. Load result

All 19 jobs reported `LOAD SUCCESSFUL`. Per-file loader output
(`tigergraph/validation/phase2_load.log`):

| CSV | LINES | OBJECTS | ERRORS |
|-----|-------|---------|--------|
| vertices/customer.csv | 13553 | 13553 | 0 |
| vertices/card.csv | 13553 | 13553 | 0 |
| vertices/transaction.csv | 590742 | 590742 | 0 |
| vertices/device_profile.csv | 9706 | 9706 | 0 |
| vertices/email_domain.csv | 60 | 60 | 0 |
| vertices/billing_region.csv | 332 | 332 | 0 |
| vertices/closed_case.csv | 5565 | 5565 | 0 |
| vertices/benchmark_case.csv | 20 | 20 | 0 |
| edges/owns.csv | 13553 | 13553 | 0 |
| edges/made.csv | 590742 | 590742 | 0 |
| edges/next.csv | 577189 | 577189 | 0 |
| edges/billed_in.csv | 525003 | 525003 | 0 |
| edges/purchaser_email.csv | 496262 | 496262 | 0 |
| edges/recipient_email.csv | 137453 | 137453 | 0 |
| edges/from_device.csv | 144432 | 144432 | 0 |
| edges/involves.csv | 14955 | 14955 | 0 |
| edges/on_card.csv | 5565 | 5565 | 0 |
| edges/connected_to.csv | 92 | 92 | 0 |
| edges/triggers.csv | 20 | 20 | 0 |

**Total rejected rows across all 19 loading jobs: 0.**
**Total lines = total objects in every job → no row was dropped, shifted or truncated.**

---

## 7. Reproduction

```bash
# 1. rebuild graph-ready data (deterministic)
python tigergraph/scripts/build_graph_data.py

# 2. file-level integrity scan
python tigergraph/scripts/16_file_integrity.py

# 3. pre-load schema/job/CSV alignment check
python tigergraph/scripts/14_schema_alignment.py

# 4. copy updated CSVs + loading jobs into the container, then:
docker exec hhg-tigergraph bash /tmp/17_phase2_load.sh

# 5. live counts + live integrity
gsql -g hhg_fraud_graph 'RUN QUERY count_all()'
gsql -g hhg_fraud_graph 'RUN QUERY phase2_validate()'
```

Full load log: `tigergraph/validation/phase2_load.log`.
