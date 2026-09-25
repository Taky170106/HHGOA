# PHASE 3 — GSQL Investigation Engine (TigerGraph Community Edition 4.2.5)

Project: **HHGoa 2026 — Agentic Fraud Investigation**
Scope of this document: the deterministic, read-only GSQL investigation layer.
Phase 2 (schema + data load) is unchanged and remains **PASS**.

---

## 0. Headline

| Metric | Result |
|---|---|
| Investigation query definitions | **10** |
| Queries that previously failed (HTTP 404) | **5** |
| Queries now compiling | **10 / 10** |
| Queries now installed (RESTPP) | **10 / 10** |
| Queries now executing with real data | **10 / 10** |
| HTTP 404 responses after repair | **0** |
| Benchmark cases verified (HHG-001…HHG-020) | **20 / 20** |
| Invalid / empty input handling | **5 / 5 graceful** |
| Read-only violations | **0** |
| Determinism (identical repeated runs) | **equivalent** |

`Q1_STATUS = RESOLVED`

---

## 1. Live-compiler evidence (the decisive finding)

The 5 failing queries all failed on the GSQL error

```
The query has mixed usage of v1 and v2 syntax.
```

Rather than trusting published TigerGraph documentation, the behaviour of the **live
4.2.5 compiler** was established empirically with isolated probe queries
(`tigergraph/queries/_probe_syntax*.gsql`). Every claim below is backed by a probe
that was compiled against the running instance.

| # | Fact established by the live compiler | Probe evidence |
|---|---|---|
| **F1** | Forward hop: `-(EDGE)-` and `-(EDGE)->` are **equivalent** and freely interchangeable in one query | `p3f_m1` OK, `p3f_m6` OK (dash + arrow in one query) |
| **F2** | Reverse hop: **`-(<-EDGE)-` is the only spelling that compiles** | `p3e_f5` OK, `p3k_k1` OK, `p3b_a2` OK |
| **F2x** | Rejected reverse spellings: `<-(EDGE)-`, `-(EDGE)<-`, `-(EDGE)-<`, `-(->EDGE)-`, `-(<-EDGE)->` | `p3a_r4`, `p3a_r3`, `p3b_a8`, `p3e_f1`, `p3f_m2` — all parse errors |
| **F3** | **A query may contain only forward hops *or* only reverse hops.** Mixing them anywhere in one query is rejected, independent of statement order, arrow form, edge aliases, or source-set reuse | `p3e_f3` (rev→fwd), `p3e_f4` (fwd→rev), `p3f_m4` (`-(<-e)-` + `-(e)->`), `p3f_m5` (`-(<-e)-` + `-(e)-`), `p3k_k5` (edge aliases), `p3k_k7` (different source sets) — **all rejected** |
| **F4** | A chained multi-hop path inside one `FROM` clause is rejected; split into single-hop `SELECT`s (identical vertex set) | `p3b_b1`, `p3c_q4/q5/q6`, `p3e_f6` rejected; `p3c_q7` (split) OK |
| **F5** | `SELECT` may return the **source alias** of a forward hop → a reverse hop is expressible forward-only as `SELECT x FROM AllX:x -(E)-> Y:y WHERE y.pk IN {ids}` | `p3k_k3`, `p3k_k4` compiled **and run**: returned card `C12382-K1` for txn `3514030` |
| **F6** | A `@@` global accumulator cannot be a `FROM` source (TYP-152); re-materialise ids into a typed local set with `WHERE pk IN @@ids` | `p3b_c1` OK, runtime verified by `p3k_k4` |
| **F7** | `@@acc += <vertex set>` is rejected in **every** form (TYP-500). The accumulator must be filled with `ACCUM @@acc += <vertex>` inside a `SELECT` | `p3m_m1`, `p3m_m3`, `p3m_m5` rejected; `p3m_m2`, `p3m_m4` OK |
| **F8** | `LIMIT <local variable>` is accepted; `CONCAT()` does **not** exist — use `+` for string concatenation | `p3n_l1` OK; `p3j_concat` TYP-1002, `p3j_concat2` OK |

### 1.1 Why this forced a repair strategy

Because of **F3**, no query in this schema can use both a reverse hop and a forward
hop — and every one of the 5 queries needs both (e.g. `get_transaction` needs
`Transaction → Card` (reverse `MADE`) *and* `Transaction → DeviceProfile`
(forward `FROM_DEVICE`)).

