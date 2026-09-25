# Data Validation Report — Graph-Ready Files

Generated: deterministic build from DATASET/ (no raw modification)

## Source Counts

- transactions.csv: 590,742 rows, 397 cols
- identity.csv: 144,432 rows
- closed_cases_history.csv: 5,565 rows
- case_pack.csv: 20 rows

## Expected Vertex Counts (source-derived)

| Vertex | Count | PK | Notes |
|--------|-------|----|-------|
| Customer | 13,553 | — | |
| Card | 13,553 | — | |
| Transaction | 590,742 | — | |
| DeviceProfile | 9,706 | — | |
| EmailDomain | 60 | — | |
| BillingRegion | 332 | — | |
| ClosedCase | 5,565 | — | |
| BenchmarkCase | 20 | — | |

## Expected Edge Counts (from produced CSVs)

| Edge | Count | Notes |
|------|-------|-------|
| OWNS | 13,553 | |
| MADE | 590,742 | |
| NEXT | 577,189 | |
| BILLED_IN | 525,003 | |
| PURCHASER_EMAIL | 496,262 | |
| RECIPIENT_EMAIL | 137,453 | |
| FROM_DEVICE | 144,432 | |
| INVOLVES | 14,955 | |
| ON_CARD | 5,565 | |
| CONNECTED_TO | 92 | |
| TRIGGERS | 20 | |

## Checks

- Duplicate TransactionIDs: PASS (0)
- Missing PKs (customer_id/card1): PASS
- Invalid timestamps: PASS
- Invalid categories (ProductCD): PASS
- Orphan identity records: 0 (expected: ~0; 6,640 online without identity is valid — those txns simply have no FROM_DEVICE edge)
- customer_id ↔ card1 1:1: PASS (13,553 each)
- Orphan edges in produced graph: PASS (0)

## Issues

None — all checks pass.

## Null / Timestamp / Numeric Handling

- Nulls: empty string in CSV for nullable string FKs (addr1, email, proxy, etc.); numeric nulls as empty; risk_score -1 sentinel for missing benchmark risk.
- Timestamp: `ts` preserved as original `YYYY-MM-DD HH:MM:SS` (DATETIME); `dt_seconds` as UINT.
- Ordering: all CSVs sorted deterministically by PK.
- Encoding: UTF-8, explicit headers, stable IDs.

## Provenance

| Graph object | Source file | Source identifier | Transformation |
|---|---|---|---|
| Customer | transactions.csv | customer_id | groupby aggregate |
| Card | transactions.csv + closed/case_pack card_id | customer_id + suffix | canonical CXXXX-KY via suffix_by_customer (see card_mapping.md) |
| Transaction | transactions.csv | TransactionID | direct + card_id join via customer_id |
| DeviceProfile | identity.csv | DeviceInfo+id_30+id_31+id_33 | SHA256 composite hash |
| EmailDomain | transactions.csv | P/R_emaildomain | distinct + counts |
| BillingRegion | transactions.csv | addr1 | distinct + mode country |
| ClosedCase | closed_cases_history.csv | case_id | direct + pipe-split edges |
| BenchmarkCase | case_pack.csv | case_id | direct |
| All edges | derived as above | — | see edge sections; no invented relationships |
