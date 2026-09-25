# Phase 0 — Data Dictionary

## Field Classification Legend
- **Raw**: Direct from dataset files
- **Derived**: Computed during analysis (not in raw files)
- **Benchmark**: From case_pack.csv or closed_cases_history.csv
- **Model-generated**: Would be produced by agent/ML (not in source data)

---

## transactions.csv Fields (397 columns)

### Core Identifiers
| Field | Type | Nullable | Cardinality | Semantic | Role | TigerGraph Vertex Attr | TigerGraph Edge Attr | Evidence Only |
|-------|------|----------|-------------|----------|------|------------------------|---------------------|---------------|
| TransactionID | int64 | No | 590,742 | Unique transaction ID | PK | Transaction.id | - | - |
| customer_id | string | No | 13,553 | Customer identifier | FK → Customer | Customer.id | - | - |
| card1 | int64 | No | 13,553 | Primary card number (numeric) | FK → Card | Card.id (numeric) | MADE.card1 | - |
| card2-card6 | mixed | Yes | Various | Card details (issuer, network, type) | Card attributes | Card.network, Card.type | - | - |

### Transaction Core
| Field | Type | Nullable | Cardinality | Semantic | Role | TigerGraph Vertex Attr | TigerGraph Edge Attr | Evidence Only |
|-------|------|----------|-------------|----------|------|------------------------|---------------------|---------------|
| TransactionDT | int64 | No | ~180K | Seconds from dataset start (Jul 2) | Temporal | Transaction.dt_seconds | - | - |
| TransactionAmt | float64 | No | Continuous | USD amount | Amount | Transaction.amount | - | - |
| ProductCD | string | No | 5 (W,C,H,R,S) | Product code; W=in_person | Channel indicator | Transaction.channel | - | - |
| channel | string | No | 2 | Derived: in_person/online | Channel | Transaction.channel | - | - |
| ts | string | No | ~180K | Real timestamp YYYY-MM-DD HH:MM:SS | Temporal | Transaction.timestamp | - | - |
| risk_score | float64 | No | Continuous | Bank model score 0-1 | Risk signal | Transaction.risk_score | - | - |

### Billing Geography
| Field | Type | Nullable | Cardinality | Semantic | Role | TigerGraph Vertex Attr | TigerGraph Edge Attr | Evidence Only |
|-------|------|----------|-------------|----------|------|------------------------|---------------------|---------------|
| addr1 | float64 | Yes (65,739) | 332 | Billing region code | FK → BillingRegion | BillingRegion.code | BILLED_IN.addr1 | - |
| addr2 | float64 | Yes (65,739) | ~60 | Billing country code (87=home) | Country | Transaction.addr2 | - | - |
| dist1, dist2 | float64 | Yes | Continuous | Distances between unnamed points | Geography signal | Transaction.dist1/2 | - | Yes |

### Email Domains
| Field | Type | Nullable | Cardinality | Semantic | Role | TigerGraph Vertex Attr | TigerGraph Edge Attr | Evidence Only |
|-------|------|----------|-------------|----------|------|------------------------|---------------------|---------------|
| P_emaildomain | string | Yes | 59 | Purchaser email domain | FK → EmailDomain | EmailDomain.domain | PURCHASER_EMAIL.domain | - |
| R_emaildomain | string | Yes | 60 | Recipient email domain | FK → EmailDomain | EmailDomain.domain | RECIPIENT_EMAIL.domain | - |

### Count Features (C1-C14)
| Field | Type | Nullable | Range | Semantic | Role | TigerGraph Vertex Attr | TigerGraph Edge Attr | Evidence Only |
|-------|------|----------|-------|----------|------|------------------------|---------------------|---------------|
| C1-C14 | float64 | No | 0-5691 | Counts: addresses, phones, etc. per card | Behavioral counts | Transaction.c1-c14 | - | Yes |

### Time Delta Features (D1-D15)
| Field | Type | Nullable | Range | Semantic | Role | TigerGraph Vertex Attr | TigerGraph Edge Attr | Evidence Only |
|-------|------|----------|-------|----------|------|------------------------|---------------------|---------------|
| D1-D15 | float64 | Yes | -193 to 879 | Days since previous events | Temporal patterns | Transaction.d1-d15 | - | Yes |

