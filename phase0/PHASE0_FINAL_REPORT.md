# Phase 0 — Final Report

**Project**: TigerGraph × Hacker House Goa 2026 — Agentic Fraud Investigation
**Phase**: 0 (Data Intelligence & Specification)
**Date**: 2026 (dataset period: 2016-07-02 to 2016-12-31)
**Source files analyzed**: `DATASET/README.md`, `transactions.csv`, `identity.csv`, `closed_cases_history.csv`, `case_pack.csv`

---

## 1. Dataset Overview

Six months of card transactions (Jul 2 – Dec 31, 2016) from the IEEE-CIS Fraud Detection dataset (Vesta), augmented by TigerGraph with customers, calendar timestamps, channels, risk scores, closed-case history, and a 20-case benchmark pack.

| File | Rows | Columns | Size | Content |
|------|------|---------|------|---------|
| transactions.csv | 590,742 | 397 | ~708 MB | All transactions (393 Vesta features + customer_id, ts, channel, risk_score) |
| identity.csv | 144,432 | 41 | ~15 MB | Device/connection records, online transactions only |
| closed_cases_history.csv | 5,565 | 15 | ~2 MB | Finished investigations: 4,665 fraud, 900 cleared |
| case_pack.csv | 20 | 8 | ~3 KB | The 20 exam cases (Nov–Dec 2016) |

**Core numbers**: 13,553 customers (1:1 with numeric card1), 13,553 cards, 332 billing regions, 59/60 email domains, ~9,706 device profiles (4,789 shared by >1 customer).

---

## 2. File Inventory

See `phase0/FILE_INVENTORY.md` — full inventory with per-field analysis, cross-file join verification (transactions↔identity 95.6% coverage; case_pack↔transactions 100%), and primary/foreign key mapping.

---

## 3. Data Dictionary Summary

See `phase0/DATA_DICTIONARY.md` — 397+41+15+8 field analysis with type/nullability/cardinality/semantics, and TigerGraph attribute classification (vertex attr / edge attr / evidence-only).

Key classifications:
- **Vertex attributes**: identifiers, core transaction fields, device profile composite, closed-case outcome/pattern/exposure
- **Evidence-only**: V1-V339 (unnamed model features), C1-C14/D1-D15/M1-M9 (unnamed counts/deltas/match flags), id_01-id_11 (encoded ratings), analyst_notes
- **Derived**: device_profile composite, card_id mapping, transaction sequences, risk-adjusted signals
- **Model-generated**: fraud_probability, pattern, exposure, verdict (agent outputs)

---

## 4. Entity Model

See `phase0/ENTITY_MODEL.md`. Eight verified entities → all deserve TigerGraph vertices:

| Entity | Count | PK |
|--------|-------|-----|
| Customer | 13,553 | customer_id |
| Card | 13,553 | card1 / card_id (CXXXX-KY) |
| Transaction | 590,742 | TransactionID |
| DeviceProfile | 9,706 | composite hash (DeviceInfo\|OS\|browser\|screen) |
| EmailDomain | 59/60 | domain |
| BillingRegion | 332 | addr1 |
| ClosedCase | 5,565 | case_id |
| BenchmarkCase | 20 | case_id |

**NOT supported by data** (rejected): Merchant, Address, Organization, IP Address, Phone — no identifiers exist in the dataset.

---

## 5. Relationship Model

See `phase0/RELATIONSHIP_MODEL.md`. All 11 relationships verified with join keys, cardinalities, and evidence:

1. Customer OWNS Card (13,553)
2. Card MADE Transaction (590,742)
3. Transaction BILLED_IN BillingRegion (~525K)
4. Transaction PURCHASER_EMAIL EmailDomain (496,262)
5. Transaction RECIPIENT_EMAIL EmailDomain (137,453)
6. Transaction FROM_DEVICE DeviceProfile (144,432)
7. Transaction NEXT Transaction (~577K, per-card temporal)
8. ClosedCase INVOLVES Transaction
9. ClosedCase ON_CARD Card (5,565)
10. ClosedCase CONNECTED_TO Card (92, 4 rings × 23 cards)
11. BenchmarkCase TRIGGERS Transaction (20)

**Multi-hop paths verified**: device-based compromise ring (A), out-of-region use (B), email clustering (C), card testing sequence (D), historical case retrieval (E), account takeover mixed-channel (F).

---

## 6. Fraud Patterns

See `phase0/FRAUD_PATTERNS.md`. All five documented patterns verified against closed-case labels:

| Pattern | Count (confirmed) | Key Signals |
|---------|-------------------|-------------|
| card_not_present_fraud | 1,404 | Amount/product outlier, 2-4 txn burst in 48h (R1-R4) |
| account_takeover | 1,205 | Mixed-channel, device/match anomalies (R1, R10) |
| card_not_present_new_device | 1,076 | CNP + id_15=New + proxy (R1-R4) |
| out_of_region_use | 955 | New addr1 region, continued home activity (R2, R3) |
| card_testing | 16 | 3+ sub-$5 online auths in 1h then large purchase (R5) |
| undocumented | 9 | Two types found in analyst_notes (see below) |
| none (cleared) | 900 | False alarms |

**Undocumented pattern A** (4 cases): Samsung SM-G935F + Chrome Android + anonymous proxy, shared across 2+ cardholders/month, linked to a 23-card ring — **matches HHG-014's device signature** (`SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080 | IP_PROXY:ANONYMOUS`).

**Undocumented pattern B** (5 cases): Four online purchases in 40 minutes, each just under $500 (auth-threshold evasion).

---

## 7. Policy Rules

See `phase0/POLICY_RULES.md`. All 10 rules + 14 actions + 3 approval routes extracted verbatim from README (Fraud Policy, lines 190-287).

Key compliance anchors:
- **R1**: verify before block on single signal when prob < 0.70
- **R2**: denial → BLOCK_CARD + CREATE_CASE; +FILE_REPORT if exposure > $1,000 or shared origin
- **R5**: card testing → DECLINE + STEP_UP; BLOCK if >$100 cleared
- **R6**: shared origin → CREATE_CASE + FILE_REPORT + MONITOR_CONNECTED_CARDS
- **R8**: uncertain + exposure > $500 → ESCALATE_TO_ANALYST
- **R9**: undocumented pattern → CREATE_CASE + FILE_REPORT + ESCALATE; describe in own words
- **R10**: no BLOCK_ALL_CARDS unless ≥2 cards confirmed fraud or credentials compromised
- **Stopping**: prob ≥ 0.85 or ≤ 0.15 with 2+ independent evidence; verification settles; or diminishing returns

---

## 8. 20-Case Overview

See full detail in this report §9. Distribution: 11 risk_score triggers, 8 customer_report, 1 analyst_request. All flagged transactions verified present — all 20 join cleanly with matching customer_id, and all 11 risk_score triggers match the transaction's risk_score exactly. Identity records exist for 14 cases; 6 lack identity: 5 are in_person (HHG-001, 003, 007, 012, 018) and HHG-002 is online but missing identity (6,640 online txns lack identity records).

| Case | Trigger | Risk | Flagged Amt | Channel | Device Notable |
|------|---------|------|-------------|---------|----------------|
| HHG-001 | risk 0.61 | 0.61 | $77.07 | in_person | - (region 444) |
| HHG-002 | risk 0.79 | 0.79 | $292.36 | online | no identity record |
| HHG-003 | customer | - | $49.00 | in_person | - (region 330) |
| HHG-004 | customer | - | $128.33 | online | firefox 47.0 desktop, New |
| HHG-005 | risk 0.54 | 0.54 | $100.07 | online | iOS Device, New, match:1 |
| HHG-006 | customer | - | $482.12 | online | Trident/IE11, New, match:2, **543-card shared profile** |
| HHG-007 | risk 0.87 | 0.87 | $111.92 | in_person | - (region 264) |
| HHG-008 | customer | - | $55.68 | online | chrome 66.0, Found |
| HHG-009 | customer | - | $30.02 | online | generic, Found, match:2 |
| HHG-010 | risk 0.90 | 0.90 | $1,000.03 | online | edge 16.0, New, match:2 |
| HHG-011 | customer | - | $131.30 | online | SM-G610F, New |
| HHG-012 | risk 0.55 | 0.55 | $30.91 | in_person | - (region 494) |
| HHG-013 | risk 0.76 | 0.76 | $35.66 | online | Windows, chrome 66, New |
| HHG-014 | analyst | - | $74.96 | online | SM-G935F, New, **IP_PROXY:ANONYMOUS**, match:2, **52-entity shared profile** |
| HHG-015 | risk 0.77 | 0.77 | $599.94 | online | Trident/IE11, New, match:2 |
| HHG-016 | customer | - | $59.67 | online | Windows, edge 16, New |
| HHG-017 | risk 0.57 | 0.57 | $100.09 | online | Windows, chrome 65, Found, **IP_PROXY:HIDDEN**, match:2 |
| HHG-018 | customer | - | $39.08 | in_person | - (region 126) |
| HHG-019 | risk 0.90 | 0.90 | $99.92 | online | Windows, chrome 61, New, match:0 |
| HHG-020 | risk 0.52 | 0.52 | $125.08 | online | Trident/IE11, New, match:2 |