**Repair applied:** every reverse hop was rewritten as a **forward-only inverted
traversal** (F5). For a declared edge `E : X → Y`, the reverse hop
`Y -(<-E)- X` is replaced by

```gsql
SELECT x FROM AllX:x -(E)-> Y:y WHERE y.<primary_key> IN @@ids_of_Y
```

This returns **exactly the same vertex set** — it is the same edge read from the
other end — so investigation behaviour, output keys and semantics are unchanged.
Only the direction written in the GSQL text changed. No schema, no data, no
parameter semantics were altered.

For hops where the target vertex already carries the join key as an attribute
(e.g. `Transaction.card_id`, `ClosedCase.card_id`) the same idea applies with an
attribute filter instead of an edge scan.

`ORIGINAL_QUERY_STATUS = REPAIRED_IN_PLACE` (no query was replaced by a
simplified stub; all keep their original parameters and output keys)
`FALLBACK_IMPLEMENTATION = NOT_USED` for the five mandatory capabilities.

---

## 2. Query catalogue

### Q1 — `get_transaction`

| Field | Value |
|---|---|
| Source | `tigergraph/queries/get_transaction.gsql` |
| Purpose | Transaction + directly connected 1-hop context |
| Parameters | `txn_id STRING` |
| Traversal | seed filter → inverted `MADE` (card) → inverted `OWNS` (customer); forward `FROM_DEVICE`, `BILLED_IN`, `PURCHASER_EMAIL`, `RECIPIENT_EMAIL`, `NEXT`; inverted `NEXT` (previous txn) |
| Output keys | `T, CardOwners, Customers, Devices, Regions, PEmails, REmails, NextTxns, PrevTxns` |
| Edges | MADE*, OWNS*, FROM_DEVICE, BILLED_IN, PURCHASER_EMAIL, RECIPIENT_EMAIL, NEXT* (* = inverted) |
| Safety | single-vertex seed, no multi-hop expansion, no writes |
| Compile | **SUCCESS** |
| Install | **installed v2** |
| Execute | **HTTP 200**, 93 ms |
| Test | txn `3000120` → 1 txn, 1 card, 1 customer, 1 device |
| Invalid input | `txn_id=""` / `999999999` → `NOT_FOUND`, HTTP 200 |

### Q2 — `find_related_transactions`

| Field | Value |
|---|---|
| Source | `tigergraph/queries/find_related_transactions.gsql` |
| Purpose | Related transactions via shared card / region / device / email |
| Parameters | `txn_id, card_id, customer_id STRING`, `max_depth UINT`, `max_results UINT` |
| Traversal | seed (forward) → re-materialise seeds → 5 bounded relationship expansions (2 hops max) |
| Output keys | `@@seedTxns, ViaCard, ViaRegion, ViaDevice, ViaPEmail, ViaREmail` |
| Edges | MADE*, OWNS, BILLED_IN*, FROM_DEVICE*, PURCHASER_EMAIL*, RECIPIENT_EMAIL* |
| Safety | **bounded**: `max_depth=1` stops at the seed set; `max_depth>=2` performs exactly one relationship expansion (natural maximum = 2 edge hops); every result set `LIMIT`-ed (`max_results`, 0 ⇒ default 500). No recursive traversal. |
| Compile | **SUCCESS** |
| Install | **installed v2** |
| Execute | **HTTP 200**, 149–164 ms |
| Test | card `C00259-K1` depth 2 limit 50 → 60 seeds, ViaCard 50, ViaRegion 50, ViaDevice 50 |
| Invalid input | all-empty → `NO_SEED`, HTTP 200 |

> **Note.** The unbounded form of this query over-produced (shared email/region
> domains return hundreds of thousands of transactions) and exceeded the RESTPP
> request timeout with **HTTP 408 at ~16 s**. Bounding was therefore required by
> Phase 3 §12 (performance) and §4 Q2 (depth + result limit), not by the compiler.

### Q3 — `find_device_connections`