### Match Flags (M1-M9)
| Field | Type | Nullable | Values | Semantic | Role | TigerGraph Vertex Attr | TigerGraph Edge Attr | Evidence Only |
|-------|------|----------|--------|----------|------|------------------------|---------------------|---------------|
| M1-M3, M5-M9 | string | No | T/F | Match flags (name, address, etc.) | Identity verification | Transaction.m1-m9 | - | Yes |
| M4 | string | No | M0/M1/M2 | Match category | Identity category | Transaction.m4 | - | Yes |

### Vesta Engineered Features (V1-V339)
| Field | Type | Nullable | Range | Semantic | Role | TigerGraph Vertex Attr | TigerGraph Edge Attr | Evidence Only |
|-------|------|----------|-------|----------|------|------------------------|---------------------|---------------|
| V1-V339 | float64 | No | Various | Ranking, counting, relationship features | ML signals | Transaction.v1-v339 | - | Yes (as signals) |

---

## identity.csv Fields (41 columns)

### Join Key
| Field | Type | Nullable | Cardinality | Semantic | Role | TigerGraph Vertex Attr | TigerGraph Edge Attr | Evidence Only |
|-------|------|----------|-------------|----------|------|------------------------|---------------------|---------------|
| TransactionID | int64 | No | 144,432 | Links to transactions.csv | FK → Transaction | - | FROM_DEVICE.txn_id | - |

### Device Profile
| Field | Type | Nullable | Cardinality | Semantic | Role | TigerGraph Vertex Attr | TigerGraph Edge Attr | Evidence Only |
|-------|------|----------|-------------|----------|------|------------------------|---------------------|---------------|
| DeviceType | string | No | 2 | mobile/desktop | Device class | DeviceProfile.type | - | - |
| DeviceInfo | string | Yes | ~10K | Device model string (e.g., SAMSUNG SM-G935F) | Device identity | DeviceProfile.info | - | - |

### Encoded Ratings (id_01-id_11)
| Field | Type | Nullable | Semantic | Role | TigerGraph Vertex Attr | Evidence Only |
|-------|------|----------|----------|------|------------------------|---------------|
| id_01-id_11 | float64 | Yes | Device rating, IP-domain rating, proxy rating, login counts, time on page | Risk signals | DeviceProfile.id_01-id_11 | Yes |

### Categorical Identity (id_12-id_38)
| Field | Type | Nullable | Key Values | Semantic | Role | TigerGraph Vertex Attr | Evidence Only |
|-------|------|----------|------------|----------|------|------------------------|---------------|
| id_15 | string | Yes | New/Found/Unknown | Device newness for account | DeviceProfile.newness | - |
| id_23 | string | Yes | IP_PROXY:TRANSPARENT/ANONYMOUS/HIDDEN | Proxy type | DeviceProfile.proxy_type | - |
| id_30 | string | Yes | 75 unique | OS | DeviceProfile.os | - |
| id_31 | string | Yes | 130 unique | Browser | DeviceProfile.browser | - |
| id_33 | string | Yes | 260 unique | Screen resolution | DeviceProfile.screen | - |
| id_34 | string | Yes | match_status:0/1/2/-1 | Match status | DeviceProfile.match_status | - |
| id_12-14,16-22,24-29,32,35-38 | mixed | Yes | Various | Other categorical | DeviceProfile.id_XX | Yes |

---

## closed_cases_history.csv Fields (15 columns)

