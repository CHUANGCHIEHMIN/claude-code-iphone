"""Path-level primitives from a CAD-printed PDF: circles, rectangles, polylines."""
import numpy as np
import pymupdf as fitz
from collections import Counter

GRAY = (0.5, 0.5, 0.5)


def bez(p0, p1, p2, p3, n=6):
    t = np.linspace(0, 1, n)[:, None]
    P = [np.array([p.x, p.y]) for p in (p0, p1, p2, p3)]
    return ((1 - t) ** 3) * P[0] + 3 * ((1 - t) ** 2) * t * P[1] + 3 * (1 - t) * t * t * P[2] + (t ** 3) * P[3]


def paths(pdf):
    page = fitz.open(pdf)[0]
    out = []
    for d in page.get_drawings():
        col = d.get('color'); fill = d.get('fill')
        col = None if col is None else tuple(round(x, 2) for x in col)
        fill = None if fill is None else tuple(round(x, 2) for x in fill)
        if col == GRAY and fill in (None, GRAY):
            continue
        # break the path into connected sub-polylines
        subs, cur = [], []
        for it in d['items']:
            k = it[0]
            if k == 'l':
                seg = [np.array([it[1].x, it[1].y]), np.array([it[2].x, it[2].y])]
            elif k == 'c':
                seg = list(bez(it[1], it[2], it[3], it[4]))
            elif k == 're':
                r = it[1]; seg = [np.array(v) for v in ((r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0))]
            elif k == 'qu':
                q = it[1]; seg = [np.array([v.x, v.y]) for v in (q.ul, q.ur, q.lr, q.ll, q.ul)]
            else:
                continue
            if cur and np.hypot(*(cur[-1] - seg[0])) < 0.05:
                cur.extend(seg[1:])
            else:
                if cur:
                    subs.append(cur)
                cur = list(seg)
        if cur:
            subs.append(cur)
        for s in subs:
            P = np.array(s)
            out.append(dict(color=col, fill=fill, width=d.get('width') or 0, P=P, closed=bool(d.get('closePath')) or
                            (len(P) > 3 and np.hypot(*(P[0] - P[-1])) < 0.05), seq=d.get('seqno')))
    for p in out:
        P = p['P']; x0, y0 = P.min(0); x1, y1 = P.max(0)
        p['bbox'] = (x0, y0, x1, y1); p['w'] = x1 - x0; p['h'] = y1 - y0
        p['len'] = float(np.hypot(*np.diff(P, axis=0).T).sum()) if len(P) > 1 else 0.0
        p['type'] = 'poly'
        if len(P) >= 12 and p['closed']:
            c = P.mean(0); r = np.hypot(*(P - c).T)
            if r.mean() > 0.5 and r.std() / r.mean() < 0.04:
                p['type'] = 'circle'; p['c'] = c; p['r'] = float(r.mean())
        if p['type'] == 'poly' and len(P) == 2:
            p['type'] = 'line'
    return out


if __name__ == '__main__':
    import sys
    for f in sys.argv[1:]:
        ps = paths(f)
        print('==', f.split('/')[-1], 'paths', len(ps))
        cc = Counter((str(p['color']), round(p['r'] * 2, 1)) for p in ps if p['type'] == 'circle')
        for k, v in sorted(cc.items()):
            print('  circle', k, v)
        fc = Counter((str(p['fill']), round(p['w'], 1), round(p['h'], 1)) for p in ps if p['fill'] is not None and p['w'] > 3)
        for k, v in sorted(fc.items()):
            print('  fill', k, v)
        lc = Counter((str(p['color']), p['type']) for p in ps)
        print('  types', dict(lc))
