# Phase 0 — Output Schema (Answer Format)

Source: `DATASET/README.md` "Answer Format" section (lines 289-444). This is the **exact** benchmark specification. Do not simplify.

---

## Submission Format
- One JSON file per case: `<case_id>.json` (e.g., `HHG-017.json`)
- 20 cases, 20 files, in a folder called `cases/` at repo root
- Same structure for every case; missing fields score zero for that part

---

## Top Level

| Field | Type | Meaning |
|-------|------|---------|
| `case_id` | string | From `case_pack.csv` |
| `case` | object | Part 1: internal investigation record |
| `evidence_requests` | list | Each: `type` (`customer_validation` \| `step_up_auth` \| `analyst_info`), `asked_after_step` (int), `assumed_response` (string). Empty if nothing asked |
| `next_best_actions` | object | Part 3 |
| `sar` | object | Part 2 |
| `stop_reason` | string | Why investigation ended |
| `tool_calls` | int | Graph + retrieval calls for this case |
| `tokens` | int | LLM tokens consumed |
| `latency_s` | number | Wall-clock seconds |

---

## Part 1: `case`

| Field | Type | Meaning |
|-------|------|---------|
| `status` | `open` \| `closed_fraud` \| `closed_legitimate` \| `escalated` | Where case stands when agent stops |
| `verdict` | `fraud` \| `legitimate` \| `uncertain` | Conclusion |
| `fraud_probability` | number 0–1 | Calibrated probability (scored) |
| `pattern` | enum: `card_testing` \| `card_not_present_fraud` \| `card_not_present_new_device` \| `out_of_region_use` \| `account_takeover` \| `undocumented` \| `none` | Identified pattern |
| `pattern_description` | string | Required when `pattern` is `undocumented` (2-3 sentences); else `""` |
| `affected_txn_ids` | list of strings | Every transaction in the fraud episode incl. flagged; **empty if legitimate** |
| `first_suspicious_txn_id` | string or `""` | Where it started |
| `connected_card_ids` | list of strings | Other cards in same compromise/ring/device |
| `connected_device_profiles` | list of strings | Device profiles (DeviceInfo + OS + browser + screen) linking to other cards |
| `exposure_usd` | number | Sum of absolute amounts of `affected_txn_ids` |
| `evidence` | list of objects | Each: `claim` (string), `source` (`graph` \| `document` \| `customer` \| `external`), `ref` (query name, document section, or request id), `entity_ids` (list of IDs the claim rests on) |
| `similar_prior_cases` | list of strings | Closed-case IDs retrieved as memory, e.g. `["CC-0141", "CC-2671"]`; empty if none |
| `summary` | string | 2-6 sentences an analyst could read |
| `written_to_graph` | boolean | Whether case stored in TigerGraph |
| `graph_case_id` | string or `""` | ID of case vertex created, if any |

---

## Part 2: `sar`

| Field | Type | Meaning |
|-------|------|---------|
| `file` | boolean | Must agree with whether `FILE_REPORT` appears in final actions |
| `reason` | string | Why file, or why not. Cite policy rule |
| `narrative` | string | Required when `file` is true: who/what/when/where/how/why. 6-12 sentences |
| `subjects` | list of strings | IDs of customers, cards, merchants, devices named in narrative |
| `total_amount_usd` | number | Total suspicious activity |
| `activity_dates` | list of two strings | First and last date `YYYY-MM-DD` |

**If `file` is false**: `narrative`=`""`, `subjects`=`[]`, `total_amount_usd`=0, `activity_dates`=`[]`.

---

## Part 3: `next_best_actions`

| Field | Type | Meaning |
|-------|------|---------|
| `initial` | list of objects | Before requested evidence returns. Each: `action` (from policy), `route` (`auto` \| `L1` \| `L2`), `reason` (cite policy rule) |
| `final` | list of objects | After assumed responses. Same shape. If nothing requested, equals `initial` |
| `what_changed` | string | Why final differs from initial, or `"nothing"` |

---

## Important Benchmark Rules (verified against README lines 436-444)

1. **IDs must be the ones in the dataset.** Made-up IDs score zero.
2. **Legitimate verdict** → `affected_txn_ids` empty, `exposure_usd` 0, `sar.file` false.
3. **`uncertain` is valid** and earns full credit on ambiguous cases, provided actions follow R1 and R8.
4. **`risk_score` is an input, not an answer.** `fraud_probability` may be far from it.
5. **Customer/analyst replies are not provided.** State assumption in `evidence_requests`; let `next_best_actions.final` reflect it.
6. **Keep `summary` short.** Evidence list carries detail. SAR narrative is the one place to be complete.
7. **Exposure** = sum of absolute amounts of identified fraudulent transactions (incl. flagged).
8. **Investigation stops** when policy-defined sufficient evidence exists (Section 6 of policy).
9. **Every recommendation** must explain evidence and cite the applicable rule (Section 7).

---

## Reference Example (HHG-017 in README)

Full JSON example at README lines 366-433. Key structural observations:
- `evidence[].source` uses `graph`/`customer`/`document`
- `evidence[].ref` names the query, e.g. `query:card_window(card_id=C00377-K1, hours=2)`, `query:device_neighbors(device_id=D000731)`, or `evidence_request:1`
- `evidence_requests[].asked_after_step` indicates workflow step index
- Example `graph_case_id` format: `CASE-2016-1187`
- Example `tool_calls`: 9, `tokens`: 12480, `latency_s`: 18.7
- `activity_dates` = `["2016-11-14", "2016-11-14"]` (first/last same day)