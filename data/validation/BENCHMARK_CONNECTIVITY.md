# Benchmark Case Connectivity — Graph Resolvability (20/20)

Generated via `tigergraph/validation/validate_graph.py` — all checks against produced CSVs.

| case_id | flagged_txn_id | card_id | customer_id | txn exists | card exists | txn customer matches pack | txn card matches pack | TRIGGERS edge | graph_resolvable | missing_relationships |
|---------|----------------|---------|-------------|------------|-------------|---------------------------|-----------------------|---------------|------------------|-----------------------|
| HHG-001 | 3514030 | C12382-K1 | C12382 | YES | YES | YES | YES | YES | YES | none |
| HHG-002 | 3478782 | C11891-K1 | C11891 | YES | YES | YES | YES | YES | YES | none |
| HHG-003 | 3530164 | C08623-K2 | C08623 | YES | YES | YES | YES | YES | YES | none |
| HHG-004 | 3583227 | C08106-K1 | C08106 | YES | YES | YES | YES | YES | YES | none |
| HHG-005 | 3523199 | C02923-K1 | C02923 | YES | YES | YES | YES | YES | YES | none |
| HHG-006 | 3476682 | C07297-K1 | C07297 | YES | YES | YES | YES | YES | YES | none |
| HHG-007 | 3514948 | C09933-K2 | C09933 | YES | YES | YES | YES | YES | YES | none |
| HHG-008 | 3558054 | C13171-K2 | C13171 | YES | YES | YES | YES | YES | YES | none |
| HHG-009 | 3581141 | C08299-K1 | C08299 | YES | YES | YES | YES | YES | YES | none |
| HHG-010 | 3506725 | C10434-K1 | C10434 | YES | YES | YES | YES | YES | YES | none |
| HHG-011 | 3583368 | C11923-K2 | C11923 | YES | YES | YES | YES | YES | YES | none |
| HHG-012 | 3553342 | C05876-K2 | C05876 | YES | YES | YES | YES | YES | YES | none |
| HHG-013 | 3526826 | C07671-K2 | C07671 | YES | YES | YES | YES | YES | YES | none |
| HHG-014 | 3478561 | C13487-K1 | C13487 | YES | YES | YES | YES | YES | YES | none |
| HHG-015 | 3464869 | C03042-K1 | C03042 | YES | YES | YES | YES | YES | YES | none |
| HHG-016 | 3534820 | C09988-K1 | C09988 | YES | YES | YES | YES | YES | YES | none |
| HHG-017 | 3450629 | C04570-K1 | C04570 | YES | YES | YES | YES | YES | YES | none |
| HHG-018 | 3491361 | C02354-K2 | C02354 | YES | YES | YES | YES | YES | YES | none |
| HHG-019 | 3503878 | C07987-K2 | C07987 | YES | YES | YES | YES | YES | YES | none |
| HHG-020 | 3509359 | C12265-K2 | C12265 | YES | YES | YES | YES | YES | YES | none |

**Summary**: 20/20 cases fully resolvable — every flagged transaction joins to its card (MADE), customer (OWNS+MADE), and has a TRIGGERS edge from its BenchmarkCase. Additional 1-hop entities (device/region/email) available per transaction for investigation (see `benchmark_case_context` query).
