# Phase 0 — Entity Model

## Entity Discovery Methodology
Entities inferred from actual dataset evidence (transactions.csv, identity.csv, closed_cases_history.csv, case_pack.csv). Each entity must have:
1. Identifying field(s) in source data
2. Measurable cardinality
3. Clear relationships to other entities
4. Justification for TigerGraph vertex

---

## Verified Entities

### 1. Customer
- **Source identifier**: `customer_id` (string, e.g., `C12382`)
- **Cardinality**: 13,553 unique in transactions; 1,892 in closed cases; 20 in case pack
- **Evidence**: 
  - `transactions.csv`: 13,553 unique `customer_id` values
  - 1:1 mapping with `card1` (each customer has exactly one card in transaction data)
  - `closed_cases_history.csv`: 1,892 unique customers with historical cases
  - `case_pack.csv`: 20 customers under investigation
- **Attributes**: `customer_id` (PK), `card_count` (always 1 in txns), `total_txns`, `online_txns`, `in_person_txns`, `addr1_regions`, `date_range_start`, `date_range_end`, `avg_amount`, `max_amount`
- **TigerGraph Vertex**: **YES** — Central hub entity; all investigations start from customer
- **Notes**: In transaction data, 1 customer = 1 card. In benchmark/closed cases, card_id format is `CXXXX-KY` (supports multiple cards per customer conceptually, but not observed in transaction data)

### 2. Card
- **Source identifier**: `card1` (int64, numeric, e.g., `21139`) in transactions; `card_id` (string, e.g., `C12382-K1`) in cases
- **Cardinality**: 13,553 unique `card1` in transactions; ~1,913 unique `card_id` in closed cases
- **Evidence**:
  - `transactions.csv`: `card1` is 1:1 with `customer_id` (13,553 each)
  - `closed_cases_history.csv`: `card_id` format `CXXXX-KY` — 1,913 unique
  - `case_pack.csv`: 20 cards in `CXXXX-KY` format
  - Mapping needed: numeric `card1` ↔ benchmark `card_id`
- **Attributes**: `card1` (numeric PK), `card_id` (benchmark format), `customer_id` (FK), `network` (card4: visa/mastercard/amex/discover), `type` (card6: credit/debit), `issuer_codes` (card2, card3, card5)
- **TigerGraph Vertex**: **YES** — Transaction owner; bridge between Customer and Transaction
- **Notes**: Transaction data shows 1:1 customer:card. Benchmark format suggests multi-card customers possible but not observed in 6-month transaction window.

### 3. Transaction
- **Source identifier**: `TransactionID` (int64, 590,742 unique)
- **Cardinality**: 590,742
- **Evidence**: Every row in `transactions.csv` is a transaction
- **Attributes**: 
  - Core: `TransactionID` (PK), `customer_id` (FK), `card1` (FK), `ts`, `TransactionDT`, `TransactionAmt`, `ProductCD`, `channel`, `risk_score`
  - Geography: `addr1`, `addr2`, `dist1`, `dist2`
  - Email: `P_emaildomain`, `R_emaildomain`
  - Features: `C1-C14`, `D1-D15`, `M1-M9`, `V1-V339`
  - Identity link: `TransactionID` joins to `identity.csv`
- **TigerGraph Vertex**: **YES** — Core event entity; primary investigation target
- **Notes**: Temporal ordering per card enables `NEXT` edges for sequence analysis

### 4. DeviceProfile
- **Source identifier**: Composite key = `DeviceInfo` + `id_30` (OS) + `id_31` (browser) + `id_33` (screen)
- **Cardinality**: 9,706 unique composite profiles; 4,789 shared by >1 customer
- **Evidence**:
  - `identity.csv`: 144,432 records with device details
  - `DeviceType` (mobile/desktop), `DeviceInfo` (model), `id_30` (OS), `id_31` (browser), `id_33` (screen)
  - Key signals: `id_15` (New/Found/Unknown), `id_23` (proxy type), `id_34` (match_status)
  - 6,640 online transactions missing identity records
- **Attributes**: `device_profile_id` (composite hash), `device_type`, `device_info`, `os`, `browser`, `screen`, `newness` (id_15), `proxy_type` (id_23), `match_status` (id_34), `id_01-id_11` (ratings), `customer_count`, `card_count`, `txn_count`
- **TigerGraph Vertex**: **YES** — Critical for linking cards/customers via shared device (Rule R6, patterns 3, 5)
- **Notes**: Many profiles are generic (e.g., `Windows|Windows 10|chrome 63.0|1920x1080` = 842 customers). Need to distinguish specific vs. generic profiles.

### 5. EmailDomain
- **Source identifier**: `P_emaildomain` / `R_emaildomain` (string)
- **Cardinality**: 59 purchaser domains, 60 recipient domains
- **Evidence**:
  - `transactions.csv`: `P_emaildomain` (8,933 customers on gmail.com), `R_emaildomain`
  - Rule R6 mentions "same recipient email"
