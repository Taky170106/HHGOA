# MCP — TigerGraph Investigation Layer (Phase 2)

> **HHGoa 2026 — TigerGraph × Hacker House Goa Agentic Fraud Investigation**

Phase 2 wraps a **live TigerGraph** with a **controlled, read-only MCP tool layer** for the LangGraph agent.
It does **not** replace the official TigerGraph MCP — it **constrains** it.

---

## 1. Purpose

Provide **9 deterministic, policy-gated, provenance-carrying investigation tools** backed by the
`hhg_fraud_graph` (8 vertices, 11 edges) and 9 GSQL queries. The agent (LangGraph + Gemma 4 26B)
reasons and plans; **TigerGraph is the authoritative memory**; tool outputs are **structured and auditable**.

Principle: *graph evidence is authoritative — LLM cannot invent relationships.*

Phase 2 is **not**: an agent, GraphRAG, XAI, next-best-action, or business-logic duplication.
Those are later phases.

---

## 2. Architecture

```
┌─────────────────┐      ┌──────────────────────────────┐      ┌──────────────────────────────────────┐      ┌───────────┐
│   TigerGraph    │─────▶│  Official MCP                │─────▶│  Our controlled layer                │─────▶│ LangGraph │
│ hhg_fraud_graph │      │  tigergraph-mcp 0.1.0+       │      │  mcp/tools/*  (9 read-only tools)    │      │  Agent    │
│ 8V / 11E + GSQL │      │  69 tools / 37 read-only     │      │  validation + allowlist + envelope   │      │ (Phase 4) │
│ RESTPP :9000    │      │  stdio / streamable-http     │      │  file_fallback when TG_HOST absent  │      │           │
│ GSQL   :14240   │      │  TG_HOST / TG_GRAPHNAME etc  │      │  mcp/config/tool_policy.yaml        │      │           │
└─────────────────┘      └──────────────────────────────┘      └──────────────────────────────────────┘      └───────────┘
```

### What belongs where

| Layer | Repo / package | Responsibility |
|-------|---------------|---------------|
| **Official TigerGraph MCP** | `tigergraph-mcp` (PyPI, GitHub: `tigergraph/tigergraph-mcp`) | Generic TigerGraph bridge: **69 tools** (37 read-only), transports **stdio** and **streamable-http**, config via `TG_HOST`/`TG_GRAPHNAME`/`TG_USERNAME`/`TG_PASSWORD`/`TG_API_TOKEN`/`TG_RESTPP_PORT`/`TG_GS_PORT`/`TG_TGCLOUD`, `--allowed-tools`/`--blocked-tools`, logging `TG_LOG_TOOL_CALLS`. Handles **any** TigerGraph graph. |
| **Our project-specific fraud investigation tool layer** | `mcp/tools/*` in this repo | **Exactly 9** fraud-investigation tools on `hhg_fraud_graph`. Strict Pydantic validation, allowlist enforcement, resource caps (`MAX_HOPS=5` etc.), structured envelope with `provenance` + `truncated`, file-fallback (`data/vertices/*.csv` + `data/edges/*.csv`) when live TG is absent, read-only guarantee, audit logging. No invention of IDs/relationships. |

> **Never confuse the two.** The official MCP is the generic transport; our layer is the
> **policy-constrained, auditable investigation API** the agent is allowed to call.

---

## 3. Official Dependency

```
tigergraph-mcp  0.1.0+
Python          3.10 — 3.14   (per official repo)
TigerGraph      4.1+
```

Install (both transports; HTTP needs `uvicorn` + `starlette`):

```bash
pip install tigergraph-mcp
# streamable-http transport requires:
pip install "tigergraph-mcp[llm]"   # optional LLM extras
pip install uvicorn starlette       # for --transport streamable-http
```

Also used by file-fallback/live stub:

```bash
pip install pyTigerGraph pandas pyyaml pydantic
```

Reference: https://github.com/tigergraph/tigergraph-mcp

---

## 4. Installation

