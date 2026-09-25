# Phase 0 — Relationship Model

## Verified Relationships (Evidence-Based)

### 1. Customer → OWNS → Card
- **Source**: `transactions.csv` — `customer_id` + `card1` pairs
- **Cardinality**: 13,553 (1:1 in transaction data)
- **Join Key**: `customer_id` (string) + `card1` (int64)
- **Evidence**: Every transaction has both fields; `customer_id` uniquely determines `card1` and vice versa
- **Attributes**: None on edge (ownership is static)
- **TigerGraph Edge**: **YES** — Directed `Customer` → `Card`
- **Notes**: Benchmark format (`CXXXX-KY`) suggests potential for 1:N but not observed in 6-month window

### 2. Card → MADE → Transaction
- **Source**: `transactions.csv` — `card1` on every transaction
- **Cardinality**: 590,742 edges (1 per transaction)
- **Join Key**: `card1` (int64)
- **Evidence**: Every transaction row has `card1`; 13,553 unique cards
- **Attributes**: `sequence_num` (position in card's chronological history)
- **TigerGraph Edge**: **YES** — Directed `Card` → `Transaction`

### 3. Transaction → BILLED_IN → BillingRegion
- **Source**: `transactions.csv` — `addr1` (region), `addr2` (country)
- **Cardinality**: ~525,000 (65,739 nulls = 11.1% missing, likely in-person)
- **Join Key**: `addr1` (float64) + `addr2` (float64)
- **Evidence**: 332 unique `addr1` values; 60 unique `addr2` values; 87 = home country
- **Attributes**: `is_home_country` (addr2==87), `channel` (in_person/online)
- **TigerGraph Edge**: **YES** — Directed `Transaction` → `BillingRegion`

### 4. Transaction → PURCHASER_EMAIL → EmailDomain
- **Source**: `transactions.csv` — `P_emaildomain`
- **Cardinality**: 496,262 (84.0% of transactions; verified count)
- **Join Key**: `P_emaildomain` (string)
- **Evidence**: 59 unique domains; gmail.com = 228,436 transactions
- **Attributes**: None
- **TigerGraph Edge**: **YES** — Directed `Transaction` → `EmailDomain` (type: purchaser)

### 5. Transaction → RECIPIENT_EMAIL → EmailDomain
- **Source**: `transactions.csv` — `R_emaildomain`
- **Cardinality**: ~135,000 (fewer recipient emails)
- **Join Key**: `R_emaildomain` (string)
- **Evidence**: 60 unique domains; gmail.com = 57,225 transactions
- **Attributes**: None
- **TigerGraph Edge**: **YES** — Directed `Transaction` → `EmailDomain` (type: recipient)

### 6. Transaction → FROM_DEVICE → DeviceProfile
- **Source**: `identity.csv` join `transactions.csv` on `TransactionID`
- **Cardinality**: 144,432 (online transactions with identity records)
- **Join Key**: `TransactionID` (int64)
- **Evidence**: 144,432 identity records; 6,640 online txns missing identity
- **Attributes**: `device_type`, `newness` (id_15), `proxy_type` (id_23), `match_status` (id_34), `id_01-id_11` ratings
- **TigerGraph Edge**: **YES** — Directed `Transaction` → `DeviceProfile`
- **Notes**: Critical for Patterns 3, 5 and Rule R6 (shared device)

### 7. Transaction → NEXT → Transaction (Per-Card Sequence)
- **Source**: `transactions.csv` — `card1` + `ts` ordering
- **Cardinality**: ~577,000 (transactions per card - 1)
- **Join Key**: `card1` + chronological `ts`
- **Evidence**: Every card has temporal sequence; enables pattern detection
- **Attributes**: `time_delta_hours`, `amount_ratio`, `channel_change` (in_person↔online)
- **TigerGraph Edge**: **YES** — Directed `Transaction` → `Transaction` (self-edge)
- **Use Case**: Card testing (Pattern 1): 3+ small online auths within 1 hour then larger purchase

### 8. ClosedCase → INVOLVES → Transaction
- **Source**: `closed_cases_history.csv` — `txn_ids` (pipe-separated)
- **Cardinality**: 14,955 edges (verified: parsed sum of `txn_ids` across all 5,565 cases; all IDs exist in transactions.csv)
- **Join Key**: Parse `txn_ids` string → individual `TransactionID`
- **Evidence**: 4,665 confirmed fraud cases with transaction lists
- **Attributes**: `is_first_fraud` (matches `first_fraud_txn_id`), `sequence_in_case`
- **TigerGraph Edge**: **YES** — Directed `ClosedCase` → `Transaction`

### 9. ClosedCase → ON_CARD → Card
- **Source**: `closed_cases_history.csv` — `card_id` (benchmark format)
- **Cardinality**: 5,565 (1 per case)
- **Join Key**: `card_id` (string `CXXXX-KY`) → map to numeric `card1`
- **Evidence**: Every closed case has a `card_id`
- **Attributes**: None
- **TigerGraph Edge**: **YES** — Directed `ClosedCase` → `Card`

### 10. ClosedCase → CONNECTED_TO → Card
- **Source**: `closed_cases_history.csv` — `connected_card_ids` (pipe-separated)
- **Cardinality**: 92 edges (4 cases × 23 cards each — verified: CC-2649, CC-2971, CC-2985, CC-3035)
- **Join Key**: Parse `connected_card_ids` → individual `card_id` → map to `card1`
- **Evidence**: 4 cases reference identical 23-card fraud ring
- **Attributes**: `connection_type` (device/region/email/ring)
- **TigerGraph Edge**: **YES** — Directed `ClosedCase` → `Card` (multiple)

### 11. BenchmarkCase → TRIGGERS → Transaction
- **Source**: `case_pack.csv` — `flagged_txn_id`
- **Cardinality**: 20 (1 per benchmark case)
- **Join Key**: `flagged_txn_id` = `TransactionID`
- **Evidence**: All 20 flagged transactions exist in transactions.csv
- **Attributes**: `trigger_type`, `trigger_text`, `risk_score` (if applicable)
- **TigerGraph Edge**: **YES** — Directed `BenchmarkCase` → `Transaction`

---

## Multi-Hop Investigation Paths (Data-Supported)

### Path A: Device-Based Compromise Ring
```
Customer → OWNS → Card → MADE → Transaction → FROM_DEVICE → DeviceProfile
                                                      ← FROM_DEVICE ← Transaction ← MADE ← Card ← OWNS ← Other Customer
```
- **Supported by**: 4,789 device profiles shared by >1 customer
- **Benchmark cases**: HHG-014 (analyst_request, shared device SM-G935F), HHG-004, HHG-005, HHG-017, HHG-020
- **Closed cases**: 9 undocumented cases all reference Samsung SM-G935F + anonymous proxy + 3 cardholders
- **Rule**: R6 (Shared origin)

### Path B: Out-of-Region Use
```
Customer → OWNS → Card → MADE → Transaction → BILLED_IN → BillingRegion (addr1 ≠ home)
                                                      ← BILLED_IN ← Transaction ← MADE ← Card ← OWNS ← Same Customer (home region)
```
- **Supported by**: 332 addr1 regions; customers with multiple addr1 (up to 53)
- **Pattern 4**: "Several days of purchases in one new region is a trip, not a clone"
- **Closed cases**: 955 out_of_region_use cases
- **Benchmark**: HHG-001 (addr1=444), HHG-007 (addr1=264), HHG-012 (addr1=494)

### Path C: Email Domain Clustering
```
Transaction → RECIPIENT_EMAIL → EmailDomain ← RECIPIENT_EMAIL ← Transaction (different card/customer)
```
- **Supported by**: Rule R6 mentions "same recipient email"
- **Evidence**: 60 recipient domains; but highly shared (gmail.com = 57K txns)
- **Usefulness**: Low specificity alone; combine with device/region

### Path D: Card Testing Sequence
```
Card → MADE → Transaction (small, online) → NEXT → Transaction (small, online) → NEXT → Transaction (small, online) → NEXT → Transaction (large, online)
```
- **Supported by**: Per-card `NEXT` edges with `time_delta_hours`, `amount_ratio`
- **Pattern 1**: "3+ tiny online authorizations under $5 within 1 hour, then larger purchase"
- **Closed cases**: 16 card_testing cases
- **Rule**: R5

### Path E: Historical Case Retrieval
```
BenchmarkCase → TRIGGERS → Transaction → FROM_DEVICE → DeviceProfile ← FROM_DEVICE ← Transaction ← INVOLVES ← ClosedCase
```
- **Supported by**: Device profiles link benchmark transactions to closed case transactions
- **GraphRAG**: Retrieve closed cases sharing device, region, or email with flagged transaction

### Path F: Account Takeover (Mixed Channel)
```
Card → MADE → Transaction (in_person) → NEXT → Transaction (online) [or vice versa]
With: DeviceProfile.newness=New, match_status anomalies
```
- **Pattern 5**: "Mixed-channel activity inconsistent with cardholder"
- **Closed cases**: 1,205 account_takeover cases
- **Signals**: Channel switch + new device + match flag anomalies

---

## Relationship Summary Table

| # | Source | Edge | Target | Cardinality | Key Attributes | TigerGraph | Critical For |
|---|--------|------|--------|-------------|----------------|------------|--------------|
| 1 | Customer | OWNS | Card | 13,553 | - | YES | Customer-centric queries |
| 2 | Card | MADE | Transaction | 590,742 | sequence_num | YES | Card history |
| 3 | Transaction | BILLED_IN | BillingRegion | ~525K | is_home_country | YES | Pattern 4, Rule R6 |
| 4 | Transaction | PURCHASER_EMAIL | EmailDomain | 496,262 | - | YES | Rule R6 (weak) |
| 5 | Transaction | RECIPIENT_EMAIL | EmailDomain | 137,453 | - | YES | Rule R6 |
| 6 | Transaction | FROM_DEVICE | DeviceProfile | 144,432 | newness, proxy, match_status | YES | Patterns 3,5, Rule R6 |
| 7 | Transaction | NEXT | Transaction | ~577K | time_delta, amount_ratio | YES | Pattern 1 (card testing) |
| 8 | ClosedCase | INVOLVES | Transaction | 14,955 (parsed) | is_first_fraud | YES | Case memory, GraphRAG |
| 9 | ClosedCase | ON_CARD | Card | 5,565 | - | YES | Card-level history |
| 10 | ClosedCase | CONNECTED_TO | Card | 92 (4 × 23) | connection_type | YES | Ring detection, Rule R6 |
| 11 | BenchmarkCase | TRIGGERS | Transaction | 20 | trigger_type, risk_score | YES | Agent entry point |

---

## Missing/Unverifiable Relationships

| Relationship | Reason |
|--------------|--------|
| Customer → LIVES_AT → Address | No address data beyond region/country |
| Transaction → AT_MERCHANT → Merchant | No merchant identifiers |
| Card → ISSUED_BY → Bank | Only issuer codes (card2,3,5), no bank entity |
| DeviceProfile → HAS_IP → IPAddress | Only proxy type, not actual IP |
| Customer → HAS_PHONE → Phone | Only count features (C1-C14) |

---

## Engineering Recommendations

1. **Edge Properties**: Store temporal attributes (`time_delta_hours`, `sequence_num`) on edges for efficient pattern queries
2. **Device Profile Specificity**: Add `specificity_score` to DeviceProfile vertex (inverse of customer_count) to weight evidence
3. **ClosedCase Parsing**: Parse `txn_ids` and `connected_card_ids` at load time into individual edges
4. **Card ID Mapping**: Build explicit mapping table `numeric_card1 ↔ benchmark_card_id` using `customer_id` as key
5. **Home Region**: Pre-compute each customer's primary `addr1` (mode) for out-of-region detection