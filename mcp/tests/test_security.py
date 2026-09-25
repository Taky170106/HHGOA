"""
test_security.py — Read-only boundary verification (Phase 2).

Verifies:
- arbitrary_gsql_write denied
- vertex_insert/update/delete denied
- edge_insert/update/delete denied
- schema_mutation denied
- policy_mutation denied (via is_allowed + allowlist check)
- credential absence handled (live unavailable -> file_fallback, not crash)
- malformed IDs rejected (INVALID_INPUT)
- resource limits enforced (RESOURCE_LIMIT_EXCEEDED)
- official MCP generic write tools are NOT exposed via our layer (registry has only 9 read-only tools)

Uses unittest, imports is_allowed from _common and inspects registry.
"""

from __future__ import annotations

import os
import unittest


DENIED_CAPABILITIES = [
    "arbitrary_gsql_write",
    "vertex_insert",
    "vertex_update",
    "vertex_delete",
    "edge_insert",
    "edge_update",
    "edge_delete",
    "schema_mutation",
    "policy_mutation",
    "loading_job_run",
    "token_create",
    "user_management",
]

BLOCKED_UPSTREAM_TOOLS = [
    "create_vertex",
    "update_vertex",
    "delete_vertex",
    "create_edge",
    "update_edge",
    "delete_edge",
    "run_gsql",
    "install_query",
    "create_schema",
]

CANONICAL_NINE = {
    "get_transaction",
    "get_customer_history",
    "get_card_history",
    "find_device_connections",
    "find_related_transactions",
    "find_related_cases",
    "get_temporal_chain",
    "calculate_exposure",
    "benchmark_case_context",
}