```bash
# from repo root D:\HHG
pip install -r requirements.txt        # if present
pip install tigergraph-mcp pyTigerGraph pandas pyyaml pydantic
```

Copy env template (real `.env` is gitignored):

```bash
cp mcp/.env.example .env
# fill TG_HOST / TG_GRAPHNAME / TG_USERNAME / TG_PASSWORD / TG_API_TOKEN etc.
```

Verify data present:

```bash
ls data/vertices/*.csv data/edges/*.csv
```

---

## 5. Environment Configuration

Mirrors the official `tigergraph-mcp` README env vars, plus local additions.

| Variable | Default | Purpose |
|----------|---------|---------|
| `TG_HOST` | — | TigerGraph hostname / URL (official). Legacy `TIGERGRAPH_HOST` / `TIGERGRAPH_HOSTNAME` also accepted |
| `TG_GRAPHNAME` | `hhg_fraud_graph` | Graph name (official `TG_GRAPHNAME`; legacy `TIGERGRAPH_GRAPH_NAME`) |
| `TG_USERNAME` | — | TigerGraph username (official) |
| `TG_PASSWORD` | — | TigerGraph password (official) |
| `TG_API_TOKEN` | — | API / JWT token (official; `TG_JWT_TOKEN` alias) |
| `TG_JWT_TOKEN` | — | Alias for `TG_API_TOKEN` |
| `TG_RESTPP_PORT` | `9000` | RESTPP port (official) |
| `TG_GS_PORT` | `14240` | GSQL port (official) |
| `TG_SSL_PORT` | — | SSL port if TLS |
| `TG_TGCLOUD` | `false` | `true` on TigerGraph Cloud |
| `TG_SECRET` | — | Cloud secret |
| `TG_CERT_PATH` | — | TLS cert path |
| `TG_LOG_TOOL_CALLS` | `true` | Log each tool call (official) |
| `TG_LOG_CALLER_IDENTITY` | `true` | Log caller identity (official) |
| `TG_DEFAULT_PROFILE` | — | Default profile name (official) |
| `TG_ALLOWED_TOOLS` | 9 investigation tools | Mirrors official `--allowed-tools` (comma-separated) |
| `TG_BLOCKED_TOOLS` | write/admin tools | Mirrors official `--blocked-tools` |
| `MCP_ENDPOINT` | — | Streamable-http endpoint (e.g. `http://localhost:8000/mcp`) |
| `HHG_ROOT` | `D:\HHG` | Project root override |
| `DATA_DIR` | `D:\HHG\data` | Data dir override for file-fallback |
| `DATABASE_URL` | — | Future phases |

Real `.env` is **gitignored** — never commit it. Use `mcp/.env.example` as the template.

---

## 6. Running Locally

### Stdio (default, for Claude/Cursor/Windsurf etc.)

```bash
tigergraph-mcp --transport stdio
# with our allowlist:
tigergraph-mcp --transport stdio --allowed-tools get_transaction,get_customer_history,get_card_history,find_device_connections,find_related_transactions,find_related_cases,temporal_chain,calculate_exposure,benchmark_case_context
```

MCP client config (example):

```json
{
  "mcpServers": {
    "tigergraph": {
      "command": "tigergraph-mcp",
      "args": ["--transport", "stdio", "--allowed-tools", "get_transaction,get_customer_history,get_card_history,find_device_connections,find_related_transactions,find_related_cases,temporal_chain,calculate_exposure,benchmark_case_context"],
      "env": { "TG_HOST": "...", "TG_GRAPHNAME": "hhg_fraud_graph" }
    }
  }
}
```

### Streamable HTTP

```bash
tigergraph-mcp --transport streamable-http --host 0.0.0.0 --port 8000
# endpoint: http://localhost:8000/mcp
```

Our layer then uses `MCP_ENDPOINT=http://localhost:8000/mcp` (or calls `pyTigerGraph` directly via `try_live_call`).

---

## 7. MCP Transport

