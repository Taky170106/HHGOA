import csv, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
R = r"D:\HHG"
def rd(p):
    with open(os.path.join(R, p), encoding="utf-8") as f:
        return list(csv.DictReader(f))
fd = rd("data/edges/from_device.csv")
print("device txn:", fd[0]["from_txn_id"], "device:", fd[0]["to_device_profile_id"])
inv = rd("data/edges/involves.csv")
print("case txn:", inv[0]["to_txn_id"], "case:", inv[0]["from_case_id"])
cc = rd("data/vertices/closed_case.csv")
print("closed_case[0]:", cc[0]["case_id"], "card", cc[0]["card_id"], "cust", cc[0]["customer_id"],
      "first_fraud_txn", cc[0]["first_fraud_txn_id"])
on = rd("data/edges/on_card.csv")
print("on_card[0]:", on[0])
# customer with many txns
cust = rd("data/vertices/customer.csv")
print("customer[0]:", cust[0]["customer_id"], "total_txns", cust[0]["total_txns"])
