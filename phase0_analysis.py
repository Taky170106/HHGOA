import pandas as pd

case_pack = pd.read_csv(r'D:\HHG\DATASET\case_pack.csv')
txns = pd.read_csv(r'D:\HHG\DATASET\transactions.csv', usecols=['TransactionID', 'customer_id', 'card1', 'ts', 'channel', 'TransactionAmt', 'ProductCD', 'addr1', 'addr2', 'risk_score', 'P_emaildomain', 'R_emaildomain'])
ident = pd.read_csv(r'D:\HHG\DATASET\identity.csv', usecols=['TransactionID', 'DeviceType', 'DeviceInfo', 'id_15', 'id_23', 'id_30', 'id_31', 'id_33', 'id_34'])
closed = pd.read_csv(r'D:\HHG\DATASET\closed_cases_history.csv')

print('=== CUSTOMER HISTORIES FOR 20 CASES ===')
for _, case in case_pack.iterrows():
    cust_id = case['customer_id']
    card_id = case['card_id']
    cust_txns = txns[txns['customer_id'] == cust_id]
    
    # card1 in transactions is numeric, card_id in case_pack is like C12382-K1
    # The numeric part after K might not match card1 directly
    # Let's check the flagged transaction's card1
    flagged = txns[txns['TransactionID'] == case['flagged_txn_id']]
    if len(flagged) > 0:
        actual_card1 = flagged.iloc[0]['card1']
        card_txns = txns[txns['card1'] == actual_card1]
    else:
        card_txns = pd.DataFrame()
    
    online = (cust_txns['channel'] == 'online').sum()
    in_person = (cust_txns['channel'] == 'in_person').sum()
    unique_cards = cust_txns['card1'].nunique()
    unique_addr1 = cust_txns['addr1'].nunique()
    date_min = cust_txns['ts'].min()
    date_max = cust_txns['ts'].max()
    avg_amt = cust_txns['TransactionAmt'].mean()
    max_amt = cust_txns['TransactionAmt'].max()
    
    print(f"{case['case_id']}: cust={cust_id} case_card={card_id} actual_card1={actual_card1 if len(flagged) > 0 else 'N/A'}")
    print(f"  txns={len(cust_txns)} online={online} in_person={in_person} cards={unique_cards} addr1s={unique_addr1}")
    print(f"  date_range={date_min} to {date_max} avg_amt={avg_amt:.2f} max_amt={max_amt:.2f}")
    print()

# Device reuse analysis
print('=== DEVICE REUSE ANALYSIS ===')
# Merge transactions with identity to get device info per transaction
txn_ident = pd.merge(
    txns[['TransactionID', 'customer_id', 'card1', 'ts']],
    ident[['TransactionID', 'DeviceInfo', 'id_15', 'id_30', 'id_31', 'id_33']],
    on='TransactionID',
    how='inner'
)

# Create device profile: DeviceInfo + OS + browser + screen
txn_ident['device_profile'] = txn_ident['DeviceInfo'].fillna('') + '|' + txn_ident['id_30'].fillna('') + '|' + txn_ident['id_31'].fillna('') + '|' + txn_ident['id_33'].fillna('')

# Count how many customers/cards per device profile
device_customers = txn_ident.groupby('device_profile')['customer_id'].nunique()
device_cards = txn_ident.groupby('device_profile')['card1'].nunique()
device_txns = txn_ident.groupby('device_profile').size()

multi_customer_devices = device_customers[device_customers > 1]
multi_card_devices = device_cards[device_cards > 1]

print(f"Total device profiles: {len(device_customers)}")
print(f"Device profiles used by >1 customer: {len(multi_customer_devices)}")
print(f"Device profiles used by >1 card: {len(multi_card_devices)}")

print("\nTop shared device profiles (by customer count):")
for dp, cnt in multi_customer_devices.sort_values(ascending=False).head(10).items():
    cards = device_cards[dp]
    txns_cnt = device_txns[dp]
    print(f"  {dp[:80]}: {cnt} customers, {cards} cards, {txns_cnt} txns")