| Aspect | Stdio | Streamable HTTP |
|--------|-------|-----------------|
| Process | `tigergraph-mcp` as child process | `tigergraph-mcp --transport streamable-http` as server |
| Discovery | MCP `tools/list` | `tools/list` over HTTP |
| Auth headers | Env (`TG_HOST` etc.) forwarded to child | `X-TG-HOST`, `X-TG-USERNAME` etc. or `Authorization: Bearer <TG_API_TOKEN>` |
| TLS | N/A | Via reverse proxy (nginx/traefik). Do not expose unauthenticated public endpoint |
| When to use | Local desktop clients | LangGraph service / hosted agent |

**Security note (official):** Do not expose the HTTP MCP without auth. Put it behind a reverse proxy with TLS
and require `X-TG-*` / bearer token. The official MCP has no built-in public-auth bypass.

---

## 8. Available Investigation Tools (9 — Read-Only)

All are **read-only** and map 1:1 to a GSQL query in `tigergraph/queries/`.

| # | Tool | Input (Pydantic) | Output (envelope `data`) | GSQL file | Notes |
|---|------|------------------|--------------------------|-----------|-------|
| 1 | `get_transaction` | `txn_id: str` (numeric, regex `^\d+$`) | `transaction`, `card`, `customer`, `devices`, `billing_regions`, `purchaser/recipient_email_domains`, `next/prev_txn_ids` | `get_transaction.gsql` | Single txn + 1-hop context |
| 2 | `get_customer_history` | `customer_id: C\d+`, `limit 1..200` | `customer`, `cards` (via OWNS), `transactions` (via MADE), `total_transactions`, `truncated` | `get_customer_history.gsql` | `MAX_RESULTS=200` |
| 3 | `get_card_history` | `card_id: C\d+-K\d+`, `limit 1..200` | `card`, `transactions` ordered by `ts`, `next_edges`, `total_transactions` | `get_card_history.gsql` | `MAX_TEMPORAL=200` |
| 4 | `find_device_connections` | `txn_id?`, `device_profile_id?` (at least one), `limit 1..200` | `seed_device_ids`, `devices`, `linked_transaction_ids`, `linked_transactions`, `linked_cards/customers` | `find_device_connections.gsql` | Device fan-out |
| 5 | `find_related_transactions` | `txn_id?/card_id?/customer_id?` (≥1), `max_hops 1..5`, `limit 1..200` | `via_card/region/device/p_email/r_email` (ids + sample rows), `max_hops` | `find_related_transactions.gsql` | `MAX_HOPS=5` |
| 6 | `find_related_cases` | `txn_id?/card_id?/customer_id?/device_profile_id?/region_code?/domain?` (≥1), `limit 1..200` | `related_case_ids`, `related_cases` (ClosedCase rows), `total_found` | `find_related_cases.gsql` | Historical cases |
| 7 | `get_temporal_chain` (alias `temporal_chain`) | `card_id: C\d+-K\d+`, `limit 1..200` | `card`, `transactions` ordered, `next_edges` | `temporal_chain.gsql` | `MAX_TEMPORAL=200` |
| 8 | `calculate_exposure` | `transaction_ids: List[str]` (1..100, numeric) | `exposure_usd` (sum amount), `matched/missing_txn_ids`, `matched_transactions` | `calculate_exposure.gsql` (`calculate_exposure_list`) | `MAX_TX_IDS=100` |
| 9 | `benchmark_case_context` (aliases `get_benchmark_case`, `list_benchmark_cases`) | `case_id: HHG-\d{3}` | `benchmark_case`, `flagged_transaction`, `card/customer`, `card_history`, `devices/regions/emails`, `related_cases_via_*`, `next/prev_txn_ids` | `benchmark_case_context.gsql` | Full case context |

**All tools return a structured envelope** (see §9). No free-text-only output. Every call logs via `mcp/tools/logging.py`.

---

## 9. Input / Output Examples

### `get_benchmark_case` (HHG-001)

Request:

```json
{ "case_id": "HHG-001" }
```

Response (truncated):

