# Phase 2 — Final Report: TigerGraph MCP + Controlled Investigation Tool Interface

**Project:** TigerGraph × Hacker House Goa 2026 — Agentic Fraud Investigation
**Graph:** `hhg_fraud_graph` (8 vertices, 11 edges, 2,499,760 edges, 20 BenchmarkCases — `tigergraph/schema/schema.gsql`, `tigergraph/validation/GRAPH_VALIDATION_REPORT.md`)
**Phase 1 status:** 13,553 Customer / 13,553 Card / 590,742 Transaction / 9,706 DeviceProfile / 60 EmailDomain / 332 BillingRegion / 5,565 ClosedCase / 20 BenchmarkCase, 0 duplicate PKs, 0 orphans, 9/9 GSQL queries authored; live TigerGraph execution pending.
**Phase 2 objective:** Official TigerGraph MCP → controlled read-only fraud-investigation tool interface (no LangGraph/LLM/GraphRAG/XAI/case-generation yet).
**Date:** 2026-09-23

---

## 1. MCP Architecture

```
TigerGraph (hhg_fraud_graph, Savanna or Community 4.1+, GSQL 3.x, 9 installed queries)
    ↓
Official TigerGraph MCP (tigergraph-mcp, 69 tools, read-only 37, stdio + streamable-http, TG_* env)
    ↓
Our controlled layer (mcp/tools/*, 9 read-only tools → 9 GSQL queries, allowlist + validation + file_fallback)
    ↓
Future LangGraph agent (Phase 3+, MCP tool discovery, MCP SDK / LangChain adapters)
```

*No business-logic duplication:* TigerGraph/GSQL remains source of truth; `mcp/tools` only mirrors traversals via minimal pandas joins on `data/vertices/*.csv` + `data/edges/*.csv` when live is unavailable. Spec §21.

**Project structure (spec §3):**
```
mcp/
  README.md, .env.example, config/tool_policy.yaml,
  schemas/tool_schemas.py,
  tools/{investigation_tools.py, case_tools.py, transaction_tools.py, relationship_tools.py, history_tools.py, _common.py, logging.py},
  tests/{test_connection.py, test_tools.py, test_security.py},
  validation/{MCP_VALIDATION_REPORT.md, MCP_CASE_CONNECTIVITY_REPORT.md}
phase2/PHASE2_FINAL_REPORT.md (this file)
```

Official package not duplicated inside repo; only project-specific wrappers/config.

## 2. Official TigerGraph MCP Version Used

