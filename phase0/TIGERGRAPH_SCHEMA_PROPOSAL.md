# Phase 0 — TigerGraph Schema Proposal

> **Status**: PROPOSAL ONLY. Do not implement until Phase 0 is verified.
> Based on verified entities and relationships from `DATASET/README.md` Suggested Graph Schema (lines 167-182) + Phase 0 data analysis.

---

## Vertices

| Vertex | Primary Key | Attributes (selected) | Source |
|--------|-------------|-----------------------|--------|
| `Customer` | `customer_id` | total_txns, online_txns, in_person_txns, region_count, avg_amount, max_amount, first_ts, last_ts | transactions.csv |
| `Card` | `card_id` (benchmark `CXXXX-KY` form) | card1_numeric, customer_id, network (card4), card_type (card6), issuer codes (card2, card3, card5) | transactions.csv + case/closed-case card_id |
| `Transaction` | `TransactionID` | amount, ts, dt_seconds, channel, product_cd, risk_score, addr2, dist1, dist2, p_email, r_email, c1-c14, d1-d15, m1-m9, v-features (optional subset) | transactions.csv |
| `DeviceProfile` | composite hash (DeviceInfo\|OS\|browser\|screen) | device_type, device_info, os, browser, screen, newness (id_15), proxy_type (id_23), match_status (id_34), customer_count, card_count, txn_count, specificity | identity.csv |
| `EmailDomain` | `domain` (+ type) | customer_count, card_count, txn_count | transactions.csv |
| `BillingRegion` | `region_code` (addr1) | country_code (addr2), is_home_region, customer_count, card_count, txn_count | transactions.csv |
| `ClosedCase` | `case_id` | outcome, pattern, opened_at, closed_at, first_fraud_txn_id, n_txns, exposure_usd, actions_taken, report_filed, analyst_notes | closed_cases_history.csv |
| `BenchmarkCase` | `case_id` (HHG-XXX) | opened_at, trigger_type, trigger_text, risk_score, flagged_txn_id | case_pack.csv |

---

## Edges

| Edge | Source → Target | Cardinality | Edge Attributes | Purpose |
|------|-----------------|-------------|-----------------|---------|
| `OWNS` | Customer → Card | 13,553 | - | Customer-card ownership |
| `MADE` | Card → Transaction | 590,742 | sequence_num | Card transaction history |
| `NEXT` | Transaction → Transaction | ~577K | time_delta_hours, amount_ratio, channel_change | Per-card temporal sequence (card testing) |
| `BILLED_IN` | Transaction → BillingRegion | ~525K | is_home_country, channel | Out-of-region detection |
| `PURCHASER_EMAIL` | Transaction → EmailDomain | 496,262 | - | Shared email (R6) |
| `RECIPIENT_EMAIL` | Transaction → EmailDomain | 137,453 | - | Shared recipient email (R6) |
| `FROM_DEVICE` | Transaction → DeviceProfile | 144,432 | newness, proxy_type, match_status | Device linking (patterns 3, 5; R6) |
| `INVOLVES` | ClosedCase → Transaction | 14,955 (parsed) | is_first_fraud | Case→transaction evidence |
| `ON_CARD` | ClosedCase → Card | 5,565 | - | Case→card linkage |
| `CONNECTED_TO` | ClosedCase → Card | 92 (4 × 23) | connection_type | Connected-card rings (R6) |
| `TRIGGERS` | BenchmarkCase → Transaction | 20 | trigger_type, risk_score | Agent entry point |

---

## Design Decisions

1. **Card ID mapping**: Use benchmark `card_id` (`CXXXX-KY`) as Card PK for consistency with cases. Store numeric `card1` as attribute. Build mapping via `customer_id`.
2. **DeviceProfile as composite**: README suggests "DeviceProfile (DeviceInfo + OS + browser + screen)". Use composite hash as PK; add `customer_count`/`card_count`/`specificity` for evidence weighting.
3. **NEXT edges**: Only within-card ordering (README line 178: "order by ts within a card"). Enables card testing (R5) and burst detection.
4. **ClosedCase edges**: Parse `txn_ids` → `INVOLVES` edges; parse `connected_card_ids` → `CONNECTED_TO` edges at load time.
5. **Vector store**: Load closed-case narratives, README pattern section, policy, regulatory docs into TigerGraph vector search for GraphRAG (README line 182).
6. **Case memory**: Agent writes new cases as `ClosedCase`-like vertices (`written_to_graph`, `graph_case_id` like `CASE-2016-1187`) so future investigations find them.

---

## Candidate GSQL Investigations

1. **Transaction history**: `card_history(card_id, start_ts, end_ts)` — MADE traversal
2. **Customer/card history**: `customer_cards(customer_id)` — OWNS traversal
3. **Device reuse**: `device_neighbors(device_id)` — FROM_DEVICE reverse traversal
4. **Connection reuse**: `region_neighbors(region_code)` / `email_neighbors(domain)` — BILLED_IN / RECIPIENT_EMAIL reverse
5. **Multi-hop relationship investigation**: combined traversals across OWNS-MADE-FROM_DEVICE
6. **Related fraud cases**: ClosedCase connected via shared device/region/card
7. **Repeated/coordinated activity**: temporal+card grouping queries
8. **Pattern detection**: card_window for R5; region-new for pattern 4; channel-switch for pattern 5
9. **Exposure calculation**: sum(TransactionAmt) over affected_txn_ids
10. **Evidence retrieval**: vector KNN over embedded case narratives + policy docs

---

## Load Plan (Phase 2, not now)
1. Create schema (vertices + edges above)
2. Load transactions.csv → Customer, Card, Transaction, BillingRegion, EmailDomain
3. Join identity.csv on TransactionID → DeviceProfile + FROM_DEVICE edges
4. Load closed_cases_history.csv → ClosedCase + INVOLVES/ON_CARD/CONNECTED_TO
5. Load case_pack.csv → BenchmarkCase + TRIGGERS
6. Verify counts before loading agents