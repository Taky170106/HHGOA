# TigerGraph Foundation — HHGoa 2026 Agentic Fraud Investigation (Phase 1)

Implements the verified Phase 0 data model as a working TigerGraph graph that can support fraud-investigation queries.

**Source of truth**: `phase0/PHASE0_FINAL_REPORT.md`, `phase0/ENTITY_MODEL.md`, `phase0/RELATIONSHIP_MODEL.md`, `phase0/TIGERGRAPH_SCHEMA_PROPOSAL.md`, `phase0/DATA_DICTIONARY.md`, `phase0/OUTPUT_SCHEMA.md`, `phase0/POLICY_RULES.md`.

**No invented entities/relationships. No MCP/GraphRAG/UI/XAI/next-best-action. No final answers for the 20 benchmark cases.**

---

## 1. Prerequisites

- Python 3.10+ with `pandas`, `numpy`
- TigerGraph instance: **Savanna (recommended)** or Community Edition 3.9+
  - Sign up: https://tigergraph.com/savanna — or install Community per TigerGraph docs
  - GSQL client (`gsql` CLI) or GraphStudio
- Disk: ~400MB for `data/vertices`+`data/edges` (produced locally — see §5)
- Credentials via environment variables (never hardcoded) — copy `.env.example` → `.env`

## 2. TigerGraph Setup

1. Create a TigerGraph solution/graph named `hhg_fraud_graph` (or set `TIGERGRAPH_GRAPH_NAME` in `.env`).
2. Ensure GSQL can connect: `gsql -h $TIGERGRAPH_HOST -u $TIGERGRAPH_USERNAME -p $TIGERGRAPH_PASSWORD`
3. Install Graph Data Science Library if you want algorithms (`tigergraph/algorithms/`): `gsql> INSTALL QUERY ...` per TigerGraph docs.

## 3. Project Structure

```
tigergraph/
  schema/          # schema.gsql + card_mapping.md
  loading/         # load_vertices.gsql, load_edges.gsql
  queries/         # 9 investigation queries A–I
  algorithms/      # ALGORITHMS.md + algorithms.gsql
  scripts/         # build_graph_data.py (ETL)
  validation/      # validate_graph.py + GRAPH_VALIDATION_REPORT.md
  README.md        # this file
data/
  vertices/        # 8 vertex CSVs (produced locally, not raw)
  edges/           # 11 edge CSVs
  validation/      # BENCHMARK_CONNECTIVITY.md
  VALIDATION_REPORT.md
phase0/            # Phase 0 deliverables (source of truth)
```

Do not modify raw files under `DATASET/`.

## 4. Graph Creation — Schema Installation

```bash
# from repo root, with TigerGraph reachable
gsql tigergraph/schema/schema.gsql
# Verify
gsql -g hhg_fraud_graph "ls"
```

What it creates: **8 vertices** (Customer, Card, Transaction, DeviceProfile, EmailDomain, BillingRegion, ClosedCase, BenchmarkCase) and **11 edges** (OWNS, MADE, NEXT, BILLED_IN, PURCHASER_EMAIL, RECIPIENT_EMAIL, FROM_DEVICE, INVOLVES, ON_CARD, CONNECTED_TO, TRIGGERS) — see `tigergraph/schema/schema.gsql`. Card PK is the canonical `CXXXX-KY` per `tigergraph/schema/card_mapping.md` (Q1 resolution).

If schema conflicts with Phase 0: **STOP and document** — do not silently pick. No conflicts were found; Card mapping is the only open decision from Phase 0 §19 Q1, resolved deterministically here.

## 5. Data Preparation (Graph-Ready Files)

Produces `data/vertices/*.csv` and `data/edges/*.csv` from `DATASET/*.csv` — deterministic, UTF-8, explicit headers, stable IDs, consistent null/timestamp handling, sorted deterministically.

```bash
python tigergraph/scripts/build_graph_data.py
# validate without writing:
python tigergraph/scripts/build_graph_data.py --validate-only
# check report:
cat data/VALIDATION_REPORT.md
```

