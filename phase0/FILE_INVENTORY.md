# Phase 0 — File Inventory

## Dataset Files

| File | Type | Size | Rows | Columns | Purpose |
|------|------|------|------|---------|---------|
| `transactions.csv` | CSV | ~708 MB | 590,742 | 397 | Core transaction log: every transaction with 393 Vesta features + added fields |
| `identity.csv` | CSV | ~15 MB | 144,432 | 41 | Device/connection details for online transactions only (joins on TransactionID) |
| `closed_cases_history.csv` | CSV | ~2 MB | 5,565 | 15 | Historical investigations (Jul–Oct 2016): 4,665 confirmed fraud, 900 cleared |
| `case_pack.csv` | CSV | ~3 KB | 20 | 8 | The 20 benchmark cases to investigate (Nov–Dec 2016) |

## File Details

### transactions.csv
- **Primary key**: `TransactionID` (unique, 590,742)
- **Foreign keys**: `customer_id` (13,553 unique), `card1` (13,553 unique, 1:1 with customer_id)
- **Time fields**: `TransactionDT` (seconds from epoch), `ts` (YYYY-MM-DD HH:MM:SS, Jul 2 – Dec 31 2016)
- **Amount**: `TransactionAmt` (USD, mean $134, max ~$4,438)
- **Channel**: `channel` (`in_person` 74.4%, `online` 25.6%) — derived from `ProductCD` (`W` = in_person)
- **Risk score**: `risk_score` (0–1, mean 0.17, max 0.99) — bank's detection model output
- **Billing**: `addr1` (332 regions, 65,739 nulls), `addr2` (country codes, 87 = home)
- **Card**: `card4` (network), `card6` (type)
- **Email**: `P_emaildomain`, `R_emaildomain` (59/60 unique domains)
- **Vesta features**: `C1–C14` (counts), `D1–D15` (time deltas), `M1–M9` (match flags), `V1–V339` (engineered features)
- **Nulls**: `addr1`/`addr2` have 65,739 nulls (11.1%) — likely in-person transactions

### identity.csv
- **Primary key**: `TransactionID` (144,432 unique, subset of online transactions)
- **Join**: Inner join with `transactions.csv` on `TransactionID` → 144,432 matches, 6,640 online txns missing identity
- **Device**: `DeviceType` (mobile/desktop), `DeviceInfo` (model string)
- **Key categorical**: `id_15` (New/Found/Unknown), `id_23` (proxy: transparent/anonymous/hidden), `id_30` (OS), `id_31` (browser), `id_33` (screen), `id_34` (match_status)
- **Encoded ratings**: `id_01–id_11` (device/IP/proxy/login ratings)

### closed_cases_history.csv
- **Primary key**: `case_id` (CC-0001 to CC-5565)
- **Entities**: `customer_id`, `card_id` (format `CXXXX-KY`)
- **Time**: `opened_at`, `closed_at` (Jul 2 – Nov 6 2016)
- **Outcome**: `confirmed_fraud` (4,665) or `cleared` (900)
- **Pattern**: 5 documented + `undocumented` (9) + `none` (cleared)
- **Transaction links**: `first_fraud_txn_id`, `txn_ids` (pipe-separated), `n_txns`
- **Financial**: `exposure_usd` (sum of fraudulent txn amounts)
- **Network**: `connected_card_ids` (pipe-separated, 4 cases with large rings of 22 cards)
- **Actions**: `actions_taken` (pipe-separated policy actions), `report_filed` (Yes/No)
- **Notes**: `analyst_notes` — narrative explaining the case

### case_pack.csv
- **20 cases** (HHG-001 to HHG-020), all Nov–Dec 2016
- **Trigger types**: `risk_score` (11), `customer_report` (8), `analyst_request` (1)
- **Fields**: `case_id`, `opened_at`, `trigger_type`, `trigger_text`, `flagged_txn_id`, `card_id`, `customer_id`, `risk_score` (only for risk_score triggers)
- **Flagged transactions**: All exist in transactions.csv; 11 have identity records, 9 are in_person (no identity)

## Cross-File Relationships (Verified)

| From | To | Join Key | Match Rate |
|------|-----|----------|------------|
| transactions | identity | TransactionID | 144,432 / 151,072 online (95.6%) |
| transactions | case_pack | TransactionID (flagged_txn_id) | 20 / 20 (100%) |
| transactions | closed_cases | TransactionID (txn_ids) | Verified via txn_ids parsing |
| case_pack | closed_cases | customer_id, card_id | 20 customers in both; card_id format matches |
| transactions | transactions (NEXT) | card1 + ts ordering | Per-card temporal chain |

## Key Observations
- **1:1 customer:card** in transaction data (each customer_id maps to exactly one card1)
- **Card ID format**: Case pack and closed cases use `CXXXX-KY` (e.g., `C12382-K1`); transactions use numeric `card1` (e.g., `21139`). Mapping required.
- **Device sharing is massive**: 4,789 device profiles used by >1 customer (many are generic: `Windows|Windows 10|chrome 63.0|1920x1080` = 842 customers)
- **Email domains highly shared**: gmail.com = 8,933 customers
- **Billing regions highly shared**: Top addr1 = 2,006 customers
- **Closed cases contain a large fraud ring** (4 cases referencing the same 23-card ring via `connected_card_ids`)