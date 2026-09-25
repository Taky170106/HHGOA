import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
src = open(r"D:\HHG\scripts\build_cases.py", encoding="utf-8").read().splitlines()
stack = []
in_str = None
i = 0
line = 1
# crude but effective: track brackets outside strings/comments
prev = ""
for ln, text in enumerate(src, 1):
    j = 0
    while j < len(text):
        c = text[j]
        if in_str:
            if c == "\\":
                j += 2
                continue
            if c == in_str:
                in_str = None
        else:
            if c in "\"'":
                # triple quotes
                if text[j:j+3] in ('"""', "'''"):
                    q = text[j:j+3]
                    j += 3
                    k = text.find(q, j)
                    if k == -1:
                        in_str = q[0]
                        j = len(text)
                        break
                    j = k + 3
                    continue
                in_str = c
            elif c == "#":
                break
            elif c in "([{":
                stack.append((c, ln, j))
            elif c in ")]}":
                if not stack:
                    print("UNMATCHED CLOSE %s at line %d col %d" % (c, ln, j))
                else:
                    o, ol, oc = stack.pop()
                    if "([{".index(o) != ")]}".index(c):
                        print("MISMATCH: open %s (line %d col %d) closed by %s (line %d col %d)"
                              % (o, ol, oc, c, ln, j))
        j += 1
    in_str = None if in_str in ("'", '"') else in_str
print("leftover stack:", stack[-8:])