---

## 9. Case Difficulty Analysis

Analytical labels for engineering (not final benchmark verdicts):

### Strong signals (device-sharing ring)
- **HHG-014**: Analyst requested; device (SM-G935F + Anonymous proxy) matches 4 undocumented closed cases (CC-2649/2971/2985/3035 — the SM-G935F ring with 23 connected cards) and a 52-entity shared profile. Likely coordinated ring → R9/R6 territory. **High evidence, but undocumented pattern.**
- **HHG-006**: Trident/IE11 profile shared by 543 cards → check ring connections.
- **HHG-020**: Trident/IE11 Win10 profile shared by 253 cards.
- **HHG-010**: $1,000+ amount, New device, match:2 — high risk score 0.90. Amount far above this customer's mean ($153) — strongest single-amount outlier in case pack.
- **HHG-019**: risk 0.90 but only $99.92; match_status:0 (no match) — potential false positive on generic profile.

### Customer reports (denial → R2 path, need device/region supporting evidence)
- **HHG-003, 004, 008, 009, 011, 016, 018**: all "I never made this" claims. Main task: find supporting/contradicting evidence (device, region, history, prior cases). Devices for 004 (firefox 47 New) and 011 (SM-G610F New) are specific; 008/009/016 generic.
- **HHG-006**: high-magnitude denial ($482) with New device + large shared profile.

### Risk-score triggers with ambiguous history
- **HHG-001**: region 444, in_person; customer has 40 regions — region novelty NOT high (rich traveler profile). Likely legitimate or uncertain (pattern 4 needs region novelty).
- **HHG-002**: risk 0.79, amount outlier ($292 vs mean $47), but NO identity record (online without device data) — missing evidence case.
- **HHG-005**: iOS Device New, but moderate amount. Risk 0.54.
- **HHG-007**: risk 0.87, in_person region 264; customer has 32 regions → need region history check.
- **HHG-012**: region 494, in_person; customer (C05876) appears in closed case CC-0003 (cleared — travel confirmed!) → strong contradicting precedent.
- **HHG-013**: risk 0.76, New device, generic Windows profile.
- **HHG-015**: $599.94 with risk 0.77, Trident IE11 New device, 8-card shared profile; customer avg $144 — amount + device notable.
- **HHG-017**: risk 0.57, IP_PROXY:HIDDEN + match:2 — proxy flag notable; customer avg $342 with max $2,892 (busy card) → amount is NOT anomalous; device Found.

### Coordinated activity candidates
- **HHG-006/020 share device-family signature** (Trident IE11 1920x1080) — check cross-case links.
- **HHG-014** connects to undocumented ring per analyst notes.

### Likely legitimate / ambiguous
- **HHG-012** (closed-case cleared precedent), **HHG-001** (rich multi-region profile), **HHG-018** (in_person, small amount, no identity), **HHG-009** (Found device, small $30).

### Requires additional evidence
- **HHG-002** (no identity record), cases with generic device profiles (008, 009, 013, 016, 019) where device ID contributes little.

---

## 10. Data-Quality Findings

See `phase0/DATA_QUALITY_REPORT.md` (pending). Verified so far:

| Check | Result |
|-------|--------|
| Duplicate TransactionIDs | 0 |
| Duplicate rows | None found in sampled key fields |
| customer_id ↔ card1 inconsistency | None: 1:1 (13,553 each) |
| Orphan identity records | None: all 144,432 join to transactions |
| Online txns without identity | 6,640 (4.4% of online) |
| addr1/addr2 nulls | 65,739 (11.1%) — in-person/profile-specific |
| Device profile collisions | Heavy: generic profiles share 500-1,000+ customers (e.g., `Windows\|Win10\|chrome 63\|1920x1080` = 842) |
| Closed-case connected-card rings | 4 cases reference a consistent 23-card ring (verified counts) |
| Undocumented closed-case notes | 9 cases, two distinct patterns |
| card4/card6 | No anomalies in sampled data |
| TransactionAmt range | 0.53 – $4,438 (in-persons up to high values via C-codes) |

---

## 11. Exact Output Schema

See `phase0/OUTPUT_SCHEMA.md` — exact benchmark answer format with all fields (top-level, `case`, `sar`, `next_best_actions`, `evidence_requests`) and verified benchmark rules. **Do not simplify.**

