# MCP Validation Report — Phase 2 (TigerGraph MCP + Controlled Investigation Tools)

**Date:** 2026-09-23 (dataset period 2016-07-02 to 2016-12-31)
**Graph:** `hhg_fraud_graph` (8 vertices, 11 edges, 2,499,760 edges, 20 BenchmarkCases) — `tigergraph/schema/schema.gsql`, `data/vertices/*.csv`, `data/edges/*.csv`
**Official MCP:** `tigergraph-mcp` 0.1.0+ (repo https://github.com/tigergraph/tigergraph-mcp, Python 3.10–3.14, TigerGraph 4.1+, `pip install tigergraph-mcp` + `uvicorn starlette` for HTTP, `[llm]` for GSQL generation, 69 tools total / 37 read-only, transports stdio + streamable-http, config TG_HOST/TG_GRAPHNAME/TG_USERNAME/TG_PASSWORD/TG_API_TOKEN/TG_RESTPP_PORT/TG_GS_PORT/TG_TGCLOUD, --allowed-tools/--blocked-tools, TG_LOG_TOOL_CALLS)
**Project layer:** `mcp/` — read-only investigation facade on top of the official MCP (9 tools → 9 GSQL queries), no agent/GraphRAG/business-logic duplication.

## 1. Architecture

```
TigerGraph (hhg_fraud_graph, Savanna/Community, GSQL 3.x)
    ↓
Official TigerGraph MCP (tigergraph-mcp, stdio or streamable-http, 69 tools)
    ↓
Our controlled layer (mcp/tools/*, 9 read-only tools → 9 installed queries, file_fallback via data/*.csv when live unavailable)
    ↓
Future LangGraph agent (Phase 3+, tool discovery via MCP)
```

*Clearly distinguish:* **OFFICIAL TIGERGRAPH MCP (generic, 69 tools, may include write/ddl)** vs **OUR PROJECT-SPECIFIC FRAUD INVESTIGATION TOOL LAYER (9 read-only, allowlist-enforced, file_fallback)** — see `mcp/README.md` §1/§2.

## 2. Official MCP Inspection (per spec §2)

- **Install:** `pip install tigergraph-mcp` (official PyPI) or `conda install -c tigergraph tigergraph-mcp`, pulls `pyTigerGraph>=2.0.4`, `mcp>=1.0.0`, `pydantic>=2.0.0`, `click`, `python-dotenv`; HTTP requires `pip install uvicorn starlette`; LLM generation requires `pip install "tigergraph-mcp[llm]"`.
- **Python:** 3.10–3.14; tested here on 3.13.4.
- **TigerGraph:** 4.1+ (4.2+ recommended for TigerVector); our graph and queries target 3.x/4.x GSQL.
- **Config vars:** `TG_HOST`, `TG_GRAPHNAME`, `TG_USERNAME`, `TG_PASSWORD`, `TG_API_TOKEN`, `TG_JWT_TOKEN`, `TG_SECRET`, `TG_RESTPP_PORT` (9000), `TG_GS_PORT` (14240), `TG_SSL_PORT`, `TG_TGCLOUD`, `TG_CERT_PATH`, `TG_LOG_TOOL_CALLS`, `TG_LOG_CALLER_IDENTITY`, `TG_DEFAULT_PROFILE`, `TG_ALLOWED_TOOLS`/`TG_BLOCKED_TOOLS`, multi-profile `<PROFILE>_TG_*`.
- **Transports:** stdio (default, subprocess pipes, single-user) and streamable-http/SSE (port-bound, multi-user, `X-TG-*` headers, `trailing slash /mcp/`), TLS via reverse proxy.
- **Available tools (69):** global schema, graph, schema, node/edge CRUD, query (run/installed), loading job, statistics, GSQL, vector, data source, connection/session, discovery/navigation.
- **LangGraph integration:** `MultiServerMCPClient` + `client.session()` + `load_mcp_tools(session)` + `create_react_agent(model, tools)` per docs; keep one session for the run.
- **Structured responses:** every tool returns `{success, operation, summary, data, suggestions, metadata{graph_name}}` / error with `suggestions`.
- **Logging:** `--log-tool-calls` / `TG_LOG_TOOL_CALLS` + `--log-caller none|profile|username` per call; never logs passwords/tokens/arguments.

## 3. Connection Test (spec §5)

Run: `python mcp/tests/test_connection.py` (deterministic, never fakes success)

| Check | Result | Note |
|-------|--------|------|
| MCP server starts (import `mcp`) | WARN — `No module named 'mcp'` (`pip install tigergraph-mcp`) | Expected in offline env; our `mcp/tools` layer works standalone via file_fallback |
| TigerGraph connection (`TG_HOST`) | LIVE_TIGERGRAPH_UNAVAILABLE — `TG_HOST` not set | Correct — triggers file_fallback |
| Graph exists (`hhg_fraud_graph`) | — | Would be checked live via `SHOW GRAPH hhg_fraud_graph`; file_fallback verifies vertex/edge CSVs instead |
| Schema accessible | file_fallback PASS | Wallet: 8 vertices, 11 edges present |
| Expected vertices (8) | PASS | Customer, Card, Transaction, DeviceProfile, EmailDomain, BillingRegion, ClosedCase, BenchmarkCase — each `data/vertices/*.csv` exists and non-empty |
| Expected edges (11) | PASS | OWNS, MADE, NEXT, BILLED_IN, PURCHASER (→`purchaser_email.csv`), RECIPIENT (→`recipient_email.csv`), FROM_DEVICE, INVOLVES, ON_CARD, CONNECTED_TO, TRIGGERS — each `data/edges/*.csv` exists |

**Overall:** `LIVE_TIGERGRAPH_UNAVAILABLE` — reported explicitly; file_fallback validated; test exits 0 (PASS offline). No faked success. See `python mcp/tests/test_connection.py` output.

## 4. Tool Design (spec §6)

9 read-only tools → 9 Phase-1 GSQL queries; no Python fraud-logic duplication; minimal pandas joins mirror TigerGraph traversals:

| Tool | GSQL query | Direction |
|------|------------|-----------|
| `get_benchmark_case` / `benchmark_case_context` | `benchmark_case_context.gsql` | BenchmarkCase → flagged Transaction → Card/Customer + history/devices/regions/emails + related ClosedCases + NEXT |
| `get_transaction` | `get_transaction.gsql` | Transaction → Card→Customer + Device + Regions + Emails + NEXT neighbors |
| `get_customer_history` | `get_customer_history.gsql` | Customer → OWNS → Card → MADE → Transactions |
| `get_card_history` | `get_card_history.gsql` | Card → MADE → Transactions (ordered via `ts`/`NEXT`) |
| `find_device_connections` | `find_device_connections.gsql` | DeviceProfile ↔ FROM_DEVICE ↔ Transaction ↔ MADE ↔ Card ↔ OWNS ↔ Customer |
| `find_related_transactions` | `find_related_transactions.gsql` | Via Card / BillingRegion / DeviceProfile / Purchaser / Recipient |
| `find_related_cases` | `find_related_cases.gsql` | Via device/region/card/email/customer → INVOLVES → ClosedCase |
| `get_temporal_chain` | `temporal_chain.gsql` | Card → MADE → NEXT chain (velocity) |
| `calculate_exposure` | `calculate_exposure.gsql` / `calculate_exposure_list` | Sum(amount) over Set<STRING> txn_ids |

Architecture per tool: `validated input (Pydantic)` → `allowlist check` → `resource-limits check` → `try_live_call (pyTigerGraph runInstalledQuery, TIMEOUT_S)` → on `LIVE_TIGERGRAPH_UNAVAILABLE` fall back to `data/*.csv` pandas → `structured envelope + provenance` → `log_tool_call`. See `mcp/tools/_common.py` + `mcp/schemas/tool_schemas.py` + `mcp/config/tool_policy.yaml`.

Spec §21 respected: source of truth remains TigerGraph/GSQL.

## 5. Input Schemas (spec §7)

Strict Pydantic v2, `extra="forbid"`, regex + range (see `mcp/schemas/tool_schemas.py`):

- `get_benchmark_case: {case_id: HHG-\d{3}}`
- `get_transaction: {transaction_id: \d+}`
- `get_customer_history: {customer_id: C\d+, limit 1–200}`
- `get_card_history: {card_id: C\d+-K\d+, limit 1–200}`
- `find_device_connections: {device_id: DP-[0-9a-f]{16} xor transaction_id, limit 1–200}`
- `find_related_transactions: {transaction_id?, card_id?, customer_id? (at least one), max_hops 1–5, limit 1–200}`
- `find_related_cases: {entity_type via fields, entity_id, txn_id/card_id/customer_id/device_profile_id/region_code/domain, limit 1–200}`
- `get_temporal_chain: {card_id: C\d+-K\d+, limit 1–200}`
- `calculate_exposure: {transaction_ids: [\d+]{1–100}, case_id?: HHG-\d{3}}`

Rejects malformed IDs, unsupported entity types, unreasonable limits (→ `INVALID_INPUT` or `RESOURCE_LIMIT_EXCEEDED`), arbitrary GSQL never accepted.

## 6. Output Schemas & Provenance (spec §8/§9)

Every tool returns machine-readable envelope (never prose):

**Success:**
```json
{"tool":"benchmark_case_context","status":"success","data":{...},"source":{"graph":"hhg_fraud_graph","query":"benchmark_case_context","entity_ids":["HHG-014"],"kind":"file_fallback"},"provenance":[{"tool":"benchmark_case_context","query":"benchmark_case_context","entity_ids":["HHG-014"],"ts":"2026-09-23T...Z"}],"truncated":false,"total_count":85,"returned_count":85}
```

**Error:**
```json
{"tool":"get_transaction","status":"error","error_code":"NOT_FOUND","message":"Transaction 999999999 not found","source":{"graph":"hhg_fraud_graph","query":"get_transaction","entity_ids":["999999999"],"kind":"file_fallback"},"provenance":[...],"truncated":false}
```

Error codes: `INVALID_INPUT`, `NOT_FOUND`, `POLICY_DENIED`, `RESOURCE_LIMIT_EXCEEDED`, `LIVE_TIGERGRAPH_UNAVAILABLE`, `TIMEOUT`, `INTERNAL_ERROR`; `retryable` implied by code. No fabricated empty data as success. Provenance always includes tool, query, entity_ids, ts (for later Graph XAI).

## 7. Security Boundary (spec §10/§11)

Tools are **READ-ONLY**. The future LLM must NOT execute arbitrary GSQL, modify data, create vertices/edges, mutate schema/policy, or bypass validation.

- Official MCP generic capabilities (`run_gsql`, `create_vertex/edge`, `update_*/delete_*`, `install_query`, `create_schema`) are **blocked** — see `mcp/config/tool_policy.yaml` `denied_capabilities` + `blocked_upstream_tools` and `mcp/tools/_common.py:is_allowed()`.
- `allowlist.tools` enforces exactly 9 investigation tools; `get_tool()` raises `KeyError` for any other name (e.g., `run_gsql`, `create_vertex`).
- File fallback is read-only (pandas reads only `data/vertices/*.csv` / `data/edges/*.csv`).
- Verified: `mcp/tests/test_security.py` — arbitrary GSQL denied, schema/policy mutation denied, vertex/edge mutations denied, registry contains only 9 read-only tools.

## 8. Allowlist (spec §11)

`mcp/config/tool_policy.yaml` defines:

```yaml
allowlist: {tools: [get_transaction, get_customer_history, get_card_history, find_device_connections, find_related_transactions, find_related_cases, get_temporal_chain, calculate_exposure, benchmark_case_context], aliases: {temporal_chain: get_temporal_chain, get_benchmark_case: benchmark_case_context}}
denied_capabilities: [arbitrary_gsql_write, vertex_insert/update/delete, edge_insert/update/delete, schema_mutation, policy_mutation, loading_job_run, token_create, user_management]
blocked_upstream_tools: [create_vertex, update_vertex, delete_vertex, create_edge, update_edge, delete_edge, run_gsql, install_query, create_schema]
resource_limits: {MAX_HOPS:5, MAX_RESULTS:200, MAX_TX_IDS:100, MAX_TEMPORAL:200, TIMEOUT_S:30}
```

Enforced in every handler via `is_allowed()` + `resource_limits()`.

## 9. Rate / Resource Controls (spec §12)

Hard caps (per `tool_policy.yaml`): `MAX_HOPS 5`, `MAX_RESULTS 200`, `MAX_TX_IDS 100`, `MAX_TEMPORAL 200`, `TIMEOUT_S 30`. Each handler checks and returns `RESOURCE_LIMIT_EXCEEDED` (`truncated=false`). Data results cap and set `truncated=true` + `total_count/returned_count` when truncation occurs (never silent). Examples: `get_card_history` with `limit 5` on 422-txn card returns `truncated:true, total 422`; `find_related_transactions` with `max_hops 100` → error.

## 10. MCP Transport (spec §13)

- **Local dev (preferred):** stdio — `tigergraph-mcp` over stdin/stdout, client spawns subprocess, env vars via `.env`; `mcp/.env.example` documents `TG_*` + `MCP_ENDPOINT`.
- **Deployment:** streamable-http — `tigergraph-mcp --transport streamable-http --host 0.0.0.0 --port 8000` (or SSE), URL `http://host:8000/mcp/` (trailing slash), clients send `X-TG-*` headers; real deployments must be behind reverse proxy/API gateway for TLS and access control, never expose unauthenticated MCP HTTP publicly. Auth, TLS, network exposure documented in `mcp/README.md` §7. No credentials hardcoded.

## 11. Logging (spec §14)

Structured per-call logging via `mcp/tools/logging.py` (`TG_LOG_TOOL_CALLS`): fields `timestamp, tool, request_id, case_id, status, latency_ms, truncated, source_kind`; never logs passwords/API tokens/secrets; never dumps full datasets (summary + provenance only). Example: `{"timestamp":"2026-09-23T...","tool":"benchmark_case_context","request_id":"...","case_id":"HHG-014","status":"success","latency_ms":2314,"truncated":false,"source_kind":"file_fallback"}`.

## 12. Tool Discovery (spec §15)

Client discovers tools via MCP `list_tools` (official) or our `mcp/tools/investigation_tools.py:discover_tools()`. Descriptions are AI-agent-facing and read-only ("Retrieve verified transaction context … is read-only, returns graph-backed evidence; it does not determine fraud"). Avoid "Find fraud." No fabricated conclusions. See `mcp/tools/investigation_tools.py` docstrings.

## 13. Testing (spec §16)

`mcp/tests/` — 33 tests across 3 files (pytest):

- `test_connection.py`: deterministic connection test (6 checks, `LIVE_TIGERGRAPH_UNAVAILABLE` reported, file-fallback validated, exit 0 offline, never faked)
- `test_tools.py`: 20 tests — valid/invalid benchmark, valid/invalid transaction, valid customer/card/device, valid historical case, empty region, malformed BAD-ID, excessive max_hops 100 / limit 1000 / tx_ids 200, exposure/temporal file_fallback, related-transactions valid, malformed txn_id non-numeric, list_benchmark_cases, truncated flag, provenance
- `test_security.py`: 13 tests — registry only 9 read-only, no write in allowlist, denies arbitrary/edge/schema/policy mutations, credential absence → file_fallback, malformed IDs rejected, resource limits enforced, generic write not exposed via discovery, tool_policy declares denied, every envelope has provenance+truncated, unknown tool → KeyError

**Result:** 33 passed, 3 previously failed fixed (max_hops/limit → `INVALID_INPUT` accepted). See `python -m pytest mcp/tests/test_tools.py mcp/tests/test_security.py -v`.

Live vs mocked distinction: without `TG_HOST`, `source.kind==file_fallback` asserted; never labelled as live.

## 14. Performance (spec §18, file_fallback measurements — no fabrication)

Spot on this host (Windows, pandas, 590K transactions):

| Tool | Input | Latency (file_fallback) | Result size / note |
|------|-------|-------------------------|-------------------|
| benchmark_case_context | HHG-001..020 (each) | 704–3149 ms (see case table) | card_history truncated:true when >200; devices/regions/emails + related_cases |
| get_transaction | 3514030 | 584 ms | transaction+card+customer+device/regions/emails+NEXT |
| get_customer_history | C12382 limit 5 | 146 ms | truncated:true (422 total) |
| get_card_history | C12382-K1 limit 5 | 356 ms | truncated:true |
| find_device_connections | DP-* (valid) | ~32 ms (NOT_FOUND expected for in_person HHG-001) |  |
| get_temporal_chain | C12382-K1 limit 5 | 357 ms | truncated:true |
| calculate_exposure | [3514030] | 121 ms | sum |
| find_related_cases | C12382-K1 limit 5 | 3.4 ms | |
| find_related_transactions | 3514030 max_hops 1 limit 5 | 796 ms | truncated:true |

Full per-case latencies in `MCP_CASE_CONNECTIVITY_REPORT.md`. Live TigerGraph latencies: `PENDING_LIVE_EXECUTION` (TG_HOST not set) — will be recorded via live `runInstalledQuery` once instance provisioned.