Details:
- No modification of raw data.
- Validates duplicates (TransactionID 0), missing PKs (0), orphan identity (0), invalid timestamps (0), categories (W/C/H/R/S only), customer↔card1 1:1 (13,553 each), and orphan edges (0).
- Timestamps: `ts` preserved as `YYYY-MM-DD HH:MM:SS` (DATETIME) + `dt_seconds` as UINT; NEXT edges carry `time_delta_hours`.
- Nulls: empty string for nullable string FKs (addr1, email, proxy, etc.); risk_score -1 sentinel for missing benchmark risk.
- Card mapping via `customer_id` bridge — see `tigergraph/schema/card_mapping.md` and `data/vertices/card_mapping.csv`.

Expected counts (source-derived, verified):

- Vertices: Customer 13,553 | Card 13,553 | Transaction 590,742 | DeviceProfile 9,706 | EmailDomain 60 | BillingRegion 332 | ClosedCase 5,565 | BenchmarkCase 20
- Edges: OWNS 13,553 | MADE 590,742 | NEXT 577,189 | BILLED_IN 525,003 | PURCHASER_EMAIL 496,262 | RECIPIENT_EMAIL 137,453 | FROM_DEVICE 144,432 | INVOLVES 14,955 | ON_CARD 5,565 | CONNECTED_TO 92 | TRIGGERS 20

## 6. Loading

After schema install and after `build_graph_data.py` has produced `data/`:

```bash
# vertices (any order, but this order is convenient)
gsql -g hhg_fraud_graph "RUN LOADING JOB load_customer USING f=\"data/vertices/customer.csv\""
gsql -g hhg_fraud_graph "RUN LOADING JOB load_card USING f=\"data/vertices/card.csv\""
gsql -g hhg_fraud_graph "RUN LOADING JOB load_transaction USING f=\"data/vertices/transaction.csv\""
gsql -g hhg_fraud_graph "RUN LOADING JOB load_device_profile USING f=\"data/vertices/device_profile.csv\""
gsql -g hhg_fraud_graph "RUN LOADING JOB load_email_domain USING f=\"data/vertices/email_domain.csv\""
gsql -g hhg_fraud_graph "RUN LOADING JOB load_billing_region USING f=\"data/vertices/billing_region.csv\""
gsql -g hhg_fraud_graph "RUN LOADING JOB load_closed_case USING f=\"data/vertices/closed_case.csv\""
gsql -g hhg_fraud_graph "RUN LOADING JOB load_benchmark_case USING f=\"data/vertices/benchmark_case.csv\""

# edges (after vertices; recommended order below)
for job in load_owns load_made load_next load_billed_in load_purchaser_email load_recipient_email load_from_device load_involves load_on_card load_connected_to load_triggers; do
  gsql -g hhg_fraud_graph "RUN LOADING JOB $job USING f=\"data/edges/${job#load_}.csv\""
done
# Exact filenames: see tigergraph/loading/load_vertices.gsql and load_edges.gsql
```

Loading is reproducible (same inputs → same counts); no manual one-off insertion as primary mechanism.

## 7. Validation

File-level validation (no live instance needed):

```bash
python tigergraph/validation/validate_graph.py
cat tigergraph/validation/GRAPH_VALIDATION_REPORT.md
cat data/validation/BENCHMARK_CONNECTIVITY.md
cat data/VALIDATION_REPORT.md
```

Live validation (after TigerGraph load):

```gsql
# in gsql, after loading
USE GRAPH hhg_fraud_graph
RUN QUERY get_transaction("3514030")
RUN QUERY get_customer_history("C12382")
RUN QUERY get_card_history("C12382-K1")
RUN QUERY find_device_connections("3514030", "")
RUN QUERY find_related_cases("3514030", "C12382-K1", "C12382", "", "", "")
RUN QUERY temporal_chain("C12382-K1")
RUN QUERY calculate_exposure_list({"3514030","3514031"})
RUN QUERY benchmark_case_context("HHG-014")
```

