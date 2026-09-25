import ast, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
p = r"D:\HHG\scripts\build_cases.py"
s = open(p, encoding="utf-8").read()

pairs = [
    # ts is a datetime string ("2016-07-02 00:02:21"), not epoch seconds
    ('tx["ts_f"] = pd.to_numeric(tx["ts"], errors="coerce")',
     'tx["ts_f"] = pd.to_datetime(tx["ts"], format="%Y-%m-%d %H:%M:%S", errors="coerce",\n'
     '                            utc=True).astype("int64").astype(float) / 1e9'),
    # guard dstr / dtstr against non-finite input
    ('def dstr(ts):\n'
     '    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d")',
     'def dstr(ts):\n'
     '    try:\n'
     '        v = float(ts)\n'
     '    except (TypeError, ValueError):\n'
     '        return ""\n'
     '    if not math.isfinite(v):\n'
     '        return ""\n'
     '    return datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%d")'),
    ('def dtstr(ts):\n'
     '    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")',
     'def dtstr(ts):\n'
     '    try:\n'
     '        v = float(ts)\n'
     '    except (TypeError, ValueError):\n'
     '        return ""\n'
     '    if not math.isfinite(v):\n'
     '        return ""\n'
     '    return datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")'),
    # narrative date fallback when the timestamp is unusable
    ('    date = dstr(f["flagged_ts"])',
     '    date = dstr(f["flagged_ts"]) or str(f["opened_at"])[:10]'),
]
missing = []
for a, b in pairs:
    if a in s:
        s = s.replace(a, b, 1)
    else:
        missing.append(a.splitlines()[0])
open(p, "w", encoding="utf-8", newline="").write(s)
ast.parse(s)
print("patched; missing:", missing)