| Field | Type | Nullable | Cardinality | Semantic | Role | TigerGraph Vertex Attr | TigerGraph Edge Attr | Evidence Only |
|-------|------|----------|-------------|----------|------|------------------------|---------------------|---------------|
| case_id | string | No | 5,565 | Closed case ID (CC-XXXX) | PK | ClosedCase.id | - | - |
| customer_id | string | No | 1,892 | Customer involved | FK → Customer | - | INVOLVES.customer | - |
| card_id | string | No | 1,913 | Card involved (CXXXX-KY) | FK → Card | - | ON_CARD.card | - |
| opened_at | datetime | No | - | Case opened timestamp | Temporal | ClosedCase.opened_at | - | - |
| closed_at | datetime | No | - | Case closed timestamp | Temporal | ClosedCase.closed_at | - | - |
| outcome | string | No | 2 | confirmed_fraud / cleared | Verdict | ClosedCase.outcome | - | - |
| pattern | string | No | 7 | Fraud pattern or none/undocumented | Pattern label | ClosedCase.pattern | - | - |
| first_fraud_txn_id | int64 | Yes | - | First fraudulent transaction | FK → Transaction | - | INVOLVES.first_txn | - |
| txn_ids | string | Yes | - | Pipe-separated transaction IDs | Evidence links | - | INVOLVES.txn_list | - |
| n_txns | int64 | No | - | Count of fraudulent transactions | Count | ClosedCase.n_txns | - | - |
| exposure_usd | float64 | No | 0-35K | Sum of fraudulent amounts | Financial | ClosedCase.exposure | - | - |
| connected_card_ids | string | Yes | - | Pipe-separated related cards | Network links | - | CONNECTED_TO.cards | - |
| actions_taken | string | No | - | Pipe-separated policy actions | Actions | ClosedCase.actions | - | - |
| report_filed | string | No | 2 | Yes/No | SAR flag | ClosedCase.report_filed | - | - |
| analyst_notes | string | No | - | Narrative explanation | Evidence | ClosedCase.notes | - | Yes |

---

## case_pack.csv Fields (8 columns)

| Field | Type | Nullable | Cardinality | Semantic | Role | TigerGraph Vertex Attr | Evidence Only |
|-------|------|----------|-------------|----------|------|------------------------|---------------|
| case_id | string | No | 20 | Benchmark case ID (HHG-XXX) | PK | - | - |
| opened_at | datetime | No | 20 | Alert timestamp | Temporal | - | - |
| trigger_type | string | No | 3 | risk_score / customer_report / analyst_request | Trigger | - | - |
| trigger_text | string | No | 20 | Human-readable trigger description | Context | - | Yes |
| flagged_txn_id | int64 | No | 20 | Transaction that triggered alert | FK → Transaction | - | - |
| card_id | string | No | 20 | Card in CXXXX-KY format | FK → Card | - | - |
| customer_id | string | No | 20 | Customer identifier | FK → Customer | - | - |
| risk_score | float64 | Yes (8) | 11 values | Model score (only for risk_score trigger) | Risk signal | - | - |

---

## Derived Fields (Not in Raw Data)

| Field | Source | Type | Purpose |
|-------|--------|------|---------|
| device_profile | DeviceInfo \| OS \| browser \| screen | string | Composite device fingerprint for linking |
| card_id_mapped | customer_id + card1 → CXXXX-KY | string | Bridge between transaction card1 and case/closed case card_id |
| transaction_sequence | Per-card ts ordering | int | Position in card's transaction history |
| time_since_prev_txn | D1/D15 or computed | float | Hours/days since previous transaction on same card |
| fraud_probability | Agent output | float | Agent's assessed probability (0-1) |
| pattern | Agent output | enum | One of 5 documented + undocumented + none |
| exposure_usd | Agent output | float | Sum of identified fraudulent transaction amounts |

---

## Key Cardinalities Summary

| Entity | Count | Notes |
|--------|-------|-------|
| Customers | 13,553 | 1:1 with card1 in transactions |
| Cards (numeric) | 13,553 | card1 field |
| Cards (benchmark format) | ~1,913 | CXXXX-KY format in cases |
| Transactions | 590,742 | All unique TransactionIDs |
| Online Transactions | 151,072 | 25.6% |
| In-Person Transactions | 439,670 | 74.4% |
| Device Profiles (composite) | 9,706 | DeviceInfo+OS+browser+screen |
| Device Profiles shared (>1 cust) | 4,789 | Many are generic (Windows/Chrome) |
| Closed Cases | 5,565 | Jul-Nov 2016 |
| Confirmed Fraud Cases | 4,665 | 83.8% |
| Cleared Cases | 900 | 16.2% |
| Benchmark Cases | 20 | Nov-Dec 2016 |
| Billing Regions (addr1) | 332 | 65K nulls |
| Email Domains | 59/60 | Purchaser/Recipient |