| Field | Value |
|---|---|
| Source | `tigergraph/queries/find_device_connections.gsql` |
| Purpose | Other transactions / cards / customers sharing the same `DeviceProfile` |
| Parameters | `txn_id, device_profile_id STRING` (supply one) |
| Traversal | forward `FROM_DEVICE` (or device filter) → inverted `FROM_DEVICE` (device → txns) → inverted `MADE` → inverted `OWNS` |
| Output keys | `@@devices, LinkedTxns, LinkedCards, LinkedCustomers` |
| Edges | FROM_DEVICE*, MADE*, OWNS* |
| Safety | bounded to one device's edge neighbourhood; read-only |
| Compile | **SUCCESS** |
| Install | **installed v2** |
| Execute | **HTTP 200**, 62–86 ms |
| Test | device `DP-2be871a3adbe7b2d` → 1 device, 5 txns, 5 cards, 5 customers |
| Invalid input | `NO_DEVICE_FOUND`, HTTP 200 |

### Q4 — `find_related_cases`

| Field | Value |
|---|---|
| Source | `tigergraph/queries/find_related_cases.gsql` |
| Purpose | Historical `ClosedCase` records reachable from the supplied entities |
| Parameters | `txn_id, card_id, customer_id, device_profile_id, region_code, domain STRING` |
| Traversal | forward `OWNS`; inverted `INVOLVES`, `ON_CARD`, `CONNECTED_TO`, `FROM_DEVICE`, `BILLED_IN`, `PURCHASER_EMAIL`, `RECIPIENT_EMAIL` |
| Output keys | `@@seedCases` |
| Edges | INVOLVES*, ON_CARD*, CONNECTED_TO*, FROM_DEVICE*, BILLED_IN*, PURCHASER_EMAIL*, RECIPIENT_EMAIL*, OWNS, MADE |
| Safety | bounded: each branch is a single relationship expansion, no recursion |
| Compile | **SUCCESS** |
| Install | **installed v2** |
| Execute | **HTTP 200**, 10–59 ms |
| Test | card `C00259-K1` → 7 cases; customer → 7; region → 12; domain → 8; txn `3000120` → 1 |
| Invalid input | all-empty → `@@seedCases: []`, HTTP 200 |

Every returned case is reached through a real `INVOLVES` / `ON_CARD` /
`CONNECTED_TO` edge — no historical relationship is invented.

### Q5 — `benchmark_case_context`

| Field | Value |
|---|---|
| Source | `tigergraph/queries/benchmark_case_context.gsql` |
| Purpose | Full investigation context for a benchmark case |
| Parameters | `case_id STRING` (`HHG-001` … `HHG-020`) |
| Traversal | `BenchmarkCase -TRIGGERS-> Transaction` (forward, untouched) → inverted `MADE`/`OWNS` → forward context (device/region/email/card history) → inverted `INVOLVES`/`ON_CARD`/`NEXT` for historical evidence and temporal neighbours |
| Output keys | `B, Flagged, FlaggedCards, FlaggedCustomer, CardHistory, Devices, Regions, PEmails, REmails, RelatedViaDevice, RelatedViaRegion, RelatedViaCard, NextTx, PrevTx` |
| Edges | TRIGGERS, MADE*, OWNS*, FROM_DEVICE, BILLED_IN, PURCHASER_EMAIL, RECIPIENT_EMAIL, INVOLVES*, ON_CARD*, NEXT* |
| Safety | single benchmark case, bounded expansions, read-only |
| Compile | **SUCCESS** |
| Install | **installed v2** |
| Execute | **HTTP 200**, 129–433 ms |
| Benchmark | **20/20** — every case returned exactly its `flagged_txn_id` |
| Invalid input | `HHG-999` → `BENCHMARK_NOT_FOUND`, HTTP 200 |

### Q6/Q7/Q8 — previously-installed queries (re-validated)

| Query | File | Parameters | Compile | Install | Execute |
|---|---|---|---|---|---|
| `get_card_history` | `get_card_history.gsql` | `card_id` | OK | installed v2 | HTTP 200, 19 ms → 60 txns, 59 NEXT edges |
| `get_customer_history` | `get_customer_history.gsql` | `customer_id` | OK | installed v2 | HTTP 200, 13 ms |
| `temporal_chain` | `temporal_chain.gsql` | `card_id` | OK | installed v2 | HTTP 200, 19 ms |

### Analytics (`calculate_exposure`, `calculate_exposure_list`)

| Query | Purpose | Install | Execute |
|---|---|---|---|
| `calculate_exposure` | Deterministic exposure total over a CSV of txn ids | installed v2 | HTTP 200, 6 ms |
| `calculate_exposure_list` | Same, over a `set<string>` | installed v2 | HTTP 200 (param `txn_ids`) |

