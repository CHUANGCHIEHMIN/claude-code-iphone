"""Template matching over PDF stroke paths, residual linework chaining.
Path ids are identical to mep_view.py (both use mep_paths.paths)."""
import math
import numpy as np
from scipy.spatial import cKDTree
from mep_paths import paths as load_paths

TOL = 0.45


def _sample(P, step=0.25):
    out = [P[0]]
    for a, b in zip(P, P[1:]):
        n = int(np.hypot(*(b - a)) / step) + 1
        out.extend(np.linspace(a, b, n + 1)[1:])
    return np.array(out)


def rot(pts, deg):
    t = math.radians(deg); c, s = math.cos(t), math.sin(t)
    # PDF y is down; rotation 'deg' is counter-clockwise as seen on paper
    return np.column_stack([pts[:, 0] * c + pts[:, 1] * s, -pts[:, 0] * s + pts[:, 1] * c])


class Page:
    def __init__(self, pdf):
        self.paths = load_paths(pdf)
        for i, p in enumerate(self.paths):
            p['id'] = i
            p['S'] = _sample(p['P'])
            p['key'] = p['color'] if p['color'] is not None else p['fill']
        self.consumed = {}
        self.trees = {}
        by = {}
        for p in self.paths:
            by.setdefault(p['key'], []).append(p)
        for k, ps in by.items():
            pts = np.vstack([p['S'] for p in ps])
            own = np.concatenate([[p['id']] * len(p['S']) for p in ps])
            self.trees[k] = (cKDTree(pts), own, pts)

    def in_region(self, region, colors=None, margin=0.3):
        x0, y0, x1, y1 = region
        out = []
        for p in self.paths:
            if colors is not None and p['key'] not in colors:
                continue
            bx0, by0, bx1, by1 = p['bbox']
            if bx0 >= x0 - margin and by0 >= y0 - margin and bx1 <= x1 + margin and by1 <= y1 + margin:
                out.append(p)
        return out


class Template:
    def __init__(self, page, name, region, colors, kind, payload=None, rots=(0, 90, 180, 270), insert=None,
                 tol=TOL, recall=0.9, precision=0.85, exclude_ids=()):
        self.page, self.name, self.kind, self.payload, self.rots = page, name, kind, payload or {}, rots
        self.colors = set(colors); self.tol = tol; self.rmin = recall; self.pmin = precision
        ps = [p for p in page.in_region(region, self.colors) if p['id'] not in exclude_ids]
        assert ps, f'template {name}: no paths in {region}'
        self.src_ids = [p['id'] for p in ps]
        self.anchor = max(ps, key=lambda p: max(p['w'], p['h']) + 1e-3 * len(p['P']))
        a = self.anchor; ac = np.array([(a['bbox'][0] + a['bbox'][2]) / 2, (a['bbox'][1] + a['bbox'][3]) / 2])
        self.ac = ac
        self.pts = np.vstack([p['S'] for p in ps]) - ac
        self.keys = np.concatenate([[str(p['key'])] * len(p['S']) for p in ps])
        allb = np.array([p['bbox'] for p in ps])
        self.ext = np.array([allb[:, 0].min(), allb[:, 1].min(), allb[:, 2].max(), allb[:, 3].max()]) - np.r_[ac, ac]
        # insertion point relative to anchor centre (pdf units); default anchor centre
        self.ins = np.zeros(2) if insert is None else np.array(insert) - ac
        self.region = region

    def candidates(self):
        a = self.anchor
        for p in self.page.paths:
            if p['key'] != a['key'] or p['type'] != a['type']:
                continue
            if abs(len(p['P']) - len(a['P'])) > max(2, 0.25 * len(a['P'])):
                continue
            for r in self.rots:
                w, h = (a['w'], a['h']) if r % 180 == 0 else (a['h'], a['w'])
                if abs(p['w'] - w) <= 0.6 and abs(p['h'] - h) <= 0.6:
                    yield p, r

    def score(self, p, r):
        c = np.array([(p['bbox'][0] + p['bbox'][2]) / 2, (p['bbox'][1] + p['bbox'][3]) / 2])
        T = rot(self.pts, r) + c
        rec_hits = 0
        for k in set(self.keys):
            m = self.keys == k
            key = eval(k) if k != 'None' else None
            if key not in self.page.trees:
                return 0, 0, None, None
            tree = self.page.trees[key][0]
            d, _ = tree.query(T[m], distance_upper_bound=self.tol)
            rec_hits += np.isfinite(d).sum()
        recall = rec_hits / len(T)
        # precision: page paths inside the transformed extent must be explained by the template
        E = rot(np.array([[self.ext[0], self.ext[1]], [self.ext[2], self.ext[3]], [self.ext[0], self.ext[3]], [self.ext[2], self.ext[1]]]), r) + c
        reg = (E[:, 0].min(), E[:, 1].min(), E[:, 0].max(), E[:, 1].max())
        inside = self.page.in_region(reg, self.colors, margin=0.6)
        if not inside:
            return recall, 0, None, None
        tt = cKDTree(T)
        tot = hit = 0; cons = []
        for q in inside:
            d, _ = tt.query(q['S'], distance_upper_bound=self.tol)
            f = np.isfinite(d).mean(); tot += len(q['S']); hit += np.isfinite(d).sum()
            if f > 0.8:
                cons.append(q['id'])
        return recall, hit / max(tot, 1), cons, c

    def match(self, verbose=False):
        out = []
        for p, r in self.candidates():
            if p['id'] in self.page.consumed:
                continue
            rc, pr, cons, c = self.score(p, r)
            if rc >= self.rmin and pr >= self.pmin:
                out.append(dict(p=p['id'], r=r, recall=rc, prec=pr, cons=cons, c=c))
        # one rotation per anchor (best), prefer exact
        best = {}
        for m in out:
            k = m['p']
            if k not in best or (m['recall'] + m['prec']) > (best[k]['recall'] + best[k]['prec']) + 1e-6:
                best[k] = m
        res = []
        for m in best.values():
            if any(i in self.page.consumed for i in m['cons']):
                continue
            for i in m['cons']:
                self.page.consumed[i] = self.name
            ins = rot(self.ins[None, :], m['r'])[0] + m['c']
            res.append(dict(name=self.name, kind=self.kind, payload=self.payload, rot=m['r'], at=ins,
                            cons=m['cons'], score=(round(m['recall'], 3), round(m['prec'], 3))))
        if verbose:
            print(f'{self.name:18s} matches {len(res)}')
        return res


