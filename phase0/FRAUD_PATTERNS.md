# Phase 0 — Fraud Pattern Analysis

Source: `DATASET/README.md` "The five known fraud patterns" section (authoritative). Patterns verified against closed_cases_history.csv pattern distribution.

---

## Documented Patterns (from README.md)

### Pattern 1: Card Testing (`card_testing`)
- **Policy reference**: R5
- **Required signals**: 3+ tiny online authorizations (often under $5), then a larger purchase
- **Time window**: Within one hour (per R5: "within an hour")
- **Relevant dataset fields**: `card1`, `ts`, `channel=online`, `TransactionAmt`, `ProductCD`
- **Graph representation**: Card → MADE → Transaction (small, online) → NEXT → Transaction (small, online) → NEXT → Transaction (small, online) → NEXT → Transaction (larger)
- **GSQL detection**: `card_window(card_id, hours=1)` — count online txns with amount < $5 in 1 hour window, check next txn amount
- **Supporting evidence**: Tiny amounts + online channel + short time window + card's product-code history
- **Contradictory evidence**: Cardholder's own pattern of small purchases (legitimate microtransactions)
- **Ambiguity**: Some legitimate uses make small trial purchases (e.g., gift card loads)
- **Closed case stats**: 16 confirmed `card_testing` cases in history
- **Benchmark example**: HHG-017 (example in README answer format resembles card testing)

### Pattern 2: Card-Not-Present Fraud (`card_not_present_fraud`)
- **Policy reference**: R1-R4
- **Required signals**: Number used online without the card; amounts/products inconsistent with cardholder history; burst of 2-4 within 48 hours
- **Relevant dataset fields**: `channel=online`, `TransactionAmt`, `ProductCD`, `P_emaildomain`, customer transaction history
- **Graph representation**: Customer history vs. flagged online transaction; compare amount percentile and product codes
- **GSQL detection**: For flagged txn, compute cardholder's amount mean/std; flag if amount is outlier; check burst of 2-4 online txns in 48h
- **Supporting evidence**: Amount outlier, product-code never used by card, rapid burst
- **Contradictory evidence**: One unusual online purchase on its own is ambiguous — must verify (R1)
- **Ambiguity**: New merchants, holiday shopping, first-time online purchases
- **Closed case stats**: 1,404 confirmed cases (most common pattern)

### Pattern 3: Card-Not-Present fraud from a New Device (`card_not_present_new_device`)
- **Policy reference**: R1-R4
- **Required signals**: Same as Pattern 2 PLUS identity record marks device `New` (id_15), sometimes behind proxy (id_23)
- **Relevant dataset fields**: `identity.csv.id_15` (New/Found/Unknown), `id_23` (proxy), `DeviceInfo`, `channel=online`
- **Graph representation**: Transaction → FROM_DEVICE → DeviceProfile (newness=New, proxy!=null)
- **GSQL detection**: First check pattern 2 signals; then look up `id_15=New` on the identity record; check `id_23` for proxy
- **Supporting evidence**: New device + CNP signals. "Stronger than pattern 2, still not proof: people buy new phones."
- **Contradictory evidence**: Legitimate new device purchases (upgrade, new phone)
- **Ambiguity**: New device alone is not conclusive
- **Closed case stats**: 1,076 confirmed cases

### Pattern 4: Out-of-Region Use (`out_of_region_use`)
- **Policy reference**: R2, R3
- **Required signals**: Card-present purchases in billing region (`addr1`) with no cardholder history in that region; normal activity continues at home region
- **Relevant dataset fields**: `addr1`, `addr2`, `channel=in_person` (ProductCD=W), customer's region history
- **Graph representation**: Card → MADE → Transaction → BILLED_IN → BillingRegion; compare against customer's known regions
- **GSQL detection**: Get customer's addr1 history; flag transaction whose addr1 is new to this customer while cardholder continues using home region
- **Supporting evidence**: Multiple purchases in one new region + continued home activity; "Several days of purchases in one new region is a trip, not a clone" (README)
- **Contradictory evidence**: Legitimate travel (trip)
- **Ambiguity**: Requirement to distinguish trips from clones — needs temporal/spatial context
- **Closed case stats**: 955 confirmed cases

