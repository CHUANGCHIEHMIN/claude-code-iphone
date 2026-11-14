"""Run a per-PDF spec: symbol templates -> text lines -> residual; write JSON + verification image."""
import sys, json, math, importlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, sys.path[0])
from mep_engine import Page, Template, chain_residual, simplify, rot

FONT = ImageFont.truetype('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 12)


def region_of(page, ids, pad=0.4):
    b = np.array([page.paths[i]['bbox'] for i in ids])
    return [b[:, 0].min() - pad, b[:, 1].min() - pad, b[:, 2].max() + pad, b[:, 3].max() + pad]


def read_numbers(page, insts, name, examples, key, half):
    """attach a number read from the digits inside each instance (circle/square numbering)."""
    from scipy.spatial import cKDTree
    def inner(c, h, excl=None):
        out = []
        for q in page.paths:
            if q['key'] != key or q['id'] == excl or (excl is None and q['id'] in page.consumed):
                continue
            b = q['bbox']
            if b[0] >= c[0] - h and b[2] <= c[0] + h and b[1] >= c[1] - h and b[3] <= c[1] + h:
                out.append(q)
        return out
    ex = {}
    for pid, num in examples.items():
        p = page.paths[pid]; c = np.array([(p['bbox'][0] + p['bbox'][2]) / 2, (p['bbox'][1] + p['bbox'][3]) / 2])
        ex[num] = np.vstack([q['S'] for q in inner(c, half, excl=pid)]) - c
    for i in insts:
        if i['name'] != name:
            continue
        inn = inner(i['at'], half)
        if not inn:
            i['payload'] = dict(num='?'); continue
        P = np.vstack([q['S'] for q in inn]) - i['at']
        best = min((max(cKDTree(E).query(P)[0].mean(), cKDTree(P).query(E)[0].mean()), num) for num, E in ex.items())
        i['payload'] = dict(num=best[1] if best[0] < 0.5 else '?')
        if best[0] < 0.5:
            for q in inn:
                page.consumed[q['id']] = 'num'
    return insts


def text_lines(page, keys, maxdim=16, maxlen=60, gapx=4.0, gapy=0.7, drop=()):
    """group remaining small strokes into text-line boxes."""
    cand = []
    for p in page.paths:
        if p['id'] in page.consumed or p['key'] not in keys:
            continue
        if max(p['w'], p['h']) > maxdim or p['len'] > maxlen:
            continue
        b = p['bbox']
        if any(b[0] >= r[0] and b[1] >= r[1] and b[2] <= r[2] and b[3] <= r[3] for r in drop):
            continue
        cand.append(p)
    n = len(cand); parent = list(range(n))

    def f(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    B = np.array([c['bbox'] for c in cand]) if cand else np.zeros((0, 4))
    for i in range(n):
        for j in range(i + 1, n):
            if cand[i]['key'] != cand[j]['key']:
                continue
            a, b = B[i], B[j]
            if a[0] - gapx <= b[2] and b[0] - gapx <= a[2] and a[1] - gapy <= b[3] and b[1] - gapy <= a[3]:
                ra, rb = f(i), f(j)
                if ra != rb:
                    parent[ra] = rb
    groups = {}
    for i in range(n):
        groups.setdefault(f(i), []).append(cand[i])
    out = []
    for g in groups.values():
        bb = np.array([p['bbox'] for p in g])
        box = [bb[:, 0].min(), bb[:, 1].min(), bb[:, 2].max(), bb[:, 3].max()]
        out.append(dict(box=[float(v) for v in box], ids=[p['id'] for p in g], key=g[0]['key']))
    out.sort(key=lambda t: (round(t['box'][1] / 20), t['box'][0]))
    return out


def run(pdf, spec, outp, verbose=True):
    page = Page(pdf)
    insts = []
    for t in spec.templates(page):
        tpl = Template(page, **t) if isinstance(t, dict) else t
        res = tpl.match(verbose)
        insts.extend(res)
    for (name, reg, colors, r) in getattr(spec, 'REGION_SYMBOLS', []):     # replace everything inside a box
        cons = [p['id'] for p in page.in_region(reg, colors, margin=0.2) if p['id'] not in page.consumed]
        for i in cons:
            page.consumed[i] = name
        insts.append(dict(name=name, kind='block', payload={}, rot=r, at=np.array([(reg[0] + reg[2]) / 2, (reg[1] + reg[3]) / 2]),
                          cons=cons, score=(1, 1)))
        if verbose:
            print(f'{name:18s} region {len(cons)} paths')
    # post: digits inside circuit circles
    if hasattr(spec, 'post'):
        insts = spec.post(page, insts)
    tl = text_lines(page, spec.TEXT_KEYS, drop=spec.DROP)
    assigned = []
    for (x0, y0, x1, y1, text, trot) in spec.TEXTS:
        hit = [t for t in tl if x0 <= (t['box'][0] + t['box'][2]) / 2 <= x1 and y0 <= (t['box'][1] + t['box'][3]) / 2 <= y1
               and not t.get('assign')]
        if not hit:
            print('WARN text not found', text, (x0, y0, x1, y1)); continue
        for t in hit:
            t['assign'] = text
            for i in t['ids']:
                page.consumed[i] = 'text'
        for p in page.in_region((x0, y0 - 4, x1, y1 + 4), spec.TEXT_KEYS, margin=0.2):   # stray glyph strokes
            pcx, pcy = (p['bbox'][0] + p['bbox'][2]) / 2, (p['bbox'][1] + p['bbox'][3]) / 2
            if p['id'] not in page.consumed and max(p['w'], p['h']) < 24 and x0 <= pcx <= x1 and y0 <= pcy <= y1:
                page.consumed[p['id']] = 'text'
        bb = np.array([t['box'] for t in hit])
        clip = (x1 - x0) > 10 or (y1 - y0) > 10          # small point-regions (L()) are not clipped
        box = [bb[:, 0].min(), bb[:, 1].min(), bb[:, 2].max(), bb[:, 3].max()]
        if clip:
            box = [max(box[0], x0), max(box[1], y0), min(box[2], x1), min(box[3], y1)]
        assigned.append(dict(box=[float(v) for v in box],
                             key=hit[0]['key'], assign=text, rot=trot))
    res = chain_residual(page, spec.RESIDUAL_KEYS, drop_regions=spec.DROP)
    data = dict(
        insts=[dict(name=i['name'], kind=i['kind'], payload=i['payload'], rot=i['rot'], at=[float(v) for v in i['at']],
                    score=i['score']) for i in insts],
        texts=[dict(box=t['box'], key=str(t['key']), text=t['assign'], rot=t['rot']) for t in assigned],
        residual=[dict(key=str(k), pts=simplify(P).tolist(), dashed=bool(d), fill=bool(fl)) for k, P, d, fl in res],
        unassigned=[dict(box=t['box'], key=str(t['key'])) for t in tl if not t.get('assign')])
    json.dump(data, open(outp + '.json', 'w'), ensure_ascii=False)
    if verbose:
        from collections import Counter
        print('instances', Counter(i['name'] for i in insts))
        print('texts assigned', len(assigned), 'unassigned text lines', len(data['unassigned']), 'residual polylines', len(res))
    return page, data, tl


def render(page, data, tl, out, region, Z=3.0):
    x0, y0, x1, y1 = region
    W, H = int((x1 - x0) * Z), int((y1 - y0) * Z)
    im = Image.new('RGB', (W, H), 'white'); g = ImageDraw.Draw(im)
    T = lambda x, y: ((x - x0) * Z, (y - y0) * Z)
    for gx in range(int(x0 // 10 * 10), int(x1), 10):
        g.line([T(gx, y0), T(gx, y1)], fill=(238, 238, 250) if gx % 50 else (200, 200, 245))
        if gx % 50 == 0: g.text(T(gx + 1, y0 + 1), str(gx), fill=(90, 90, 200), font=FONT)
    for gy in range(int(y0 // 10 * 10), int(y1), 10):
        g.line([T(x0, gy), T(x1, gy)], fill=(238, 238, 250) if gy % 50 else (200, 200, 245))
        if gy % 50 == 0: g.text(T(x0 + 1, gy + 1), str(gy), fill=(90, 90, 200), font=FONT)
    for r in data['residual']:
        c = eval(r['key']); col = tuple(int(v * 170) for v in c) if c else (0, 0, 0)
        pts = [T(*p) for p in r['pts']]
        if len(pts) > 1:
            g.line(pts, fill=col, width=1)
    for i in data['insts']:
        x, y = i['at']; px, py = T(x, y)
        g.rectangle([px - 14, py - 14, px + 14, py + 14], outline=(0, 160, 0) if i['kind'] == 'block' else (200, 0, 200), width=2)
        lab = i['name'] if i['kind'] == 'block' else ('T:' + str(i['payload'].get('text', '')))
        if i['payload'].get('num'):
            lab += '=' + str(i['payload']['num'])
        g.text((px + 15, py - 16), f"{lab} r{i['rot']}", fill=(0, 0, 0), font=FONT)
    for t in tl:
        b = t['box']; a, c = T(b[0], b[1]), T(b[2], b[3])
        col = (0, 120, 255) if t.get('assign') else (255, 0, 0)
        g.rectangle([a[0] - 2, a[1] - 2, c[0] + 2, c[1] + 2], outline=col, width=1)
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        g.text((a[0], c[1] + 2), (t['assign'] if t.get('assign') else f'?{cx:.0f},{cy:.0f}'), fill=col, font=FONT)
    im.save(out)


if __name__ == '__main__':
    pdf, specname, outp = sys.argv[1:4]
    spec = importlib.import_module(specname)
    page, data, tl = run(pdf, spec, outp)
    for k, reg in enumerate(spec.VIEWS):
        render(page, data, tl, f'{outp}_v{k}.png', reg, spec.ZOOM)
