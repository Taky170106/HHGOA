import ast, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
p = r"D:\HHG\scripts\build_cases.py"
s = open(p, encoding="utf-8").read()
old = '        f = gather(row)\n        a = analyse(f)'
new = ('        f = gather(row)\n'
       '        tid, cid, cuid = f["flagged_txn_id"], f["card_id"], f["customer_id"]\n'
       '        a = analyse(f)')
assert old in s, "anchor not found"
s = s.replace(old, new, 1)
open(p, "w", encoding="utf-8", newline="").write(s)
ast.parse(s)
print("OK")
