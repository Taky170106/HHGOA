import pandas as pd

txns = pd.read_csv(r'D:\HHG\DATASET\transactions.csv', usecols=['TransactionID', 'TransactionAmt'])
closed = pd.read_csv(r'D:\HHG\DATASET\closed_cases_history.csv')

# Verify exposure recomputation on a sample of real closed cases
mismatches = 0
tested = 0
total_diff = 0
for _, row in closed.sample(50, random_state=42).iterrows():
    ids = [t.strip() for t in str(row['txn_ids']).split('|') if t.strip()]
    if not ids:
        continue
    amts = txns[txns['TransactionID'].astype(str).isin(ids)]['TransactionAmt']
    recomputed = amts.abs().sum()
    tested += 1
    diff = abs(recomputed - row['exposure_usd'])
    total_diff += diff
    if diff > 0.01:
        mismatches += 1

print(f"Exposure recomputation over {tested} random closed cases:")
print(f"  Mismatches (>$0.01): {mismatches}")
print(f"  Total abs diff: ${total_diff:.2f}")

# Show the max diff case
max_diff_case = None
max_diff = 0
for _, row in closed.sample(50, random_state=42).iterrows():
    ids = [t.strip() for t in str(row['txn_ids']).split('|') if t.strip()]
    if not ids:
        continue
    amts = txns[txns['TransactionID'].astype(str).isin(ids)]['TransactionAmt'].abs().sum()
    d = abs(amts - row['exposure_usd'])
    if d > max_diff:
        max_diff = d
        max_diff_case = (row['case_id'], row['exposure_usd'], amts)
if max_diff_case:
    print(f"  Max diff: {max_diff_case[0]} claimed={max_diff_case[1]} recomputed={max_diff_case[2]:.2f} diff={max_diff:.2f}")
else:
    print("  No differences found")