```json
{
  "tool": "benchmark_case_context",
  "status": "success",
  "data": {
    "benchmark_case": { "case_id": "HHG-001", "flagged_txn_id": "3514030", "card_id": "C12382-K1", "customer_id": "C12382", "risk_score": 0.61 },
    "flagged_transaction": { "txn_id": "3514030", "card_id": "C12382-K1", "amount": 77.07, "addr1": "444.0" },
    "card": { "card_id": "C12382-K1", "customer_id": "C12382" },
    "customer": { "customer_id": "C12382" },
    "card_history": [ { "txn_id": "3514030" } ],
    "total_card_history": 422,
    "devices": [],
    "billing_regions": [ { "region_code": "444.0" } ],
    "purchaser_email_domains": ["gmail.com"],
    "recipient_email_domains": [],
    "next_txn_ids": ["3514031"],
    "prev_txn_ids": []
  },
  "source": { "graph": "hhg_fraud_graph", "query": "benchmark_case_context", "entity_ids": ["HHG-001"], "kind": "file_fallback" },
  "provenance": [ { "tool": "benchmark_case_context", "query": "benchmark_case_context", "entity_ids": ["HHG-001"], "ts": "2026-04-14T00:00:00+00:00" } ],
  "truncated": true,
  "total_count": 422,
  "returned_count": 200
}
```

### `get_transaction` (3514030)

Request:

```json
{ "txn_id": "3514030" }
```

Response:

```json
{
  "tool": "get_transaction",
  "status": "success",
  "data": {
    "transaction": { "txn_id": "3514030", "card_id": "C12382-K1", "amount": 77.07 },
    "card": { "card_id": "C12382-K1" },
    "customer": { "customer_id": "C12382" },
    "devices": [],
    "billing_regions": [ { "region_code": "444.0" } ],
    "purchaser_email_domains": ["gmail.com"],
    "recipient_email_domains": [],
    "next_txn_ids": ["3514031"],
    "prev_txn_ids": []
  },
  "source": { "graph": "hhg_fraud_graph", "query": "get_transaction", "entity_ids": ["3514030"], "kind": "file_fallback" },
  "provenance": [ { "tool": "get_transaction", "query": "get_transaction", "entity_ids": ["3514030"], "ts": "2026-04-14T00:00:00+00:00" } ],
  "truncated": false
}
```

### `calculate_exposure`

Request:

```json
{ "transaction_ids": ["3514030", "3478782"], "case_id": "HHG-001" }
```

Response:

```json
{
  "tool": "calculate_exposure",
  "status": "success",
  "data": { "matched_count": 2, "total_requested": 2, "exposure_usd": 369.43, "matched_txn_ids": ["3514030","3478782"], "missing_txn_ids": [] },
  "source": { "graph": "hhg_fraud_graph", "query": "calculate_exposure_list", "entity_ids": ["3514030","3478782"], "kind": "file_fallback" },
  "provenance": [ { "tool": "calculate_exposure", "query": "calculate_exposure_list", "entity_ids": ["3514030","3478782"], "ts": "2026-04-14T00:00:00+00:00" } ],
  "truncated": false,
  "total_count": 2
}
```

Error example:

```json
{ "tool": "get_transaction", "status": "error", "error_code": "INVALID_INPUT", "message": "txn_id must match ^\\d+$", "source": { "graph": "hhg_fraud_graph", "query": "get_transaction", "entity_ids": ["bad"], "kind": "file_fallback" }, "provenance": [ { "tool": "get_transaction", "query": "get_transaction", "entity_ids": ["bad"], "ts": "2026-04-14T00:00:00+00:00" } ], "truncated": false }
```

Envelope schema: `mcp/schemas/tool_schemas.py` (`SuccessEnvelope` / `ErrorEnvelope`, `ErrorCode`).

---

## 10. Security Boundary

This layer is **read-only**. The following are **denied and never exposed**:

- `arbitrary_gsql_write` / `run_gsql` with write statements
- `vertex_insert` / `vertex_update` / `vertex_delete` (`create_vertex`, `update_vertex`, `delete_vertex`)
- `edge_insert` / `edge_update` / `edge_delete` (`create_edge`, `update_edge`, `delete_edge`)
- `schema_mutation` (`create_schema`, `install_query`)
- `policy_mutation`, `loading_job_run`, `token_create`, `user_management`