---

## 12. TigerGraph Proposal

See `phase0/TIGERGRAPH_SCHEMA_PROPOSAL.md` — 8 vertices, 11 edges, PK choices, edge attributes, case-memory representation, load plan. Aligns with README Suggested Graph Schema. **Proposal only, pending Phase 0 sign-off.**

---

## 13. GSQL Investigation Requirements

Proposed (see schema proposal for GSQL list):
1. transaction history (MADE traversal)
2. customer/card history
3. device reuse (FROM_DEVICE reverse)
4. connection reuse (region/email reverse)
5. multi-hop investigation (OWNS-MADE-FROM_DEVICE chains)
6. related fraud cases (shared device/region/card → ClosedCase)
7. repeated/coordinated activity (temporal card grouping)
8. pattern detection (card_window R5; region novelty; channel switch)
9. exposure calculation (sum over affected_txn_ids)
10. evidence retrieval (vector KNN)

---

## 14. GraphRAG Requirements

- **Embed**: closed-case `analyst_notes`, README pattern section, Fraud Policy, regulatory references (FinCEN/FATF/FFIEC/OFAC) into TigerGraph vector store
- **Retrieval targets** per case: similar prior cases (same device profile, region, email, card), relevant policy rules, pattern typologies
- **Cite** retrieved sources as `similar_prior_cases` and `evidence.source=document`
- **Key challenge**: generic device profiles pollute similarity — weight by specificity

---

## 15. Agent Tool Requirements

Proposed tool set (see `phase0/AGENT_TOOL_REQUIREMENTS.md` for detail; justified by policy + dataset):
- **Read-only graph**: get_case, get_transaction, get_customer, get_card, get_neighbors, find_related_transactions, find_device_connections, find_related_cases, run_fraud_pattern, calculate_exposure, card_history, region_history
- **Retrieval**: retrieve_policy, retrieve_historical_case, retrieve_pattern_typology
- **Evidence simulation**: request_customer_validation, request_step_up_auth, request_analyst_info (simulate responses; record assumed_response)
- **State-changing**: create_case (auto, writes to graph), recommend_action, generate_report, file_report (L2)
- **Policy**: evaluate_policy (R1-R10 decision support)
- **Authorization model**: only `auto` actions executed by agent; L1/L2 recommended with route

---

## 16. Explainability Requirements

See `phase0/EXPLAINABILITY_MODEL.md` (pending). Graph paths that form useful explanations:
- Flagged Transaction → FROM_DEVICE → DeviceProfile → other cards → other customers → ClosedCase
- Card → MADE → Transaction → BILLED_IN → BillingRegion (region novelty)
- Card CHAIN via NEXT edges (card testing sequence)
- No SHAP primary mechanism; graph evidence attribution + provenance per README (§ Explainability in README Technology Stack)

---

## 17. Risks and Ambiguities

| Risk | Detail | Mitigation |
|------|--------|------------|
| Generic device profiles | `|||` profile = 1,011 customers; top profiles 500-1,000+ | Specificity weighting; combine with other evidence; treat generic profiles as low signal |
| Missing identity for 6,640 online txns | HHG-002 flagged txn lacks identity | Handle gracefully: device-based queries return empty; use region/email/history |
| Card1 ↔ card_id mapping | Numeric card1 vs CXXXX-KY | Explicit mapping via customer_id at load time |
| addr1/addr2 nulls (11.1%) | Region queries miss these | Fallback: addr2 country, dist features |
| Undocumented patterns in case pack | HHG-014 likely undocumented ring | R9 path: CREATE_CASE + FILE_REPORT + ESCALATE + pattern_description |
| "Half the cases are legitimate" (README) | Over-blocking scored badly | Lean toward verify (R1) and close (R3) where evidence is thin |
| risk_score not truth | 0.90 cases (HHG-010/019) may be legitimate | fraud_probability from evidence, not risk_score |
| Closed-case retrieval noise | Similar prior cases can be misleading | Require shared entity evidence (device/region/card) |
| Exposure definition | Only transactions *identified as fraud* count | Careful affected_txn_ids selection; legitimate = 0 exposure |

---

## 18. Implementation Recommendations

