import csv, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
for r in csv.DictReader(open(r"D:\HHG\DATASET\case_pack.csv", encoding="utf-8")):
    print("%s | %-16s | txn %s card %s cust %s risk=%s" % (
        r["case_id"], r["trigger_type"], r["flagged_txn_id"], r["card_id"],
        r["customer_id"], r["risk_score"] or "-"))
    print("     ", r["trigger_text"])