Enforcement:

1. **`mcp/config/tool_policy.yaml`** — `allowlist.tools` is exactly the 9 above; `denied_capabilities.blocked_upstream_tools` lists the 9 official write/admin tools that are blocked when proxying.
2. **Runtime check** — every handler calls `is_allowed(tool)` from `mcp/tools/_common.py`; on denied → `POLICY_DENIED` error envelope.
3. **Arbitrary GSQL blocked** — no `run_gsql` passthrough; only the 9 installed queries are callable.
4. **File fallback is read-only** — reads `data/vertices/*.csv` + `data/edges/*.csv` via pandas; never writes.

Registry check: `mcp/tests/test_security.py` asserts `registry` contains **only** the 9 read-only tools.

---

## 11. Tool Allowlist

File: `mcp/config/tool_policy.yaml`

```yaml
allowlist:
  tools:
    - get_transaction
    - get_customer_history
    - get_card_history
    - find_device_connections
    - find_related_transactions
    - find_related_cases
    - get_temporal_chain
    - calculate_exposure
    - benchmark_case_context
```

Aliases: `temporal_chain` → `get_temporal_chain`, `get_benchmark_case` / `list_benchmark_cases` → `benchmark_case_context`.

Enforcement: `mcp/tools/_common.py:is_allowed()` (reads `tool_policy.yaml`, respects `aliases`). Tests: `mcp/tests/test_security.py`.

When running the **official** MCP standalone, also pass `--allowed-tools` / `--blocked-tools` (or `TG_ALLOWED_TOOLS` / `TG_BLOCKED_TOOLS`) to restrict what the **generic** MCP advertises — our layer then remains the only exposed surface.

---

## 12. Testing

```bash
# from repo root
python -m pytest mcp/tests/test_connection.py -v
python -m pytest mcp/tests/test_tools.py -v
python -m pytest mcp/tests/test_security.py -v
# or all:
python -m pytest mcp/tests/ -v
```

| Suite | Covers |
|-------|--------|
| `test_connection.py` | MCP import, TG env, live vs `LIVE_TIGERGRAPH_UNAVAILABLE` vs file-fallback, 8 vertices / 11 edges existence (with PURCHASER/RECIPIENT → PURCHASER_EMAIL/RECIPIENT_EMAIL mapping) |
| `test_tools.py` | ≥15 cases: valid/invalid benchmark case, valid/invalid transaction, valid customer/card/device, valid historical case, empty region, malformed `BAD-ID`, `max_hops=100`, `limit=1000`, `tx_ids=200`, file-fallback, provenance/truncated |
| `test_security.py` | Read-only boundary, blocked tools not in registry, credential absence, malformed IDs, resource limits |

Tests are **deterministic** and use **file-fallback** when live credentials are absent — they **never label mocked/file-fallback as live** (`source.kind` is asserted).

---

## 13. Live TigerGraph Requirements

To run against **live** TigerGraph (optional — file-fallback is the default):

1. Provision TigerGraph 4.1+ (Savanna or Community) and create graph `hhg_fraud_graph`:
   ```bash
   gsql tigergraph/schema/schema.gsql
   gsql tigergraph/loading/load_vertices.gsql
   gsql tigergraph/loading/load_edges.gsql
   gsql tigergraph/queries/*.gsql
   ```
   See `tigergraph/README.md` §6/§8 for full load instructions.

2. Set `.env` (from `mcp/.env.example`): `TG_HOST`, `TG_GRAPHNAME=hhg_fraud_graph`, `TG_USERNAME`, `TG_PASSWORD` (or `TG_API_TOKEN`), ports.

3. Verify:
   ```bash
   python mcp/tests/test_connection.py
   # expect: Live TigerGraph OK (or LIVE_TIGERGRAPH_UNAVAILABLE → file_fallback PASS)
   ```

