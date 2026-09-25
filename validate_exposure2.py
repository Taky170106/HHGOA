import pandas as pd

txns = pd.read_csv(r'D:\HHG\DATASET\transactions.csv', usecols=['TransactionID', 'TransactionAmt'])
closed = pd.read_csv(r'D:\HHG\DATASET\closed_cases_history.csv')

# Recompute for ALL cleared cases and check if non-zero amounts exist in their txn lists
cleared = closed[closed['outcome'] == 'cleared']
print(f"Total cleared cases: {len(cleared)}")
print(f"Cleared with txn_ids: {cleared['txn_ids'].notna().sum()}")
print(f"Cleared with exposure > 0: {(cleared['exposure_usd'] > 0).sum()}")

# For confirmed fraud cases, verify exposure = sum txn amounts
fraud = closed[closed['outcome'] == 'confirmed_fraud']
mismatch_fraud = 0
max_diff = 0
max_case = None
tested = 0
for _, row in fraud.sample(100, random_state=7).iterrows():
    ids = [t.strip() for t in str(row['txn_ids']).split('|') if t.strip()]
    if not ids:
        continue
    amts = txns[txns['TransactionID'].astype(str).isin(ids)]['TransactionAmt'].abs().sum()
    tested += 1
    d = abs(amts - row['exposure_usd'])
    if d > 0.01:
        mismatch_fraud += 1
        if d > max_diff:
            max_diff = d
            max_case = (row['case_id'], row['exposure_usd'], round(amts, 2), row['outcome'])
print(f"\nConfirmed-fraud exposure recompute: {tested} tested, {mismatch_fraud} mismatches")
if max_case:
    print(f"  Max diff: {max_case}")

# Show the deviations pattern
print(f"\nMax claimed exposure in fraud: {fraud['exposure_usd'].max():.2f}")
print(f"Mean claimed exposure in fraud: {fraud['exposure_usd'].mean():.2f}")
print(f"Median: {fraud['exposure_usd'].median():.2f}")