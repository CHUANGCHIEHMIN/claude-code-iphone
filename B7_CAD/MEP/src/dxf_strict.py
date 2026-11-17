"""Strict DXF tag/type validation + degenerate-entity scan.  usage: python3 dxf_strict.py FILE..."""
import sys, math
import ezdxf
from collections import Counter


def tag_type(code):
    if 10 <= code <= 59 or 110 <= code <= 149 or 210 <= code <= 239 or 460 <= code <= 469 or 1010 <= code <= 1059:
        return float
    if 60 <= code <= 99 or 160 <= code <= 179 or 270 <= code <= 289 or 370 <= code <= 389 or 400 <= code <= 409 \
            or 420 <= code <= 429 or 440 <= code <= 459 or 1060 <= code <= 1071 or 170 <= code <= 175 or 280 <= code <= 289 \
            or 290 <= code <= 299:
        return int
    return str


for f in sys.argv[1:]:
    raw = open(f, 'rb').read()
    probs = Counter()
    if b'\r' in raw:
        probs['CR chars'] += 1
    lines = raw.decode('utf-8').split('\n')
    if lines[-1] == '':
        lines.pop()
    if len(lines) % 2:
        probs['odd line count'] += 1
    for i in range(0, len(lines) - 1, 2):
        c = lines[i].strip()
        try:
            code = int(c)
        except ValueError:
            probs[f'non-int group code near line {i}'] += 1; continue
        v = lines[i + 1]
        t = tag_type(code)
        if t is float:
            try:
                x = float(v)
                if not math.isfinite(x):
                    probs[f'non-finite {code}'] += 1
            except ValueError:
                probs[f'bad float code {code}: {v[:20]!r}'] += 1
        elif t is int:
            try:
                int(v.strip())
            except ValueError:
                probs[f'bad int code {code}: {v[:20]!r}'] += 1
        elif code in (1, 3) and len(v.encode('utf-8')) > 2049:
            probs[f'string too long code {code}'] += 1
    doc = ezdxf.readfile(f)
    deg = Counter()
    for layout in [doc.modelspace()] + [doc.blocks.get(b.name) for b in doc.blocks if not b.name.startswith('*')]:
        for e in layout:
            t = e.dxftype()
            if t == 'TEXT' and e.dxf.height <= 0: deg['TEXT h<=0'] += 1
            if t == 'TEXT' and not e.dxf.text: deg['TEXT empty'] += 1
            if t == 'MTEXT' and e.dxf.char_height <= 0: deg['MTEXT h<=0'] += 1
            if t in ('ATTRIB', 'ATTDEF') and e.dxf.height <= 0: deg[t + ' h<=0'] += 1
            if t == 'LWPOLYLINE' and len(e) < 2: deg['LWPOLYLINE <2 pts'] += 1
            if t in ('CIRCLE', 'ARC') and e.dxf.radius <= 1e-9: deg[t + ' r=0'] += 1
            if t == 'LINE' and (e.dxf.start - e.dxf.end).magnitude < 1e-9: deg['LINE zero length'] += 1
            if t == 'HATCH' and len(e.paths) == 0: deg['HATCH no paths'] += 1
            if t == 'INSERT':
                if abs(e.dxf.xscale) < 1e-9 or abs(e.dxf.yscale) < 1e-9: deg['INSERT scale 0'] += 1
                for a in e.attribs:
                    if a.dxf.height <= 0: deg['ATTRIB h<=0'] += 1
            if t == 'TEXT' and e.dxf.get('width', 1) <= 0: deg['TEXT width<=0'] += 1
    print(f.split('/')[-1], 'tag problems:', dict(probs) or 'none', '| degenerate:', dict(deg) or 'none')
