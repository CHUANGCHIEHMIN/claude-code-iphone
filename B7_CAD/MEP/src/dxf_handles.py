"""Raw DXF tag-level checks: dangling handle pointers, duplicate handles, odd group codes.
usage: python3 dxf_handles.py FILE.dxf"""
import sys
from collections import Counter, defaultdict

f = sys.argv[1]
lines = open(f, encoding='utf-8', errors='strict').read().split('\n')
if lines and lines[-1] == '':
    lines.pop()
tags = []
for i in range(0, len(lines) - 1, 2):
    tags.append((lines[i].strip(), lines[i + 1].rstrip('\r')))
handles = Counter()
ptrs = []
section = None
cur = None
for k, (code, val) in enumerate(tags):
    if code == '0':
        cur = val
    if code == '2' and k > 0 and tags[k - 1] == ('0', 'SECTION'):
        section = val
    if code in ('5', '105') and cur not in ('SECTION',):
        handles[val.upper()] += 1
    if code in ('330', '340', '347', '348', '350', '360', '390', '1005') or (code.isdigit() and 320 <= int(code) <= 369):
        if val.strip() not in ('0', ''):
            ptrs.append((section, cur, code, val.strip().upper()))
dups = [h for h, n in handles.items() if n > 1]
dangling = [(s, e, c, v) for s, e, c, v in ptrs if v not in handles and c != '1005']
print(f.split('/')[-1], 'tags', len(tags), 'handles', len(handles), 'dup', len(dups), 'pointers', len(ptrs), 'dangling', len(dangling))
cnt = Counter((s, e, c) for s, e, c, v in dangling)
for k, n in cnt.most_common(15):
    print('   dangling', k, n)
hseed = None
for k, (code, val) in enumerate(tags):
    if code == '9' and val == '$HANDSEED':
        hseed = tags[k + 1][1]; break
mx = max(int(h, 16) for h in handles)
print('   $HANDSEED', hseed, 'max handle', hex(mx), 'OK' if hseed and int(hseed, 16) > mx else 'HANDSEED TOO LOW')