1. **Load data first, design queries against real row counts** — pattern detection thresholds (e.g., R5 "3 in an hour") should be tuned on actual data distributions
2. **Investigate HHG-014 first** — highest-value spectral case (undocumented ring), validates the graph's device-linking power
3. **Pre-compute per-card aggregation** (amount mean/std, region set, channel mix, product codes) as vertex attributes at load time to accelerate baseline-vs-signal comparisons
4. **Build card_id mapping + device specificity tables before agent implementation**
5. **Prioritize stop-condition discipline** (Section 6) — cases over-both directions are marked down
6. **Test the 20-case pack against closed-case retrieval early** to validate GraphRAG embeddings

---

## 19. Questions to Resolve Before Phase 1

| # | Question | Where it matters |
|---|----------|------------------|
| Q1 | Confirm canonical card ID strategy: CXXXX-KY vs numeric card1 for `connected_card_ids`, INVOLVES edges, and SAR subjects | Schema + card-id mapping |
| Q2 | How to represent agent-created cases in the graph? (ClosedCase-style with graph_case_id `CASE-YYYY-NNNN`?) | Case memory |
| Q3 | Device profile specificity threshold: below what customer_count is a profile "specific enough" to weight as evidence? | Evidence weighting |
| Q4 | For in_person (channel=W) cases without identity: what is the primary spanning evidence (region only)? | HHG-001/003/007/012/018 |
| Q5 | Does the benchmark expect `evidence.ref` to name *concrete GSQL query names* (e.g., `query:card_window(...)`) as in the example? | Answer formatting |
| Q6 | LLM choice confirmed: Gemma 4 26B meets latency/token constraints for 20 cases? | Runtime |
| Q7 | XGBoost optional: dataset has no labels in transaction file; only closed-case labels. Is ML feature engineering in scope for Innovation? | Optional ML |
| Q8 | Regulatory documents: which to embed (all listed, or a curated subset)? | GraphRAG + SAR quality |
| Q9 | Auto-monitoring of exam period for post-Nov alerts: in scope for Innovation bonus? | Innovation scope |
| Q10 | Vector store on TigerGraph Savanna vs Community: embedding dimension for BGE-small-en-v1.5 (384)? | GraphRAG config |

---

## Conclusion

Dataset is well-structured and rich for graph investigation. The five documented patterns, policy (R1-R10), and answer format are machine-actionable. The strongest technical challenges are: (1) generic device profiles diluting shared-origin evidence, (2) card ID mapping across file formats, (3) calibrating fraud_probability against evidence rather than risk_score, and (4) discipline on stopping and exposure definitions. HHG-014 is the standout spectral case (undocumented device ring). Half the cases are legitimate — verify first, block only with evidence and policy backing.

---

## Files Created

```
phase0/FILE_INVENTORY.md
phase0/DATA_DICTIONARY.md
phase0/ENTITY_MODEL.md
phase0/RELATIONSHIP_MODEL.md
phase0/FRAUD_PATTERNS.md
phase0/POLICY_RULES.md
phase0/OUTPUT_SCHEMA.md
phase0/TIGERGRAPH_SCHEMA_PROPOSAL.md
phase0/PHASE0_FINAL_REPORT.md
```

**Pending (recommended next):** `phase0/CASE_PACK_ANALYSIS.md` (per-case evidence drill-down), `phase0/CASE_DIFFICULTY.md` (standalone), `phase0/DATA_QUALITY_REPORT.md` (with counts), `phase0/GRAPH_INVESTIGATION_QUESTIONS.md` (Q1-Q10 paths), `phase0/EXPLAINABILITY_MODEL.md`, `phase0/AGENT_TOOL_REQUIREMENTS.md`.

---

PHASE 0 STATUS: COMPLETE (core deliverables; per-case evidence drill-down optional)

FILES CREATED: 9 (listed above)

KEY FINDINGS:
- 13,553 customers/cards, 590,742 txns, 5,565 closed cases (4,665 fraud / 900 cleared), 20 benchmark cases
- 4,789 device profiles shared across customers — shared-origin is the #1 investigation lever (R6)
- HHG-014 matches an undocumented Samsung SM-G935F + anonymous-proxy fraud ring (4 closed cases, linked 23-card ring)
- 9 undocumented closed cases split into 2 real patterns (SM-G935F proxy ring: 4 cases; sub-$500 bursts: 5 cases)
- 11/20 cases are risk_score triggers; 8 customer reports; 1 analyst request; flagged txns all verified
- in_person (channel W) carries no identity; 6,640 online txns also lack identity records

BLOCKERS: none blocking Phase 0 sign-off. Recommended before Phase 1: answer Q1-Q2 above (card ID strategy, case-memory representation) and confirm Phase 1 scope.

NEXT PHASE: TigerGraph schema implementation, only after Phase 0 is verified.