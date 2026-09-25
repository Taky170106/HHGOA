# Phase 0 — Final Validation Report

**Verified against**: `DATASET/transactions.csv`, `identity.csv`, `closed_cases_history.csv`, `case_pack.csv`, `DATASET/README.md`
**Validation method**: pandas recomputation from raw files (scripts: `validate_edges.py`, `validate_gsql_policy_schema.py`, `validate_exposure.py`, `validate_exposure2.py`)

---

## 1. Graph Edges vs Actual Rows

| # | Edge | Claimed | Verified Actual | Verdict |
|---|------|---------|-----------------|---------|
| 1 | Customer OWNS Card | 13,553 (1:1) | 13,553 pairs; 0 customers with >1 card1 | ✅ |
| 2 | Card MADE Transaction | 590,742 | 590,742 rows, 13,553 unique cards | ✅ |
| 3 | Transaction BILLED_IN BillingRegion | ~525K | 525,003 (addr1 non-null); 332 unique | ✅ |
| 4 | Transaction PURCHASER_EMAIL EmailDomain | ~590K (was) | **496,262** (84.0%); 59 unique | ⚠️ FIXED → 496,262 |
| 5 | Transaction RECIPIENT_EMAIL EmailDomain | ~135K | 137,453; 60 unique | ✅ |
| 6 | Transaction FROM_DEVICE DeviceProfile | 144,432 | 144,432; online missing = 6,640; 9,706 profiles | ✅ |
| 7 | Transaction NEXT Transaction | ~577K | 577,189 | ✅ |
| 8 | ClosedCase INVOLVES Transaction | ~20K+ (was) | **14,955** parsed; 0 IDs missing from txns | ⚠️ FIXED → 14,955 |
| 9 | ClosedCase ON_CARD Card | 5,565 | 5,565; 1,913 unique card_ids | ✅ |
| 10 | ClosedCase CONNECTED_TO Card | ~88/22-ring (was) | **92 edges: 4 cases × 23 cards** (CC-2649/2971/2985/3035) | ⚠️ FIXED → 92 (4×23) |
| 11 | BenchmarkCase TRIGGERS Transaction | 20 | 20/20 found | ✅ |

---

## 2. All 20 Case → Transaction Joins

- **20/20 flagged_txn_id** found in transactions.csv
- **20/20 customer_id** on flagged txn matches case_pack customer_id
- **11/11 risk_score triggers** match transaction risk_score exactly (≤0.001)
- **14 cases have identity records; 6 do not** (5 in_person: HHG-001/003/007/012/018; 1 online-without-identity: HHG-002)
- Trigger distribution: 11 risk_score, 8 customer_report, 1 analyst_request ✅

---

## 3. GSQL Query Feasibility

| Query | Feasibility Evidence | Verdict |
|-------|---------------------|---------|
| card_window (R5 card testing) | 3+ small online auths + larger purchase observable; per-card ts ordering works | ✅ |
| device_neighbors | 9,706 profiles; 5,564 profiles have >1 txn; reverse traversal data exists | ✅ |
| region novelty (Pattern 4) | 37,531 customer-region pairs; C12382 has 40 addr1 (as reported) | ✅ |
| channel-switch (Pattern 5 ATO) | 3,871 cards show ≥1 channel switch | ✅ |
| related fraud cases (shared entity) | 5,565 cases; 4 with connected_card_ids; 1,913 unique cards | ✅ |
| exposure calculation | Recomputes exactly for confirmed-fraud cases (0/100 mismatches) | ✅ |
| evidence retrieval | Closed-case narratives + policy + README available for embedding | ✅ |

**Exposure formula verified**: for 100 sampled confirmed-fraud cases, `sum(abs(txn amounts in txn_ids))` == `exposure_usd` exactly. All 900 cleared cases correctly have exposure 0 (their txn_ids exist but no fraud identified).

---

## 4. Policy Rules vs README