- **Attributes**: `domain` (PK), `type` (purchaser/recipient), `customer_count`, `card_count`, `txn_count`
- **TigerGraph Vertex**: **YES** — Link for Rule R6 (shared recipient email)
- **Notes**: Highly shared (gmail.com = 8,933 customers). Useful for clustering but low specificity.

### 6. BillingRegion
- **Source identifier**: `addr1` (float64, 332 unique codes)
- **Cardinality**: 332 regions; top region has 2,006 customers
- **Evidence**:
  - `transactions.csv`: `addr1` (65,739 nulls = 11.1%, likely in-person)
  - `addr2` = country code (87 = home country)
  - Pattern 4: "Out-of-region use"
  - Rule R6: "shared region cluster"
- **Attributes**: `region_code` (PK), `country_code` (addr2), `customer_count`, `card_count`, `txn_count`, `is_home_region` (addr2==87)
- **TigerGraph Vertex**: **YES** — Geographic link for Pattern 4 and Rule R6

### 7. ClosedCase
- **Source identifier**: `case_id` (string, `CC-XXXX`, 5,565)
- **Cardinality**: 5,565 (4,665 confirmed_fraud, 900 cleared)
- **Evidence**: `closed_cases_history.csv` — complete historical memory
- **Attributes**: 
  - `case_id` (PK), `customer_id` (FK), `card_id` (FK), `opened_at`, `closed_at`, `outcome`, `pattern`
  - `first_fraud_txn_id`, `txn_ids` (pipe-separated), `n_txns`, `exposure_usd`
  - `connected_card_ids` (pipe-separated), `actions_taken`, `report_filed`, `analyst_notes`
- **TigerGraph Vertex**: **YES** — Case memory; GraphRAG retrieval source; agent writes new cases here
- **Notes**: 4 cases reference a 23-card fraud ring via `connected_card_ids` (verified: CC-2649, CC-2971, CC-2985, CC-3035). 9 `undocumented` pattern cases with detailed notes.

### 8. BenchmarkCase (CasePack)
- **Source identifier**: `case_id` (string, `HHG-XXX`, 20)
- **Cardinality**: 20
- **Evidence**: `case_pack.csv` — the examination cases
- **Attributes**: `case_id` (PK), `opened_at`, `trigger_type`, `trigger_text`, `flagged_txn_id` (FK→Transaction), `card_id` (FK→Card), `customer_id` (FK→Customer), `risk_score` (nullable)
- **TigerGraph Vertex**: **YES** — Agent input; becomes ClosedCase after investigation
- **Notes**: 11 risk_score, 8 customer_report, 1 analyst_request triggers. All Nov-Dec 2016.

---

## Entities NOT Supported by Data

| Entity | Reason |
|--------|--------|
| Merchant | No merchant ID/name in data. ProductCD (W/C/H/R/S) is product category, not merchant. |
| Address | Only `addr1` (region code) and `addr2` (country). No street/city. |
| Organization | No organizational entities in data. |
| IP Address | Only proxy type (id_23), not actual IP. |
| Phone | Only count features (C1-C14), not actual numbers. |

---

## Entity Summary Table

| Entity | Vertex? | Cardinality | Primary Key | Key Attributes | Key Relationships |
|--------|---------|-------------|-------------|----------------|-------------------|
| Customer | YES | 13,553 | customer_id | txn counts, regions, date range | OWNS Card |
| Card | YES | 13,553 | card1 (numeric) / card_id (benchmark) | network, type, customer_id | MADE Transaction, OWNED_BY Customer |
| Transaction | YES | 590,742 | TransactionID | amount, ts, channel, risk_score, features | FROM Card, BILLED_IN Region, PURCHASER_EMAIL, RECIPIENT_EMAIL, FROM_DEVICE, NEXT |
| DeviceProfile | YES | 9,706 | composite hash | type, info, OS, browser, screen, newness, proxy | USED_BY Transaction, LINKS Card/Customer |
| EmailDomain | YES | 59/60 | domain | type (P/R), counts | PURCHASER/RECIPIENT_OF Transaction |
| BillingRegion | YES | 332 | region_code | country_code, is_home | BILLED_IN Transaction |
| ClosedCase | YES | 5,565 | case_id | outcome, pattern, exposure, notes, connected_cards | INVOLVES Transaction/Card, CONNECTED_TO Card |
| BenchmarkCase | YES | 20 | case_id | trigger, flagged_txn, risk_score | TRIGGERS investigation, becomes ClosedCase |

---

## Engineering Recommendations

1. **Card ID Mapping**: Create explicit mapping table `card1_numeric` ↔ `card_id_benchmark` using customer_id as bridge
2. **Device Profile Deduplication**: Separate generic profiles (high customer_count) from specific ones; weight by specificity
3. **ClosedCase txn_ids**: Parse pipe-separated `txn_ids` into individual `INVOLVES` edges for graph traversal
4. **Connected Cards**: Parse `connected_card_ids` into `CONNECTED_TO` edges for ring detection
5. **Temporal Edges**: Create `NEXT` edges per card ordered by `ts` for sequence pattern detection (card testing)