### Pattern 5: Account Takeover (`account_takeover`)
- **Policy reference**: R1 (baseline), R10 (blocking constraints)
- **Required signals**: Mixed-channel activity inconsistent with cardholder; device and match-flag anomalies; points to stolen credentials rather than stolen number
- **Relevant dataset fields**: `channel` switches (in_person↔online), `id_34` (match_status), `id_15` (device newness), `M` match flags, `C` count features
- **Graph representation**: Card → MADE → Transaction (channel A) → NEXT → Transaction (channel B) with DeviceProfile anomalies
- **GSQL detection**: Detect channel switches on a card; check device match flags on the online txns; compare with cardholder baseline
- **Supporting evidence**: Channel switches, new device + match_status anomalies, unusual login patterns
- **Contradictory evidence**: Customer legitimately changes devices, travels (in_person elsewhere + online at home is normal)
- **Ambiguity**: Credentials compromise vs. card number compromise distinction
- **Closed case stats**: 1,205 confirmed cases

---

## Undocumented Patterns (found in closed_cases_history.csv)

Two undocumented patterns observed in `analyst_notes` of 9 confirmed-fraud cases:

### Undocumented A: Proxy-Device Compromise Ring (4 cases)
- **Cases**: CC-2649, CC-2971, CC-2985, CC-3035 (these 4 also carry the shared 23-card connected ring)
- **Signal**: Samsung SM-G935F + Chrome for Android + anonymous proxy (`id_23=IP_PROXY:ANONYMOUS`); device never seen on account; 2+ other cardholders reported same device profile that month
- **Notes evidence** (CC-2649): "cardholder C03528 reported 3 online purchase(s)... Samsung SM-G935F on Chrome for Android behind an anonymous proxy, a device never seen on this account. Two other cardholders reported the same device profile this month."
- **Relevance**: HHG-014 flagged device is `SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080 | IP_PROXY:ANONYMOUS` — matches this ring signature

### Undocumented B: Sub-$500 Burst (5 cases)
- **Cases**: CC-3748, CC-3841, CC-3907, CC-4086, CC-4124
- **Signal**: Four online purchases within 40 minutes, each just under $500 (auth-threshold evasion)
- **Notes evidence** (CC-3748): "reported four online purchases within forty minutes, each just under $500, none of which they made. Amounts appear chosen to stay under a $500 authorization threshold."
- **Relevance**: Pattern R9 (undocumented) applies when evidence shows coordinated/repeated abuse

---

## Pattern Distribution in Closed Cases (verified counts)

| Pattern | Confirmed Fraud | Cleared | Total |
|---------|----------------|---------|-------|
| card_not_present_fraud | 1,404 | 0 | 1,404 |
| account_takeover | 1,205 | 0 | 1,205 |
| card_not_present_new_device | 1,076 | 0 | 1,076 |
| out_of_region_use | 955 | 0 | 955 |
| card_testing | 16 | 0 | 16 |
| undocumented | 9 | 0 | 9 |
| none (cleared) | 0 | 900 | 900 |
| **Total** | **4,665** | **900** | **5,565** |

---

## Pattern Attribution Notes
- **Source**: Readme lines 109-121 (five documented patterns); closed_cases_history.csv `pattern` column and `analyst_notes` (undocumented patterns)
- Cleared cases have `pattern = none` and narrative explaining why the alert was false alarm
- README line 111: "They are **not the only patterns in the data.** Noticing activity that fits none of them, describing it in your own words, and recommending a defensible action is scored."
- README line 156: "Some activity in this data fits none of the five."