Expected: vertex counts above, 0 orphan edges, 20/20 benchmark cases connected, sample traversals succeed. See `tigergraph/validation/GRAPH_VALIDATION_REPORT.md` for the validated report.

## 8. Running Each GSQL Query

All queries are in `tigergraph/queries/` (GSQL 3.x). Install then run:

```bash
gsql tigergraph/queries/get_transaction.gsql
gsql -g hhg_fraud_graph "RUN QUERY get_transaction(\"3514030\")"

gsql tigergraph/queries/get_customer_history.gsql
gsql -g hhg_fraud_graph "RUN QUERY get_customer_history(\"C12382\")"

gsql tigergraph/queries/get_card_history.gsql
gsql -g hhg_fraud_graph "RUN QUERY get_card_history(\"C12382-K1\")"

gsql tigergraph/queries/find_device_connections.gsql
gsql -g hhg_fraud_graph "RUN QUERY find_device_connections(\"3514030\", \"\")"

gsql tigergraph/queries/find_related_transactions.gsql
gsql -g hhg_fraud_graph "RUN QUERY find_related_transactions(\"3514030\", \"\", \"\")"

gsql tigergraph/queries/find_related_cases.gsql
gsql -g hhg_fraud_graph "RUN QUERY find_related_cases(\"3514030\",\"C12382-K1\",\"C12382\",\"\",\"\",\"\")"

gsql tigergraph/queries/temporal_chain.gsql
gsql -g hhg_fraud_graph "RUN QUERY temporal_chain(\"C12382-K1\")"

gsql tigergraph/queries/calculate_exposure.gsql
gsql -g hhg_fraud_graph "RUN QUERY calculate_exposure_list({\"3514030\",\"3514031\"})"

gsql tigergraph/queries/benchmark_case_context.gsql
gsql -g hhg_fraud_graph "RUN QUERY benchmark_case_context(\"HHG-014\")"
```

### Expected inputs/outputs

| Query | Input | Output |
|-------|-------|--------|
| get_transaction | txn_id | Transaction attrs + Card/Customer/Device/Region/Email + NEXT neighbors |
| get_customer_history | customer_id | Customer → Cards → Transactions |
| get_card_history | card_id | Card → Transactions (ordered via ts/NEXT) |
| find_device_connections | txn_id or device_profile_id | Other cards/customers/txns sharing device |
| find_related_transactions | txn_id / card_id / customer_id | Related txns via verified edges (card/region/device/email) |
| find_related_cases | any entity ID(s) | Historical ClosedCases via verified paths |
| temporal_chain | card_id | Ordered txn sequence + NEXT edges (velocity/repeats) |
| calculate_exposure | Set<STRING> txn_ids | Sum(amount) |
| benchmark_case_context | benchmark_case_id | Full context to begin investigation |

## 9. Troubleshooting

- **Orphan edges / PK mismatches**: re-run `python tigergraph/scripts/build_graph_data.py` (produces fresh `card_mapping.csv`); verify `DATASET/` not modified.
- **Card ID not found**: use canonical `CXXXX-KY` per `tigergraph/schema/card_mapping.md`; numeric card1 alone is attribute `card1_num`, not PK.
- **Empty FROM_DEVICE**: expected for in_person (channel W) and for 6,640 online txns without identity — query returns empty, not error.
- **Generic device super-component**: filter by `DeviceProfile.specificity >= 0.01` per `tigergraph/algorithms/ALGORITHMS.md` before WCC/Louvain.
- **GSQL install errors**: ensure `USE GRAPH hhg_fraud_graph` before `CREATE QUERY`; check GSQL version ≥3.9.
- **.env not found**: copy `.env.example` → `.env` and set host/credentials; never commit `.env`.

## 10. What Phase 1 Does NOT Do

- No LLM agent, no MCP, no GraphRAG embeddings, no UI, no XAI, no next-best-action, no final answers for the 20 benchmark cases — per Phase 1 scope.

Next phase (after validation passes): TigerGraph MCP + agent tool interface.
