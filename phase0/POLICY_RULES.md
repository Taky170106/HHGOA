# Phase 0 — Policy Rules Analysis

Source: `DATASET/README.md` "Fraud Policy" section (lines 190-287). Version 1.0. Action names and approval routes below use the exact benchmark identifiers.

---

## Policy Actions (exact identifiers)

| Action | What it does | Customer impact |
|--------|--------------|-----------------|
| `ALLOW_TRANSACTION` | Let flagged transaction stand | None |
| `DECLINE_TRANSACTION` | Decline flagged authorization only; card stays active | Low |
| `MONITOR_CARD` | Card active; raise monitoring sensitivity 72h | None |
| `MONITOR_CONNECTED_CARDS` | Monitor other cards linked (device/region/ring) | None |
| `WARN_CUSTOMER` | Informational message | None |
| `VERIFY_WITH_CUSTOMER` | Ask cardholder about transaction; card active pending reply | Low |
| `STEP_UP_AUTH` | Require OTP/app confirmation | Low |
| `BLOCK_CARD` | Block card and reissue | High |
| `BLOCK_ALL_CARDS` | Block every card the customer holds | Very high |
| `GENERATE_REPORT` | Write up investigation internally; no case opened | None |
| `CREATE_CASE` | Open internal fraud case with evidence; write to graph | None |
| `FILE_REPORT` | File SAR with regulator | None |
| `ESCALATE_TO_ANALYST` | Hand to human analyst with evidence | None |
| `CLOSE_NO_FRAUD` | Close alert as legitimate | None |

**Note**: Several actions may be recommended for one case; order them by what happens first.

---

## Approval Routing

| Route | Applies to |
|-------|------------|
| `auto` | ALLOW_TRANSACTION, MONITOR_CARD, MONITOR_CONNECTED_CARDS, WARN_CUSTOMER, VERIFY_WITH_CUSTOMER, STEP_UP_AUTH, GENERATE_REPORT, CREATE_CASE, ESCALATE_TO_ANALYST, CLOSE_NO_FRAUD |
| `L1` (team lead) | DECLINE_TRANSACTION; BLOCK_CARD when exposure ≤ $2,500 |
| `L2` (fraud manager) | BLOCK_CARD when exposure > $2,500; BLOCK_ALL_CARDS always; FILE_REPORT always |

**Agent executes only `auto` actions.** L1/L2 actions are recommended with route stated and wait for a human.

---

## Policy Rules (exact text, README lines 231-243)

| Rule | Condition | Required Evidence | Permitted Actions | Prohibited | Approval | Effect on Next-Best-Action |
|------|-----------|-------------------|-------------------|------------|----------|----------------------------|
| **R1** | Case rests on single signal (incl. risk score alone) AND fraud probability < 0.70 | Single signal | `VERIFY_WITH_CUSTOMER` or `STEP_UP_AUTH` before any block | Blocking on one signal when prob < 0.70 ("policy breach") | auto | Forces verify/step-up before block |
| **R2** | Customer denies transaction | Denial | `BLOCK_CARD`, `CREATE_CASE`; add `FILE_REPORT` if exposure > $1,000 OR shared device/other-card fraud | - | BLOCK_CARD: L1/L2 by exposure; FILE_REPORT: L2; CREATE_CASE: auto | Adds report when threshold met |
| **R3** | Customer confirms transaction | Confirmation | `CLOSE_NO_FRAUD`; note confirmation | - | auto | Close case as legitimate |
| **R4** | No reply within 24h | Timeout | `MONITOR_CARD`, `DECLINE_TRANSACTION` for pending auths; escalate if exposure > $500 | - | DECLINE: L1; escalate: auto | Escalation on high exposure |
| **R5** | Card testing: 3+ small online auths within 1h then larger purchase | Sequence | `DECLINE_TRANSACTION`, `STEP_UP_AUTH`. If purchase > $100 cleared: `BLOCK_CARD` | - | DECLINE: L1; BLOCK: L1/L2 | Block when large purchase cleared |
| **R6** | Several cards fraud from same device/region/recipient email in one window | Shared element | `CREATE_CASE`, `FILE_REPORT`, `MONITOR_CONNECTED_CARDS` for every sharing card | - | FILE_REPORT: L2 | Names shared element; monitors connected cards |
| **R7** | Disputed but matches recurring pattern (same merchant/amount/monthly) | Recurring match | `CREATE_CASE`, `VERIFY_WITH_CUSTOMER`, `WARN_CUSTOMER` | Do NOT block | CREATE_CASE: auto | Verify without blocking |
| **R8** | Verdict `uncertain` AND exposure > $500 OR evidence conflicts | Uncertainty + exposure | `ESCALATE_TO_ANALYST` | - | auto | Escalate |
| **R9** | Activity fits no known pattern but shows coordinated/repeated abuse across customers | Evidence of undocumented pattern | `CREATE_CASE`, `FILE_REPORT`, `ESCALATE_TO_ANALYST`; describe pattern in own words | Don't force into known category | FILE_REPORT: L2 | Files report for undocumented patterns |
| **R10** | Never BLOCK_ALL_CARDS | - | Only if ≥2 customer's cards show confirmed fraud OR credentials confirmed compromised | BLOCK_ALL_CARDS otherwise | L2 | Restricts very-high-impact action |