4. In `mcp/tools/_common.py`, `try_live_call()` will attempt `pyTigerGraph` when `TG_HOST` is set; on failure it returns `LIVE_TIGERGRAPH_UNAVAILABLE` and callers fall back to files (marking `source.kind=file_fallback`).

**Never fake live success** — if `TG_HOST` is unset or unreachable, tools report `LIVE_TIGERGRAPH_UNAVAILABLE` or use file-fallback with explicit provenance.

---

## 14. LangGraph Integration Preparation

Prepared for Phase 4 (agent), no agent code in this layer.

| Concern | Preparation in Phase 2 |
|---------|------------------------|
| Transport | Stdio (`tigergraph-mcp`) or streamable-http (`--transport streamable-http --host 0.0.0.0 --port 8000`, `MCP_ENDPOINT`) |
| Discovery | `mcp/tools/investigation_tools.py:discover_tools()`, `get_tool(name)`, `tool_metadata()` |
| Invocation | Each tool is a plain `Callable[..., Dict]` returning a JSON-serializable envelope — bind via LangGraph `Tool` / `StructuredTool` with Pydantic schema from `mcp/schemas/tool_schemas.py` |
| Structured output | `SuccessEnvelope` / `ErrorEnvelope` with `source.kind` (`tigergraph_live` | `file_fallback`), `provenance[]`, `truncated`, `total_count`/`returned_count` |
| Provenance | Every envelope carries `provenance: [{tool, query, entity_ids, ts}]` for audit trail (case file `investigation_steps`) |
| Policy | Agent may only call `CANONICAL_TOOLS` (9); any other name → `POLICY_DENIED` |

Example (Phase 4 sketch):

```python
from mcp.tools.investigation_tools import discover_tools, get_tool
from langchain_core.tools import StructuredTool

tools = [StructuredTool.from_function(
    func=get_tool(name),
    name=name,
) for name in discover_tools(canonical_only=True)]
```

---

## 15. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `mcp` not importable | `tigergraph-mcp` not installed | `pip install tigergraph-mcp` |
| `LIVE_TIGERGRAPH_UNAVAILABLE` | `TG_HOST` unset or unreachable, or `pyTigerGraph` missing | Set `TG_HOST` etc. in `.env`, or rely on file-fallback (`data/vertices/*.csv`) |
| `LIVE_TIGERGRAPH_UNAVAILABLE: pyTigerGraph not installed` | Live attempted without client | `pip install pyTigerGraph` or use file-fallback |
| `POLICY_DENIED` | Tool not in allowlist or blocked upstream name | Check `mcp/config/tool_policy.yaml` allowlist; use canonical 9 |
| `RESOURCE_LIMIT_EXCEEDED` | `max_hops >5` or `limit >200` or `tx_ids >100` | Reduce `max_hops`/`limit` or batch `calculate_exposure` |
| `INVALID_INPUT: txn_id must match ^\d+$` | Non-numeric txn id | Pass numeric string like `"3514030"` |
| `INVALID_INPUT: case_id must match ^HHG-\d{3}$` | Bad benchmark id | Use `HHG-001` … `HHG-020` |
| `NOT_FOUND` | ID not in graph/files | Verify id exists in `data/vertices/*.csv` |
| `NO_DEVICE_FOUND` | In-person txn has no `FROM_DEVICE` edge (65k online without identity, 6,640 valid) | Use region/email/history instead |
| Empty `related_cases` | No historical case shares device/region/card/email | Expected for generic devices — filter by `specificity >= 0.01` |
| `truncated=true` | Result exceeded `MAX_RESULTS` / `MAX_TEMPORAL` | Page or narrow seed; check `total_count` |

---

## 16. References

- Official MCP: https://github.com/tigergraph/tigergraph-mcp
- GSQL queries: `tigergraph/queries/*.gsql`
- Schema: `tigergraph/schema/schema.gsql` (8 vertices, 11 edges)
- Policy: `mcp/config/tool_policy.yaml`
- Schemas: `mcp/schemas/tool_schemas.py`
- Tests: `mcp/tests/test_{connection,tools,security}.py`