- All 10 rules (R1–R10) transcribed **verbatim** from README Fraud Policy (lines 231-243)
- Action names (14) and approval routes (`auto`/`L1`/`L2`) match README exactly
- Case-vs-SAR distinction (3a), next-best-action change (3b), exposure (4), evidence gathering (5), stopping (6), explaining (7) — all match README sections

---

## 5. JSON Output Schema vs README Answer Format

| Component | Fields | Verdict |
|-----------|--------|---------|
| Top-level | 9 (case_id, case, evidence_requests, next_best_actions, sar, stop_reason, tool_calls, tokens, latency_s) | ✅ |
| `case` | 15 (status, verdict, fraud_probability, pattern, pattern_description, affected_txn_ids, first_suspicious_txn_id, connected_card_ids, connected_device_profiles, exposure_usd, evidence, similar_prior_cases, summary, written_to_graph, graph_case_id) | ✅ |
| `sar` | 6 (file, reason, narrative, subjects, total_amount_usd, activity_dates) | ✅ |
| `next_best_actions` | 3 (initial, final, what_changed) | ✅ |
| `evidence_requests` item | 3 (type, asked_after_step, assumed_response) | ✅ |
| `evidence` item | 4 (claim, source, ref, entity_ids) | ✅ |
| Enums | pattern(7), status(4), verdict(3), route(3), source(4), request_type(3) | ✅ |

---

## 6. No Invented Entity/Field Semantics

- **Entities rejected for lack of data**: Merchant, IP Address, Address, Phone, Organization — no identifiers exist anywhere in the dataset (verified: no merchant column; no IP column; addr1/addr2 are region/country codes only; C-counts are aggregate counts, not raw identifiers)
- **Unnamed features flagged as signals only**: V1–V339, C1–C14, D1–D15, M1–M9, id_01–id_11 are all explicitly marked evidence-only (not claimed to mean specific things)
- **Every entity/relationship has a source column + join key cited** in ENTITY_MODEL.md / RELATIONSHIP_MODEL.md
- **No fabricated IDs**: all example IDs in deliverables (transaction IDs, case IDs, customer IDs) come from actual dataset rows

---

## Errors Found and Fixed During Validation

| Deliverable | Error | Fix |
|-------------|-------|-----|
| RELATIONSHIP_MODEL.md | PURCHASER_EMAIL ~590K | → 496,262 |
| RELATIONSHIP_MODEL.md | CONNECTED_TO ~88, 22-card | → 92 (4×23) |
| RELATIONSHIP_MODEL.md | INVOLVES ~20K+ | → 14,955 |
| TIGERGRAPH_SCHEMA_PROPOSAL.md | PURCHASER_EMAIL ~590K | → 496,262 |
| TIGERGRAPH_SCHEMA_PROPOSAL.md | CONNECTED_TO ~88 | → 92 (4×23) |
| ENTITY_MODEL.md / FILE_INVENTORY.md | 22-card ring | → 23-card ring (4 cases) |
| FRAUD_PATTERNS.md | Undocumented A=5, B=4 | → A=4 (CC-2649/2971/2985/3035), B=5 (CC-3748/3841/3907/4086/4124) |
| PHASE0_FINAL_REPORT.md | Same pattern-count swap + "11 have identity" + Q1 typo ("el culata") | All corrected (14 with identity; A=4/B=5; Q1 text fixed) |

---

## Validation Verdict

**PASS** — All high-signal claims in the Phase 0 deliverables are now verified against raw data and README. The 6 numerical/pattern-count errors found were corrected in place; no remaining unverifiable claims.

**Residual unknowns (documented, not errors)**:
- V/C/D/M/id feature semantics (unnamed by Vesta by design — marked evidence-only)
- Exact merchant identity (no merchant field exists)
- Card1↔CXXXX-KY mapping requires load-time bridge via customer_id (design decision, Q1)