- **Package:** `tigergraph-mcp` 0.1.0+ (PyPI `tigergraph-mcp`, installed via `pip install tigergraph-mcp`; repo https://github.com/tigergraph/tigergraph-mcp, inspected 2026-09-23; CHANGELOG shows initial public release).
- **Python:** 3.10–3.14 (this env 3.13.4; `mcp` package import attempted — offline env shows `No module named 'mcp'` until `pip install mcp` / `tigergraph-mcp`; our layer degrades gracefully to file_fallback).
- **TigerGraph:** 4.1+ required (4.2+ recommended for TigerVector); our schema/queries target 3.x/4.x GSQL on `hhg_fraud_graph`.
- **Dependencies installed by official package:** `pyTigerGraph>=2.0.4`, `mcp>=1.0.0`, `pydantic>=2.0.0`, `click`, `python-dotenv`; HTTP needs `uvicorn starlette`; LLM generation needs `tigergraph-mcp[llm]`.
- **Tool inventory upstream:** 69 tools (`37 read-only` via `--allowed-tools read-only`), categories `schema, data, query, vector, loading, utility, discovery`, supports `--allowed-tools`/`--blocked-tools` (comma-separated) and `X-TG-Tools` per-session narrowing, logging via `TG_LOG_TOOL_CALLS` + `TG_LOG_CALLER_IDENTITY`.

Documented in `mcp/README.md` §3/§4 and `mcp/config/tool_policy.yaml` header.

## 3. TigerGraph Version (if known)

- **Required downstream:** TigerGraph 4.1+ (Savanna or Community 3.9+ for local dev). No live instance was reachable in this offline environment, so exact server version is `PENDING_LIVE_EXECUTION` — will be recorded via `GET /version` / `gsql SHOW VERSION` on first live connection. Our GSQL (`tigergraph/schema/schema.gsql`, `tigergraph/queries/*.gsql`) is 3.x-compatible.

## 4. Transport Used

Both transports supported as per spec §13:

- **Preferred for dev:** `stdio` (default) — `tigergraph-mcp` over stdin/stdout, client spawns subprocess, env via `.env` or `env` map; `tigergraph-mcp --env-file .env -v`.
- **Deployment:** `streamable-http` (or legacy `sse`) — `tigergraph-mcp --transport streamable-http --host 0.0.0.0 --port 8000 --env-file /etc/tigergraph-mcp/.env`, URL `http://host:8000/mcp/` (trailing slash), clients send `X-TG-*` headers (`X-TG-Profile`, `X-TG-Host`, `X-TG-Username`/`Password`/`Api-Token`, etc.), isolation per session. Must be behind reverse proxy/API gateway for TLS and access control; never expose unauthenticated MCP HTTP publicly. No credentials hardcoded — `.env` gitignored, `mcp/.env.example` documents required vars.

See `mcp/README.md` §5/§7 and `mcp/config/tool_policy.yaml` `transport`.

## 5. Available Tools (9 investigation capabilities, spec §6)

Our agent sees **only** 9 read-only tools, each → one Phase-1 installed query (no duplicate logic):

| Tool (canonical) | GSQL query | Alias | Read-only | Purpose (agent-facing) |
|------------------|------------|-------|-----------|------------------------|
| `benchmark_case_context` | `benchmark_case_context.gsql` | `get_benchmark_case`, `list_benchmark_cases` (limited list wrapper) | Yes | Retrieve verified benchmark-case → flagged transaction → card/customer context + related graph evidence (read-only, does not determine fraud) |
| `get_transaction` | `get_transaction.gsql` | — | Yes | Transaction + Card→Customer + Device + Regions + Emails + NEXT neighbors |
| `get_customer_history` | `get_customer_history.gsql` | — | Yes | Customer → OWNS → Card → MADE → Transactions |
| `get_card_history` | `get_card_history.gsql` | — | Yes | Card → Transactions ordered by `ts`/NEXT |
| `find_device_connections` | `find_device_connections.gsql` | — | Yes | DeviceProfile ↔ Transaction ↔ Card ↔ Customer (R6, Patterns 3/5) |
| `find_related_transactions` | `find_related_transactions.gsql` | — | Yes | Via card/region/device/email (verified edges) |
| `find_related_cases` | `find_related_cases.gsql` | — | Yes | Historical ClosedCases via shared entity |
| `get_temporal_chain` | `temporal_chain.gsql` | `temporal_chain` | Yes | Card NEXT chain (velocity) |
| `calculate_exposure` | `calculate_exposure(_list).gsql` | — | Yes | Sum(amount) over Set<STRING> txn_ids |

MCP tool → validated input → allowlist check → resource-limits check → approved GSQL → TigerGraph → structured result (see `mcp/tools/investigation_tools.py:discover_tools()`, `mcp/tools/_common.py:try_live_call`).

Generic upstream write/admin tools (`create_vertex/edge`, `run_gsql`, `install_query`, `create_schema`, etc.) are **not** in our allowlist and `get_tool()` raises `KeyError`.

## 6. Tool Schemas (spec §7/§8)

Strict Pydantic v2, `extra="forbid"`, regex + ranges, explicit error codes (`mcp/schemas/tool_schemas.py`):

- `benchmark_case_context: {case_id: ^HHG-\d{3}$}`
- `get_transaction: {transaction_id: ^\d+$}`
- `get_customer_history: {customer_id: ^C\d+$, limit 1–200}`
- `get_card_history: {card_id: ^C\d+-K\d+$, limit 1–200}`
- `find_device_connections: {txn_id?: ^\d+$, device_profile_id?: ^DP-[0-9a-f]{16}$ (xor, at least one), limit 1–200}`
- `find_related_transactions: {txn_id?: \d+, card_id?: C\d+-K\d+, customer_id?: C\d+ (≥1), max_hops 1–5, limit 1–200}`
- `find_related_cases: {txn_id?, card_id?, customer_id?, device_profile_id?, region_code?: ^\d+(\.0)?$, domain?: email (≥1), limit 1–200}`
- `get_temporal_chain: {card_id: C\d+-K\d+, limit 1–200}`
- `calculate_exposure: {transaction_ids: [\d+]{1–100} deduped, case_id?: HHG-\d{3}}`

Unreasonable limits, malformed IDs, unsupported entity types rejected → `{status:error, error_code: INVALID_INPUT|RESOURCE_LIMIT_EXCEEDED|NOT_FOUND|POLICY_DENIED, message, retryable implicit}`.

Structured success: `{tool, status:success, data:{...}, source:{graph,query,entity_ids,kind}, provenance:[{tool,query,entity_ids,ts}], truncated, total_count}` — never prose, never fabricated empty as success. Examples: `get_benchmark_case HHG-001` returns `benchmark_case, flagged_transaction, card, customer, card_history, devices, billing_regions, related_cases`; `calculate_exposure [3514030]` returns `{exposure_usd, count}`. See `mcp/README.md` §8.

## 7. Security Boundaries (spec §10)

Read-only boundary enforced at the MCP tool layer (treated as controlled tool boundary):

- Future LLM **must NOT** execute arbitrary GSQL, modify/delete data, create vertices/edges, mutate historical/benchmark cases, change policies, or bypass validation.
- Phase 2 tools are read-only — every handler checks `is_allowed()` then `has_live_credentials()` → `try_live_call` only via `runInstalledQuery`/`run_query` with read queries; file fallback only reads `data/*.csv`.
- Official MCP generic `gsql`/`add_node/edge`/`delete_*` are blocked (`blocked_upstream_tools`); not exposed via `mcp/tools/investigation_tools.py:registry` (only 9 canonical).
- Credential absence handled gracefully → `LIVE_TIGERGRAPH_UNAVAILABLE` + file_fallback, not crash; truncated reported explicitly.

## 8. Allowlist (spec §11)

`mcp/config/tool_policy.yaml` (enforced via `is_allowed()` + `resource_limits()` in every handler, not merely documented):

```yaml
allowlist: {tools: [get_transaction, get_customer_history, get_card_history, find_device_connections, find_related_transactions, find_related_cases, get_temporal_chain, calculate_exposure, benchmark_case_context], aliases: {get_benchmark_case: benchmark_case_context}}
denied_capabilities: [arbitrary_gsql_write, vertex_insert/update/delete, edge_insert/update/delete, schema_mutation, policy_mutation, loading_job_run, token_create, user_management]
blocked_upstream_tools: [create_vertex, update_vertex, delete_vertex, create_edge, update_edge, delete_edge, run_gsql, install_query, create_schema]
resource_limits: {MAX_HOPS:5, MAX_RESULTS:200, MAX_TX_IDS:100, MAX_TEMPORAL:200, TIMEOUT_S:30}
```

On denied: `{status:error, error_code:POLICY_DENIED}`.

## 9. Test Results (spec §16)

`mcp/tests/` — 3 files, 33 tests + deterministic connection script:

- `test_connection.py` (spec §5, importable `main()`): checks MCP import, TG env, graph existence, schema, 8 vertices + 11 edges (PURCHASER/RECIPIENT map to `purchaser_email`/`recipient_email`), file_fallback PASS (LIVE_TIGERGRAPH_UNAVAILABLE explicitly, no fake success). Exit 0 offline. Run: `python mcp/tests/test_connection.py`. Result: `PASS (file_fallback)` — `mcp` package not installed offline → WARN, `TG_HOST` not set → LIVE_TIGERGRAPH_UNAVAILABLE, 8/8 vertices + 11/11 edges present via `data/*.csv`.
- `test_tools.py` (20 tests, unittest): valid/invalid benchmark (HHG-001 / HHG-999), valid/invalid transaction (3514030 / 999999999), valid customer C12382, valid card C12382-K1, valid device (via txn 3478561), valid historical case, empty region 9999.0, malformed BAD-ID, excessive max_hops 100 / limit 1000 / tx_ids 200, exposure/temporal file_fallback, related-transactions valid, malformed txn, list_benchmark_cases, truncated flag, provenance. Distinguishes mocked/file_fallback vs live (`source.kind==file_fallback` asserted offline).
- `test_security.py` (13 tests): registry only 9 read-only, no write in allowlist, denies arbitrary/edge/schema/policy mutations, credential absence → file_fallback, malformed IDs rejected, resource limits, generic write not in discovery, tool_policy declares denied, every envelope has provenance+truncated, unknown tool → KeyError.

**Run:** `python -m pytest mcp/tests/test_tools.py mcp/tests/test_security.py -v` → **33 passed** (3 previously failed for limit→`INVALID_INPUT` fixed to accept either `INVALID_INPUT` or `RESOURCE_LIMIT_EXCEEDED`). `python -m pytest mcp/tests/test_connection.py` collects 0 (script-style test, run directly).

Live vs mocked labeled correctly — never label file_fallback as live.

## 10. Case Connectivity Results (spec §17)

`mcp/validation/MCP_CASE_CONNECTIVITY_REPORT.md` (20/20 via `get_benchmark_case` / `benchmark_case_context` file_fallback):

All `HHG-001`..`HHG-020` → `benchmark_case_context` `status:success` (source `file_fallback`, explicit provenance, latency 704–3149 ms):

- HHG-001 (C12382-K1, flagged 3514030, addr 444, risk 0.61, in_person — devices empty, correct)
- HHG-002 (C11891-K1, 3478782, risk 0.79, no identity edge — known)
- HHG-003 C08623-K2, HHG-004 C08106-K1, HHG-005 C02923-K1, HHG-006 C07297-K1, HHG-007 C09933-K2, HHG-008 C13171-K2, HHG-009 C08299-K1 (56 total), HHG-010 C10434-K1 (36, $1000 outlier), HHG-011 C11923-K2, HHG-012 C05876-K2, HHG-013 C07671-K2, HHG-014 C13487-K1 (85, SM-G935F ring → 4 undocumented ClosedCases CC-2649/2971/2985/3035 surfaced via device), HHG-015 C03042-K1, HHG-016 C09988-K1, HHG-017 C04570-K1, HHG-018 C02354-K2, HHG-019 C07987-K2, HHG-020 C12265-K2 — each card_history capped at 200 (`truncated:true` when total>200).

For every case: `BenchmarkCase → TRIGGERS → flagged Transaction (590,742) → Card (CXXXX-KY via Q1) → Customer → card_history/devices/regions/emails + related ClosedCases` holds. `evidence_count` = card_history length (+ devices/regions/related_cases). Spot checks (HHG-001 flagged): `get_transaction` 584 ms success, `get_customer_history` 146 ms truncated true, `get_card_history` 356 ms truncated true, `get_temporal_chain` 357 ms truncated true, `calculate_exposure [3514030]` 122 ms, `find_related_cases` 3.4 ms, `find_related_transactions` 796 ms truncated true — all `file_fallback`. No final fraud verdicts.

## 11. Performance Results (spec §18, no fabrication)

File_fallback measurements on this host (Windows, Python 3.13, pandas, 590K transactions, `mcp/tools/logging.py` `Timer`):

| Tool | Input | Latency | Size / truncated |
|------|-------|---------|------------------|
| benchmark_case_context | HHG-001..020 each | 704–3149 ms per case (see §10 table; median ~1100 ms; HHG-001 3149 ms max — 422-txn card + joins; HHG-014 2314 ms — ring expansion) | card_history 36–200 returned, truncated when total>200 |
| get_transaction | 3514030 | 584 ms | transaction+card+customer+device/regions/emails+NEXT, truncated false |
| get_customer_history | C12382 limit 5 | 146 ms | truncated true (422 total) |
| get_card_history | C12382-K1 limit 5 | 356 ms | truncated true |
| get_temporal_chain | C12382-K1 limit 5 | 357 ms | truncated true |
| calculate_exposure | [3514030] | 122 ms | sum |
| find_related_cases | C12382-K1 limit 5 | 3.4 ms | empty or few, truncated false |
| find_related_transactions | 3514030 max_hops 1 limit 5 | 796 ms | truncated true |

Live TigerGraph performance: `PENDING_LIVE_EXECUTION` — `TG_HOST` not set → `LIVE_TIGERGRAPH_UNAVAILABLE`; will be recorded via `runInstalledQuery` with `TIMEOUT_S 30` once instance provisioned. Our `try_live_call` uses `pyTigerGraph.runInstalledQuery(query, params, timeout=TIMEOUT_S*1000)`.

## 12. Live Execution Status

- **Official MCP server:** `tigergraph-mcp` not installed in offline env (WARN `No module named 'mcp'` — `pip install tigergraph-mcp` required); our `mcp/tools` layer works standalone. No live server started in this validation (file_fallback).
- **TigerGraph connection:** `LIVE_TIGERGRAPH_UNAVAILABLE` — `TG_HOST`/`TIGERGRAPH_HOST` not configured (no `.env`); connection test `python mcp/tests/test_connection.py` exits 0 (PASS file_fallback), file_fallback validated (8 vertices / 11 edges present), live graph/schema check deferred. To enable live, `cp mcp/.env.example .env` and set `TG_HOST=http://...`, `TG_GRAPHNAME=hhg_fraud_graph`, `TG_USERNAME`, `TG_PASSWORD`/`TG_API_TOKEN` per `mcp/README.md` §5.
- **Graph discovery:** file_fallback discovers 8/8 vertices and 11/11 edges from `data/vertices/*.csv` + `data/edges/*.csv`; live discovery would use `tigergraph__get_graph_schema` / `SHOW GRAPH hhg_fraud_graph` via `pyTigerGraph.gsql()` (see `_try_live_connection`).
- **Tools / security / tests / live execution:** as above (tools 9 read-only via file_fallback, security read-only enforced, 33 tests pass, live pending).

## 13. Known Limitations

- Offline env → official `tigergraph-mcp` not installed, so live stdio/streamable-http server not exercised — our MCP wrapper is the validated interface; install `tigergraph-mcp` to run the official server per `mcp/README.md`.
- Live TigerGraph not reachable → all performance is file_fallback (pandas); live `runInstalledQuery` latencies remain `PENDING_LIVE_EXECUTION`.
- File fallback mirrors but does not replicate TigerGraph index performance / vector search (Phase 3 GraphRAG).
- `find_device_connections` on truly in_person flagged txns correctly returns `NOT_FOUND` (no DeviceProfile) — caller should use card/customer context instead (as in `benchmark_case_context`).
- No LLM/LangGraph/GraphRAG/XAI/uncertainty/next-best-action/counterfactual — per scope, deferred to Phase 3+.

## 14. Phase 3 Prerequisites

- Provision TigerGraph Savanna or Community 4.1+ (`hhg_fraud_graph`), run `gsql tigergraph/schema/schema.gsql` and `tigergraph/loading/load_*.gsql` per `tigergraph/README.md` §4/§6; verify `tigergraph/validation/GRAPH_VALIDATION_REPORT.md`.
- `pip install tigergraph-mcp pyTigerGraph mcp pydantic python-dotenv` (and `uvicorn starlette` for HTTP) — confirm `tigergraph-mcp --help` and `TG_HOST` connectivity.
- Set `mcp/.env` (from `mcp/.env.example`, gitignored) and run `python mcp/tests/test_connection.py` until `LIVE TigerGraph OK`.
- Install `mcp/tests` deps (`pytest`) and expect 33+ live tests to pass with `source.kind==tigergraph_live`.
- Then connect GraphRAG (historical case/policy retrieval) and LangGraph orchestration on top of this read-only MCP layer — see `mcp/README.md` §14 and `mcp/validation/MCP_VALIDATION_REPORT.md` §12.

---

## Artifacts Delivered (spec §3)

```
mcp/README.md
mcp/.env.example
mcp/config/tool_policy.yaml
mcp/schemas/tool_schemas.py
mcp/tools/investigation_tools.py, case_tools.py, transaction_tools.py, relationship_tools.py, history_tools.py, _common.py, logging.py
mcp/tests/test_connection.py, test_tools.py, test_security.py
mcp/validation/MCP_VALIDATION_REPORT.md
mcp/validation/MCP_CASE_CONNECTIVITY_REPORT.md
phase2/PHASE2_FINAL_REPORT.md (this file)
```

Upstream package not duplicated; only project-specific wrappers/config.

---

PHASE 2 STATUS: COMPLETE (file-fallback validated; live execution pending instance)

MCP STATUS:
- server: official tigergraph-mcp inspected (0.1.0+, 69 tools, stdio+streamable-http), not installed in offline env — our controlled wrapper installed and file-fallback validated
- TigerGraph connection: LIVE_TIGERGRAPH_UNAVAILABLE (TG_HOST not set) — correctly reported, file_fallback PASS, no fake success
- graph discovery: 8/8 vertices, 11/11 edges PASS via data/*.csv (PURCHASER/RECIPIENT map to *_EMAIL); live via SHOW GRAPH pending
- tools: 9/9 read-only investigation tools → 9 GSQL queries, validated inputs, structured outputs, provenance+truncated, file_fallback mirrors GSQL
- security: read-only boundary enforced (allowlist 9, denied write/schema/policy, arbitrary GSQL blocked, generic upstream tools not exposed)
- tests: 33 passed (test_tools 20 + test_security 13), test_connection PASS file_fallback
- live execution: PENDING_LIVE_EXECUTION (see mcp/validation/)

BLOCKERS:
- Live TigerGraph instance not provisioned (TG_HOST absent) — expected offline; no design or graph blockers. Install tigergraph-mcp and provision Savanna/Community 4.1+ to enable live path.

NEXT PHASE:
GraphRAG + historical case/policy evidence retrieval. Do NOT start Phase 3 automatically.