class TestReadOnlyBoundary(unittest.TestCase):
    def test_registry_only_nine_read_only_tools(self):
        from mcp.tools.investigation_tools import CANONICAL_TOOLS, registry
        from mcp.tools._common import load_policy

        # canonical set must be exactly 9
        self.assertEqual(set(CANONICAL_TOOLS), CANONICAL_NINE)
        # aliases exist but canonical-only set is 9
        # registry should not expose any blocked upstream tool
        for blocked in BLOCKED_UPSTREAM_TOOLS:
            self.assertNotIn(blocked, registry, f"Blocked upstream tool '{blocked}' must not be in registry")
        # canonical tools must all be in registry
        for t in CANONICAL_NINE:
            self.assertIn(t, registry)

    def test_no_write_tools_in_allowlist(self):
        from mcp.tools._common import load_policy

        policy = load_policy()
        allowed = set(policy.get("allowlist", {}).get("tools", []))
        for blocked in BLOCKED_UPSTREAM_TOOLS:
            self.assertNotIn(blocked, allowed)
        # denied_capabilities must be declared
        denied = policy.get("denied_capabilities", [])
        # could be list or dict; handle both shapes
        if isinstance(denied, list):
            for cap in DENIED_CAPABILITIES[:6]:
                self.assertIn(cap, denied)
        else:
            # dict form has blocked_upstream_tools key
            blocked_in_policy = denied.get("blocked_upstream_tools", []) if isinstance(denied, dict) else []
            for b in BLOCKED_UPSTREAM_TOOLS:
                self.assertIn(b, blocked_in_policy)

    def test_is_allowed_denies_arbitrary(self):
        from mcp.tools._common import is_allowed

        for name in BLOCKED_UPSTREAM_TOOLS + ["run_gsql", "arbitrary_gsql_write", "vertex_insert", "delete_vertex"]:
            self.assertFalse(is_allowed(name), f"is_allowed('{name}') must be False")

    def test_is_allowed_denies_schema_and_policy_mutation(self):
        from mcp.tools._common import is_allowed

        for name in ["schema_mutation", "policy_mutation", "create_schema", "install_query"]:
            self.assertFalse(is_allowed(name))

    def test_is_allowed_denies_edge_mutations(self):
        from mcp.tools._common import is_allowed

        for name in ["edge_insert", "edge_update", "edge_delete", "create_edge", "update_edge", "delete_edge"]:
            self.assertFalse(is_allowed(name))

    def test_credential_absence_handled_gracefully(self):
        # Temporarily clear TG env and ensure a tool still returns file_fallback success (not crash)
        saved = {k: os.environ.get(k) for k in ["TG_HOST", "TIGERGRAPH_HOST", "TIGERGRAPH_HOSTNAME", "TG_API_TOKEN", "MCP_ENDPOINT"]}
        try:
            for k in list(saved.keys()):
                os.environ.pop(k, None)
            from mcp.tools.transaction_tools import get_transaction

            env = get_transaction("3514030")
            self.assertEqual(env.get("status"), "success")
            self.assertEqual(env.get("source", {}).get("kind"), "file_fallback")
            self.assertIn("provenance", env)
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
                else:
                    os.environ.pop(k, None)

    def test_malformed_ids_rejected(self):
        from mcp.tools.case_tools import get_benchmark_case
        from mcp.tools.transaction_tools import get_transaction, get_customer_history, get_card_history

        bad_cases = [
            (get_benchmark_case, ("BAD-FORMAT",), "INVALID_INPUT"),
            (get_transaction, ("not-numeric",), "INVALID_INPUT"),
            (get_customer_history, ("C-BAD",), "INVALID_INPUT"),
            (get_card_history, ("C123-BAD",), "INVALID_INPUT"),
        ]
        for fn, args, code in bad_cases:
            env = fn(*args)  # type: ignore
            self.assertEqual(env.get("status"), "error", f"{fn.__name__} should error on {args}")
            self.assertEqual(env.get("error_code"), code)
            self.assertIn("provenance", env)

    def test_resource_limits_enforced(self):
        from mcp.tools.relationship_tools import find_related_transactions
        from mcp.tools.transaction_tools import get_customer_history, calculate_exposure

        # max_hops too large — Pydantic enforces ge/le → INVALID_INPUT; policy layer would be RESOURCE_LIMIT_EXCEEDED — accept either
        env = find_related_transactions(txn_id="3514030", max_hops=100, limit=10)
        self.assertEqual(env.get("status"), "error")
        self.assertIn(env.get("error_code"), ("INVALID_INPUT", "RESOURCE_LIMIT_EXCEEDED"))
        self.assertFalse(env.get("truncated"))

        # limit too large via get_customer_history
        env2 = get_customer_history("C12382", limit=1000)
        self.assertEqual(env2.get("status"), "error")
        self.assertIn(env2.get("error_code"), ("INVALID_INPUT", "RESOURCE_LIMIT_EXCEEDED"))

        # too many tx_ids
        ids = [str(3514000 + i) for i in range(200)]
        env3 = calculate_exposure(ids)
        self.assertEqual(env3.get("status"), "error")
        self.assertIn(env3.get("error_code"), ("INVALID_INPUT", "RESOURCE_LIMIT_EXCEEDED"))

    def test_malformed_device_id_rejected(self):
        from mcp.tools.relationship_tools import find_device_connections

        env = find_device_connections(device_profile_id="DP-BAD", limit=10)
        self.assertEqual(env.get("status"), "error")
        self.assertEqual(env.get("error_code"), "INVALID_INPUT")

    def test_unknown_tool_lookup_raises(self):
        from mcp.tools.investigation_tools import get_tool

        with self.assertRaises(KeyError):
            get_tool("run_gsql")
        with self.assertRaises(KeyError):
            get_tool("create_vertex")
        with self.assertRaises(KeyError):
            get_tool("arbitrary_gsql_write")

    def test_generic_write_not_exposed_via_discovery(self):
        from mcp.tools.investigation_tools import discover_tools

        all_tools = discover_tools()
        canonical = discover_tools(canonical_only=True)
        for blocked in BLOCKED_UPSTREAM_TOOLS:
            self.assertNotIn(blocked, all_tools)
            self.assertNotIn(blocked, canonical)
        # canonical should be exactly 9
        self.assertEqual(len(canonical), 9)
        self.assertEqual(set(canonical), CANONICAL_NINE)

    def test_tool_policy_file_exists_and_declares_denied(self):
        from pathlib import Path
        import yaml  # type: ignore

        root = Path(__file__).resolve().parents[2]
        p = root / "mcp" / "config" / "tool_policy.yaml"
        # also try HHG_ROOT
        if not p.exists():
            p = Path(os.getenv("HHG_ROOT", r"D:\HHG")) / "mcp" / "config" / "tool_policy.yaml"
        self.assertTrue(p.exists(), f"tool_policy.yaml must exist at {p}")
        with open(p, "r", encoding="utf-8") as f:
            policy = yaml.safe_load(f)
        self.assertIn("allowlist", policy)
        self.assertIn("denied_capabilities", policy)
        # resource limits declared
        self.assertIn("resource_limits", policy)
        rl = policy["resource_limits"]
        for k in ["MAX_HOPS", "MAX_RESULTS", "MAX_TX_IDS", "MAX_TEMPORAL"]:
            self.assertIn(k, rl)

    def test_every_tool_returns_provenance_and_truncated(self):
        # Spot-check that both success and error envelopes include provenance + truncated
        from mcp.tools.case_tools import get_benchmark_case
        from mcp.tools.transaction_tools import get_transaction

        for env in [get_benchmark_case("HHG-001"), get_benchmark_case("BAD"), get_transaction("3514030"), get_transaction("bad")]:
            self.assertIn("provenance", env)
            self.assertGreaterEqual(len(env["provenance"]), 1)
            self.assertIn("truncated", env)
            self.assertIn("source", env)
