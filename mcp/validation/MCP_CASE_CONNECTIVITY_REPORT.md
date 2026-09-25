# MCP Case Connectivity — HHG-001..020 (spec §17)

Every benchmark case verified via `benchmark_case_context` (→ `benchmark_case_context.gsql` / file_fallback) — resolves BenchmarkCase → flagged transaction → customer/card context → related graph evidence. No final fraud verdicts.

Generated from `gen_mcp_validation.py` (file_fallback on `data/vertices/*.csv` + `data/edges/*.csv`, no live TigerGraph — `source.kind=file_fallback`).

| case_id | tool | result | evidence_count | latency_ms | status | notes |
|---------|------|--------|----------------|------------|--------|-------|
| HHG-001 | benchmark_case_context | success | card_history 200 (total 422, truncated true) | 3149.5 | PASS | in_person (addr 444.0, risk 0.61) — no device, region evidence |
| HHG-002 | benchmark_case_context | success | 44 (not truncated) | 704.9 | PASS | online risk 0.79, $292.36 — no identity in identity.csv (known missing edge) |
| HHG-003 | benchmark_case_context | success | 200 (truncated) | 1048.1 | PASS | C08623-K2 |
| HHG-004 | benchmark_case_context | success | 200 (truncated) | 732.7 | PASS | |
| HHG-005 | benchmark_case_context | success | 92 (not truncated) | 1035.7 | PASS | |
| HHG-006 | benchmark_case_context | success | 200 (truncated) | 1119.4 | PASS | |
| HHG-007 | benchmark_case_context | success | 200 (truncated) | 1105.2 | PASS | C09933-K2 |
| HHG-008 | benchmark_case_context | success | 200 (truncated) | 718.7 | PASS | C13171-K2 |
| HHG-009 | benchmark_case_context | success | 56 (not truncated) | 939.6 | PASS | |
| HHG-010 | benchmark_case_context | success | 36 (not truncated) | 923.3 | PASS | $1000 outlier |
| HHG-011 | benchmark_case_context | success | 200 (truncated) | 779.2 | PASS | C11923-K2 |
| HHG-012 | benchmark_case_context | success | 200 (truncated) | 1464.4 | PASS | C05876-K2 |
| HHG-013 | benchmark_case_context | success | 200 (truncated) | 1391.7 | PASS | C07671-K2 |
| HHG-014 | benchmark_case_context | success | 85 (not truncated) | 2314.6 | PASS | SM-G935F ring — surfaced 4 undocumented ClosedCases (CC-2649/2971/2985/3035) via device |
| HHG-015 | benchmark_case_context | success | 79 (not truncated) | 1286.7 | PASS | |
| HHG-016 | benchmark_case_context | success | 61 (not truncated) | 799.5 | PASS | |
| HHG-017 | benchmark_case_context | success | 59 (not truncated) | 1248.1 | PASS | IP_PROXY:HIDDEN |
| HHG-018 | benchmark_case_context | success | 200 (truncated) | 1120.3 | PASS | C02354-K2 |
| HHG-019 | benchmark_case_context | success | 200 (truncated) | 1153.0 | PASS | C07987-K2 |
| HHG-020 | benchmark_case_context | success | 112 (not truncated) | 1152.7 | PASS | C12265-K2 |

**Summary:** 20/20 cases `status=success` via MCP layer; each flagged Transaction exists (`hhg_fraud_graph` Transaction 590,742), its Card (CXXXX-KY via Q1 mapping) and Customer exist, `TRIGGERS` present, and graph traversals return card_history (+ device/regions/emails + related ClosedCases via file_fallback). For every case `BenchmarkCase → flagged transaction → customer/card context → related graph evidence` holds.

Spot checks (HHG-001 flagged 3514030):

| tool | result | latency | truncated |
|------|--------|---------|-----------|
| get_transaction | success | 584 ms | false |
| get_customer_history (C12382 limit 5) | success | 146 ms | true (422 total) |
| get_card_history (C12382-K1 limit 5) | success | 356 ms | true |
| find_device_connections (txn 3514030) | NOT_FOUND | 33 ms | — | in_person → no device (expected; generic valid device test PASSED) |
| get_temporal_chain (C12382-K1 limit 5) | success | 357 ms | true |
| calculate_exposure ([3514030]) | success | 122 ms | false |
| find_related_cases (card C12382-K1) | success | 3 ms | false |
| find_related_transactions (txn 3514030) | success | 796 ms | true |

Live execution: `PENDING_LIVE_EXECUTION` (`TG_HOST` not set — `LIVE_TIGERGRAPH_UNAVAILABLE` correctly reported; file_fallback validated). To verify live, set `TG_HOST/TG_GRAPHNAME/TG_USERNAME/TG_PASSWORD` and re-run `python gen_mcp_validation.py` or `python mcp/tests/test_connection.py`.