def chain_residual(page, keys, drop_regions=(), gap=1.7, ang=35):
    """chain remaining paths (by colour) into polylines; returns list of (key, pts, dashed)."""
    segs = []
    for p in page.paths:
        if p['id'] in page.consumed or p['key'] not in keys:
            continue
        bx0, by0, bx1, by1 = p['bbox']
        if any(bx0 >= r[0] and by0 >= r[1] and bx1 <= r[2] and by1 <= r[3] for r in drop_regions):
            continue
        if p['fill'] is not None and p['color'] is None:
            segs.append(dict(key=p['key'], P=p['P'], fill=True)); continue
        segs.append(dict(key=p['key'], P=p['P'], fill=False))
    out = []
    by = {}
    for s in segs:
        if s['fill']:
            out.append((s['key'], s['P'], False, True)); continue
        by.setdefault(s['key'], []).append(s['P'])
    for key, polys in by.items():
        used = [False] * len(polys)
        ends = []
        for i, P in enumerate(polys):
            ends.append((P[0], i, 0)); ends.append((P[-1], i, 1))
        tree = cKDTree(np.array([e[0] for e in ends]))

        def direction(P, at_end):
            if at_end:
                v = P[-1] - P[max(0, len(P) - 3)]
            else:
                v = P[0] - P[min(len(P) - 1, 2)]
            n = np.hypot(*v)
            return v / n if n > 1e-6 else v

        for i in range(len(polys)):
            if used[i]:
                continue
            used[i] = True
            chain = [np.array(polys[i])]; dashed = False
            for side in (1, 0):
                while True:
                    cur = chain[-1] if side == 1 else chain[0]
                    endpt = cur[-1] if side == 1 else cur[0]
                    dv = direction(cur, side == 1)
                    best = None
                    for j in tree.query_ball_point(endpt, gap):
                        pt, k, which = ends[j]
                        if used[k]:
                            continue
                        Q = np.array(polys[k])
                        Qo = Q if which == 0 else Q[::-1]          # oriented to start at the joint
                        if side == 0:
                            Qo = Qo                                 # will be reversed when prepending
                        qv = Qo[min(len(Qo) - 1, 2)] - Qo[0]
                        n = np.hypot(*qv)
                        g = np.hypot(*(pt - endpt))
                        if n > 1e-6 and g > 0.05:
                            cosang = float(np.dot(dv, qv / n))
                            if cosang < math.cos(math.radians(ang)):
                                continue
                        elif n > 1e-6:
                            cosang = float(np.dot(dv, qv / n))
                            if cosang < -0.2:
                                continue
                        if best is None or g < best[0]:
                            best = (g, k, Qo)
                    if best is None:
                        break
                    g, k, Qo = best
                    used[k] = True
                    if g > 0.15:
                        dashed = True
                    if side == 1:
                        chain.append(Qo)
                    else:
                        chain.insert(0, Qo[::-1])
            pts = np.vstack(chain)
            # drop duplicate consecutive points
            keep = [0] + [k for k in range(1, len(pts)) if np.hypot(*(pts[k] - pts[k - 1])) > 0.02]
            out.append((key, pts[keep], dashed, False))
    return out


def simplify(pts, tol=0.08):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    ab = b - a; n = np.hypot(*ab)
    if n < 1e-9:
        d = np.hypot(*(pts - a).T)
    else:
        v = pts - a
        d = np.abs(ab[0] * v[:, 1] - ab[1] * v[:, 0]) / n
    i = int(np.argmax(d))
    if d[i] > tol:
        return np.vstack([simplify(pts[:i + 1], tol)[:-1], simplify(pts[i:], tol)])
    return np.vstack([a, b])