**Analytics evaluated against the real data**

| Candidate analytic | Meaningful on this schema? | Evidence |
|---|---|---|
| Transaction degree / connectivity | **Yes** — `NEXT` in/out degree is directly materialised | `get_transaction` returns `NextTxns` / `PrevTxns` |
| Shared-device connectivity | **Yes** — 144,432 `FROM_DEVICE` edges | `find_device_connections`: 1 device → 5 txns / 5 cards / 5 customers |
| Shared-email connectivity | **Yes** — 496,262 `PURCHASER_EMAIL`, 137,453 `RECIPIENT_EMAIL` | `find_related_transactions.ViaPEmail/ViaREmail` |
| Transaction neighbourhood | **Yes** — 1-hop entities + 2-hop context | `get_transaction` + `find_related_transactions` |
| Bounded multi-hop paths | **Yes** — depth/limit bounded | `find_related_transactions(max_depth, max_results)` |
| Historical-case connectivity | **Yes** — 14,955 `INVOLVES`, 5,565 `ON_CARD`, 92 `CONNECTED_TO` | `find_related_cases`, `RelatedVia*` |
| Txn-to-txn relationship patterns | **Yes** — 577,189 `NEXT` edges | `temporal_chain`, `NextTx`/`PrevTx` |
| Amount/statistical (non-graph) features | **No** — not graph structure; belongs to the ML layer | deferred, not faked |

### Graph-path explanation data (Phase 3 §6)

Traversal results carry, for every hop, the **source id, destination id, vertex type
and edge type** (each printed key names the vertex type, and the edge used to reach
it is fixed per key and documented above). Depth is bounded and explicit
(`max_depth`, plus the fixed 1-hop / 2-hop structure of each expansion). This is the
raw material for the later XAI layer — **no Graph XAI is implemented here.**

---

## 3. Read-only / security

Every one of the 10 queries contains only `SELECT`, `IF`, `ACCUM`, `PRINT`, and
local vertex-set assignments. Grep-verified: **no `INSERT`, `UPDATE`, `DELETE`,
`CREATE VERTEX/EDGE`, `DROP DATA`, or loading job** appears in any
`tigergraph/queries/*.gsql` file. No query accepts a user-controlled GSQL string.
No benchmark, customer, transaction or card record is modified.

## 4. Performance

| Query | Representative execution time |
|---|---|
| `calculate_exposure` | 5.7 ms |
| `find_related_cases` | 10 – 59 ms |
| `get_customer_history` | 13 ms |
| `get_card_history` / `temporal_chain` | 19 ms |
| `get_transaction` | 88 – 93 ms |
| `find_device_connections` | 62 – 86 ms |
| `find_related_transactions` (depth 2, limit 50) | 149 – 164 ms |
| `benchmark_case_context` (all 20 cases) | 129 – 433 ms (mean ≈ 185 ms) |

The only performance defect found was the unbounded `find_related_transactions`
(HTTP 408 @ ~16 s); it is now depth- and limit-bounded (§Q2).

## 5. Files

**Created / rewritten by Phase 3**

- `tigergraph/queries/get_transaction.gsql`
- `tigergraph/queries/find_related_transactions.gsql`
- `tigergraph/queries/find_device_connections.gsql`
- `tigergraph/queries/find_related_cases.gsql`
- `tigergraph/queries/benchmark_case_context.gsql`
- `tigergraph/scripts/phase3a_compile.sh`, `phase3a_install.sh`, `phase3a_full_errors.sh`,
  `phase3a_reinstall_frt.sh`
- `tigergraph/scripts/phase3_validate.py`, `phase3_e2e_path.py`, `phase3a_execute.py`
- `docs/PHASE3_GSQL_INVESTIGATION.md`, `docs/PHASE3_QUERY_CATALOG.json`
- `tigergraph/validation/phase3_validation.json`, `phase3_e2e_path.json`

**Probe files (diagnostic only, queries dropped from the catalog)**
`tigergraph/queries/_probe_syntax.gsql` … `_probe_syntax11.gsql`

**Untouched:** `DATASET/`, `data/`, `tigergraph/schema/schema.gsql`, all loaders,
all Phase 2 evidence files.