---

## Case vs Report Distinction (Section 3a)

### Case (`CREATE_CASE`)
- Bank's internal investigation record
- Open one **when**: fraud probability ≥ 0.30, OR evidence requested, OR customer disputes a charge
- Closable as fraud or legitimate; updatable with new evidence
- **Must be written into the graph** — later investigations retrieve it

### SAR (`FILE_REPORT`)
- Regulatory filing sent outside bank
- File one **when**: fraud confirmed/strongly suspected AND at least one of:
  - exposure > $1,000
  - activity connects to shared device profile, shared region cluster, or another customer's fraud
  - pattern is coordinated or undocumented (R9)
- A report always has a case behind it; most cases never need a report
- Narrative must stand on its own: who, what, when, where, how, why

**"Deciding correctly between 'case only' and 'case plus report' is part of the next-best-action score."** (README line 259)

---

## Next-Best-Action Can Change (Section 3b)

- Recommend what evidence supports now → request more evidence if policy calls → recommend again
- Example (verbatim concept): prob 0.45 on single signal → initial `VERIFY_WITH_CUSTOMER` (R1); customer denies → final `BLOCK_CARD`, `CREATE_CASE`, possibly `FILE_REPORT` (R2), connected cards monitored
- Record both initial and final recommendation + what changed

---

## Exposure (Section 4)

- **Exposure** = sum of absolute amounts of every transaction identified as part of the fraud episode, **including the flagged one**
- Reported in USD
- Legitimate → exposure 0

---

## Gathering More Evidence (Section 5)

- Agent may, **without approval**: ask customer to validate, request step-up auth, request information from analyst
- **Responses are not provided** in this round — simulate them in own system, state assumption in `evidence_requests`

---

## Stopping (Section 6)

Stop investigating when ANY:
- Fraud probability ≥ 0.85 OR ≤ 0.15, supported by **at least two independent pieces of evidence**
- A verification response settles the question
- Further steps unlikely to change the decision (say so in `stop_reason`)

---

## Explaining (Section 7)

Every recommendation must state:
- What evidence was used
- Why more evidence was requested (if it was)
- Why chosen actions follow from policy
- **Cite the rule number**

---

## Case Creation Thresholds Summary

| Event | Action |
|-------|--------|
| fraud_probability ≥ 0.30 | CREATE_CASE |
| Evidence requested | CREATE_CASE |
| Customer disputes charge | CREATE_CASE |
| Confirmed fraud + exposure > $1,000 | FILE_REPORT |
| Confirmed fraud + shared device/region/other card | FILE_REPORT |
| Coordinated/undocumented pattern (R9) | FILE_REPORT |
| uncertain + exposure > $500 (R8) | ESCALATE_TO_ANALYST |
| fraud_probability ≥ 0.85 or ≤ 0.15 + 2 evidence items | STOP |