# Check if any case devices are shared
print("\n=== CASE DEVICE PROFILES ===")
for _, case in case_pack.iterrows():
    txn_id = case['flagged_txn_id']
    id_rec = ident[ident['TransactionID'] == txn_id]
    if len(id_rec) > 0:
        id_rec = id_rec.iloc[0]
        dp = str(id_rec['DeviceInfo']) + '|' + str(id_rec['id_30']) + '|' + str(id_rec['id_31']) + '|' + str(id_rec['id_33'])
        cust_count = device_customers.get(dp, 0)
        card_count = device_cards.get(dp, 0)
        print(f"{case['case_id']}: device_profile={dp[:100]} customers={cust_count} cards={card_count}")

# Connection reuse - email domains, addr1
print("\n=== EMAIL DOMAIN REUSE ===")
email_customers = txns.groupby('P_emaildomain')['customer_id'].nunique()
email_cards = txns.groupby('P_emaildomain')['card1'].nunique()
print("Top shared purchaser email domains:")
for em, cnt in email_customers.sort_values(ascending=False).head(15).items():
    if cnt > 1:
        print(f"  {em}: {cnt} customers, {email_cards[em]} cards")

# Billing region reuse
print("\n=== BILLING REGION (addr1) REUSE ===")
addr_customers = txns.groupby('addr1')['customer_id'].nunique()
addr_cards = txns.groupby('addr1')['card1'].nunique()
addr_txns = txns.groupby('addr1').size()
for ad, cnt in addr_customers.sort_values(ascending=False).head(15).items():
    if cnt > 1:
        print(f"  addr1={ad}: {cnt} customers, {addr_cards[ad]} cards, {addr_txns[ad]} txns")

# Closed cases - connected cards analysis
print("\n=== CLOSED CASES CONNECTED CARDS ===")
connected = closed['connected_card_ids'].dropna()
print(f"Cases with connected cards: {len(connected)}")
for _, row in connected.head(20).items():
    print(f"  {row}")

# Check patterns in closed cases
print("\n=== CLOSED CASE PATTERNS BY OUTCOME ===")
for outcome in ['confirmed_fraud', 'cleared']:
    subset = closed[closed['outcome'] == outcome]
    print(f"\n{outcome} ({len(subset)} cases):")
    print(f"  Patterns: {subset['pattern'].value_counts().to_dict()}")
    print(f"  Avg exposure: {subset['exposure_usd'].mean():.2f}")
    print(f"  Max exposure: {subset['exposure_usd'].max():.2f}")
    print(f"  Report filed: {(subset['report_filed'] == 'Yes').sum()}")

# Check undocumented cases
print("\n=== UNDOCUMENTED PATTERN CASES ===")
undoc = closed[closed['pattern'] == 'undocumented']
for _, row in undoc.iterrows():
    print(f"  {row['case_id']}: {row['analyst_notes']}")

print("\n=== DATA QUALITY CHECKS ===")
# Missing values in key columns
for col in ['customer_id', 'card1', 'TransactionID', 'ts', 'channel', 'TransactionAmt', 'ProductCD', 'addr1', 'addr2']:
    nulls = txns[col].isna().sum()
    if nulls > 0:
        print(f"  {col}: {nulls} nulls")

# Duplicate check
print(f"Duplicate TransactionIDs: {txns['TransactionID'].duplicated().sum()}")
print(f"Duplicate customer_id+card1 pairs: {txns[['customer_id', 'card1']].duplicated().sum()}")

# Check customer-card consistency
cust_card = txns.groupby('customer_id')['card1'].nunique()
print(f"Customers with multiple cards: {(cust_card > 1).sum()}")
print(f"Max cards per customer: {cust_card.max()}")

# Check if card1 uniquely maps to customer_id
card_cust = txns.groupby('card1')['customer_id'].nunique()
print(f"Cards with multiple customers: {(card_cust > 1).sum()}")

print("\n=== CASE PACK TRIGGER TYPE DISTRIBUTION ===")
print(case_pack['trigger_type'].value_counts().to_dict())

print("\n=== RISK SCORE DISTRIBUTION FOR RISK_SCORE TRIGGERS ===")
risk_cases = case_pack[case_pack['trigger_type'] == 'risk_score']
print(f"Count: {len(risk_cases)}")
print(f"Risk scores: {risk_cases['risk_score'].tolist()}")