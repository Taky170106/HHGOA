import pandas as pd
import json

print("=" * 70)
print("PHASE 0 FINAL VALIDATION — EDGES vs ACTUAL ROWS")
print("=" * 70)

# Load all data
txns = pd.read_csv(r'D:\HHG\DATASET\transactions.csv', usecols=['TransactionID', 'customer_id', 'card1', 'ts', 'channel', 'TransactionAmt', 'ProductCD', 'addr1', 'addr2', 'risk_score', 'P_emaildomain', 'R_emaildomain'])
ident = pd.read_csv(r'D:\HHG\DATASET\identity.csv')
closed = pd.read_csv(r'D:\HHG\DATASET\closed_cases_history.csv')
case_pack = pd.read_csv(r'D:\HHG\DATASET\case_pack.csv')

# ---- EDGE 1: Customer OWNS Card ----
print("\n--- Edge 1: Customer OWNS Card ---")
cust_card = txns.groupby('customer_id')['card1'].nunique()
multi = (cust_card > 1).sum()
print(f"Customer-card pairs in data: {txns[['customer_id','card1']].drop_duplicates().shape[0]}")
print(f"Customers with >1 card1 in data: {multi} (claim: 1:1, 13,553)")

# ---- EDGE 2: Card MADE Transaction ----
print("\n--- Edge 2: Card MADE Transaction ---")
print(f"Card->Txn rows: {len(txns)} (claim: 590,742)")
print(f"Unique cards: {txns['card1'].nunique()} (claim: 13,553)")

# ---- EDGE 3: Transaction BILLED_IN BillingRegion ----
print("\n--- Edge 3: Transaction BILLED_IN BillingRegion ---")
billed = txns['addr1'].notna().sum()
print(f"Txns with addr1: {billed} (claim ~525K)")
print(f"Unique addr1: {txns['addr1'].nunique()} (claim: 332)")

# ---- EDGE 4 & 5: Email edges ----
print("\n--- Edge 4/5: PURCHASER_EMAIL / RECIPIENT_EMAIL ---")
print(f"Txns with P_email: {txns['P_emaildomain'].notna().sum()} (claim ~590K)")
print(f"Txns with R_email: {txns['R_emaildomain'].notna().sum()} (claim ~135K)")
print(f"Unique P domains: {txns['P_emaildomain'].nunique()} (claim 59)")
print(f"Unique R domains: {txns['R_emaildomain'].nunique()} (claim 60)")

# ---- EDGE 6: Transaction FROM_DEVICE DeviceProfile ----
print("\n--- Edge 6: Transaction FROM_DEVICE DeviceProfile ---")
print(f"Identity records: {len(ident)} (claim: 144,432)")
online_txns = txns[txns['channel'] == 'online']['TransactionID']
matched = len(set(online_txns) & set(ident['TransactionID']))
print(f"Online txns with identity: {matched} (claim: 144,432)")
print(f"Online txns missing identity: {len(online_txns) - matched} (claim: 6,640)")

# Verify device profiles composite
ident['dp'] = ident['DeviceInfo'].fillna('') + '|' + ident['id_30'].fillna('') + '|' + ident['id_31'].fillna('') + '|' + ident['id_33'].fillna('')
print(f"Unique device profiles (composite): {ident['dp'].nunique()} (claim ~9,706)")

# ---- EDGE 7: Transaction NEXT Transaction ----
print("\n--- Edge 7: Transaction NEXT Transaction (per-card temporal) ---")
txns_sorted = txns.sort_values(['card1', 'ts'])
prevs = txns_sorted.groupby('card1')['TransactionID'].count() - 1
next_edges = int(prevs.sum())
print(f"Potential NEXT edges: {next_edges} (claim ~577K)")

# ---- EDGE 8: ClosedCase INVOLVES Transaction ----
print("\n--- Edge 8: ClosedCase INVOLVES Transaction ---")
closed['parsed_txn_ids'] = closed['txn_ids'].fillna('').apply(lambda x: [t.strip() for t in x.split('|') if t.strip()])
all_involved = [t for ids in closed['parsed_txn_ids'] for t in ids]
print(f"Total INVOLVES edges (parsed): {len(all_involved)}")
print(f"Closed cases with txn_ids: {closed['txn_ids'].notna().sum()}")

# Verify all closed-case txn_ids exist in transactions
txn_set = set(txns['TransactionID'].astype(str))
missing_txns = [t for t in all_involved if t not in txn_set]
print(f"Closed-case txn_ids NOT in transactions.csv: {len(missing_txns)}")
if missing_txns[:5]:
    print(f"  Sample missing: {missing_txns[:5]}")

# ---- EDGE 9: ClosedCase ON_CARD Card ----
print("\n--- Edge 9: ClosedCase ON_CARD Card ---")
print(f"Closed cases with card_id: {closed['card_id'].notna().sum()} (claim: 5,565)")
print(f"Unique closed-case card_ids: {closed['card_id'].nunique()} (claim ~1,913)")

# ---- EDGE 10: ClosedCase CONNECTED_TO Card ----
print("\n--- Edge 10: ClosedCase CONNECTED_TO Card ---")
conn = closed['connected_card_ids'].dropna()
total_connected = sum(len(x.split('|')) for x in conn)
print(f"Cases with connected_card_ids: {len(conn)} (claim: 4)")
print(f"Total CONNECTED_TO edges: {total_connected} (claim ~88)")

# ---- EDGE 11: BenchmarkCase TRIGGERS Transaction ----
print("\n--- Edge 11: BenchmarkCase TRIGGERS Transaction ---")
pack_txns = set(case_pack['flagged_txn_id'].astype(str))
missing = [t for t in pack_txns if t not in txn_set]
print(f"Case-pack flagged txns in transactions.csv: {len(pack_txns) - len(missing)}/20")
print(f"Missing: {len(missing)}")

print("\n" + "=" * 70)
print("VALIDATION 2 — ALL 20 CASE JOINS DETAILED")
print("=" * 70)
for _, case in case_pack.iterrows():
    cid = str(case['flagged_txn_id'])
    txn = txns[txns['TransactionID'].astype(str) == cid]
    cust_match = len(txn) > 0 and str(txn.iloc[0]['customer_id']) == case['customer_id']
    print(f"{case['case_id']}: txn={cid} found={len(txn)>0} customer_match={cust_match} risk_match={case['risk_score'] is not None and abs(txn.iloc[0]['risk_score'] - case['risk_score']) < 0.001 if len(txn)>0 and pd.notna(case['risk_score']) else 'n/a'}")