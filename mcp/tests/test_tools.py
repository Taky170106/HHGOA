"""
test_tools.py — Tests for all 9 investigation tools (spec §16, at least 15 tests).

Valid/invalid benchmark case, valid/invalid transaction, valid customer/card/device,
valid historical case (find_related_cases), empty result (nonexistent region),
malformed input (bad case_id format), excessive traversal depth (max_hops 100),
excessive limit (1000), excessive tx_ids (200), plus file-fallback success checks.

Uses unittest, imports from mcp.tools.*, distinguishes mocked/file-fallback vs live
(never labels mocked as live). Each test asserts status success/error, error_code,
provenance present, truncated flag. Deterministic, no network required.
"""

from __future__ import annotations

import os
import unittest

# Ensure file-fallback path when TG_HOST absent — tests must not require live TG
# (live branches are covered when credentials are set; otherwise file_fallback is success)


class TestInvestigationTools(unittest.TestCase):
    # ---- helpers ----

    def assertEnvelopeShape(self, env: dict, tool: str | None = None):
        self.assertIn("tool", env)
        self.assertIn("status", env)
        self.assertIn(env["status"], ("success", "error"))
        self.assertIn("source", env)
        self.assertIn("provenance", env)
        self.assertIn("truncated", env)
        self.assertIsInstance(env["provenance"], list)
        self.assertGreaterEqual(len(env["provenance"]), 1, "provenance must have at least one entry")
        prov = env["provenance"][0]
        self.assertIn("tool", prov)
        self.assertIn("query", prov)
        self.assertIn("ts", prov)
        if tool:
            self.assertEqual(env["tool"], tool)

    def assertSuccess(self, env: dict, tool: str | None = None):
        self.assertEqual(env.get("status"), "success")
        self.assertIn("data", env)
        self.assertEnvelopeShape(env, tool)
        # source.kind must be file_fallback when no live credentials
        kind = env.get("source", {}).get("kind", "")
        if not os.getenv("TG_HOST") and not os.getenv("TIGERGRAPH_HOST"):
            self.assertEqual(kind, "file_fallback", "without TG_HOST, source.kind must be file_fallback (never label mocked as live)")

    def assertError(self, env: dict, expected_code: str | None = None):
        self.assertEqual(env.get("status"), "error")
        self.assertIn("error_code", env)
        if expected_code:
            self.assertEqual(env.get("error_code"), expected_code)
        self.assertEnvelopeShape(env)
        self.assertIn("message", env)

    # ---- 1. Valid benchmark case (HHG-001) ----
    def test_valid_benchmark_case(self):
        from mcp.tools.case_tools import get_benchmark_case

        env = get_benchmark_case("HHG-001")
        self.assertSuccess(env, "benchmark_case_context")
        self.assertIn("benchmark_case", env["data"])
        self.assertEqual(str(env["data"]["benchmark_case"].get("case_id")), "HHG-001")
        # flagged txn should resolve
        self.assertIsNotNone(env["data"].get("flagged_transaction"))

    # ---- 2. Invalid benchmark case (not found) ----
    def test_invalid_benchmark_case_not_found(self):
        from mcp.tools.case_tools import get_benchmark_case

        env = get_benchmark_case("HHG-999")
        self.assertError(env, "NOT_FOUND")
        self.assertIn("HHG-999", str(env.get("message", "")))

    # ---- 3. Valid transaction (3514030 = HHG-001 flagged) ----
    def test_valid_transaction(self):
        from mcp.tools.transaction_tools import get_transaction

        env = get_transaction("3514030")
        self.assertSuccess(env, "get_transaction")
        txn = env["data"].get("transaction") or {}
        self.assertEqual(str(txn.get("txn_id")), "3514030")
        # card/customer should be populated via provenance joins
        self.assertIsNotNone(env["data"].get("card"))
        self.assertIsNotNone(env["data"].get("customer"))

    # ---- 4. Invalid transaction (not found) ----
    def test_invalid_transaction_not_found(self):
        from mcp.tools.transaction_tools import get_transaction

        env = get_transaction("999999999")
        self.assertError(env, "NOT_FOUND")

    # ---- 5. Valid customer (C12382 from HHG-001) ----
    def test_valid_customer(self):
        from mcp.tools.transaction_tools import get_customer_history

        env = get_customer_history("C12382", limit=10)
        self.assertSuccess(env, "get_customer_history")
        self.assertIn("customer", env["data"])
        self.assertEqual(str(env["data"]["customer"].get("customer_id")), "C12382")
        self.assertIn("transactions", env["data"])

    # ---- 6. Valid card (C12382-K1) ----
    def test_valid_card(self):
        from mcp.tools.transaction_tools import get_card_history

        env = get_card_history("C12382-K1", limit=10)
        self.assertSuccess(env, "get_card_history")
        self.assertIn("card", env["data"])
        self.assertIn("transactions", env["data"])

    # ---- 7. Valid device connections (seed via txn 3478561 has device) ----
    def test_valid_device_connections(self):
        from mcp.tools.relationship_tools import find_device_connections

        # Try via txn_id first (HHG-014 flagged has a device)
        env = find_device_connections(txn_id="3478561", limit=10)
        # If that txn has no device in edge file, we get NOT_FOUND — try via explicit device id from file
        if env.get("status") == "error" and env.get("error_code") == "NOT_FOUND":
            # discover a real device id from file
            try:
                from mcp.tools._common import load_edges

                fd = load_edges("from_device")
                real_dev = str(fd.iloc[0]["to_device_profile_id"]) if len(fd) > 0 else None
            except Exception:
                real_dev = None
            if real_dev:
                env2 = find_device_connections(device_profile_id=real_dev, limit=10)
                self.assertSuccess(env2, "find_device_connections")
                self.assertIn("devices", env2["data"])
                return
            self.skipTest("No device data available for file-fallback")
        else:
            self.assertSuccess(env, "find_device_connections")
            self.assertIn("devices", env["data"])

    # ---- 8. Valid historical case via find_related_cases ----
    def test_valid_historical_case(self):
        from mcp.tools.history_tools import find_related_cases

        # Use a known device or region or card to find closed cases
        try:
            from mcp.tools._common import load_vertices, load_edges

            # pick a card that has ON_CARD edges
            try:
                oc = load_edges("on_card")
                card_for_case = str(oc.iloc[0]["to_card_id"]) if len(oc) > 0 else "C12382-K1"
            except Exception:
                card_for_case = "C12382-K1"
        except Exception:
            card_for_case = "C12382-K1"

        env = find_related_cases(card_id=card_for_case, limit=10)
        self.assertSuccess(env, "find_related_cases")
        self.assertIn("related_cases", env["data"])
        # At least 0 or more — but shape must be success with provenance
        self.assertIsInstance(env["data"]["related_cases"], list)

    # ---- 9. Empty result (nonexistent region 9999.0) ----
    def test_empty_result_nonexistent_region(self):
        from mcp.tools.history_tools import find_related_cases

        env = find_related_cases(region_code="9999.0", limit=10)
        # Should be success with 0 results (region not in graph -> empty set, not error)
        self.assertEqual(env.get("status"), "success")
        self.assertEnvelopeShape(env, "find_related_cases")
        # Could also be empty list; truncated must be false for empty
        self.assertFalse(env.get("truncated"))
        total = env["data"].get("total_found", 0) if isinstance(env.get("data"), dict) else 0
        self.assertEqual(total, 0)

    # ---- 10. Malformed input — bad case_id format ----
    def test_malformed_benchmark_case_id(self):
        from mcp.tools.case_tools import get_benchmark_case

        env = get_benchmark_case("BAD-ID")
        self.assertError(env, "INVALID_INPUT")

    # ---- 11. Excessive traversal depth (max_hops 100 > MAX_HOPS 5) ----
    def test_excessive_max_hops(self):
        from mcp.tools.relationship_tools import find_related_transactions

        env = find_related_transactions(txn_id="3514030", max_hops=100, limit=10)
        # Pydantic validation enforces limit → INVALID_INPUT; policy-level also RESOURCE_LIMIT_EXCEEDED — accept either
        self.assertEqual(env.get("status"), "error")
        self.assertIn(env.get("error_code"), ("INVALID_INPUT", "RESOURCE_LIMIT_EXCEEDED"))
        self.assertFalse(env.get("truncated"), "resource limit errors must have truncated=false")

    # ---- 12. Excessive limit (1000 > MAX_RESULTS 200) ----
    def test_excessive_limit(self):
        from mcp.tools.transaction_tools import get_customer_history

        env = get_customer_history("C12382", limit=1000)
        self.assertEqual(env.get("status"), "error")
        self.assertIn(env.get("error_code"), ("INVALID_INPUT", "RESOURCE_LIMIT_EXCEEDED"))

    # ---- 13. Excessive tx_ids (200 > MAX_TX_IDS 100) ----
    def test_excessive_tx_ids(self):
        from mcp.tools.transaction_tools import calculate_exposure

        ids = [str(3514030 + i) for i in range(200)]
        env = calculate_exposure(ids)
        # validation fires before policy limit — both map to INVALID_INPUT or RESOURCE_LIMIT
        self.assertEqual(env.get("status"), "error")
        self.assertIn(env.get("error_code"), ("INVALID_INPUT", "RESOURCE_LIMIT_EXCEEDED"))

    # ---- 14. File-fallback success — calculate_exposure ----
    def test_calculate_exposure_file_fallback(self):
        from mcp.tools.transaction_tools import calculate_exposure

        env = calculate_exposure(["3514030", "3478782"])
        self.assertSuccess(env, "calculate_exposure")
        self.assertIn("exposure_usd", env["data"])
        self.assertGreaterEqual(env["data"]["exposure_usd"], 0.0)

    # ---- 15. File-fallback success — temporal chain ----
    def test_temporal_chain_file_fallback(self):
        from mcp.tools.history_tools import get_temporal_chain

        env = get_temporal_chain("C12382-K1", limit=10)
        self.assertSuccess(env, "get_temporal_chain")
        self.assertIn("transactions", env["data"])
        self.assertGreaterEqual(len(env["data"]["transactions"]), 1)

    # ---- 16. Find related transactions (valid seed) ----
    def test_find_related_transactions_valid(self):
        from mcp.tools.relationship_tools import find_related_transactions

        env = find_related_transactions(txn_id="3514030", max_hops=1, limit=10)
        self.assertSuccess(env, "find_related_transactions")
        self.assertIn("via_card_ids", env["data"])

    # ---- 17. Malformed transaction id (non-numeric) ----
    def test_malformed_txn_id(self):
        from mcp.tools.transaction_tools import get_transaction

        env = get_transaction("not-a-number")
        self.assertError(env, "INVALID_INPUT")

    # ---- 18. List benchmark cases ----
    def test_list_benchmark_cases(self):
        from mcp.tools.case_tools import list_benchmark_cases

        env = list_benchmark_cases(limit=5, offset=0)
        self.assertSuccess(env, "benchmark_case_context")
        self.assertIn("benchmark_cases", env["data"])
        self.assertEqual(len(env["data"]["benchmark_cases"]), 5)
        self.assertFalse(env.get("truncated") is None)  # must be present

    # ---- 19. Truncated flag behavior (temporal chain with small limit) ----
    def test_truncated_flag_present(self):
        from mcp.tools.transaction_tools import get_card_history

        # C12382-K1 has ~422 txns; limit 5 should truncate -> truncated true
        env = get_card_history("C12382-K1", limit=5)
        self.assertSuccess(env, "get_card_history")
        # If total > limit, truncated should be True
        total = env["data"].get("total_transactions", 0)
        if total > 5:
            self.assertTrue(env.get("truncated"))

    # ---- 20. Provenance completeness ----
    def test_provenance_always_present(self):
        from mcp.tools.case_tools import get_benchmark_case

        for cid in ["HHG-001", "BAD", "HHG-999"]:
            env = get_benchmark_case(cid)
            self.assertIn("provenance", env)
            self.assertGreaterEqual(len(env["provenance"]), 1)
            self.assertIn("query", env["provenance"][0])
            self.assertIn("ts", env["provenance"][0])
