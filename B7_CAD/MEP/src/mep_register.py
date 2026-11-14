"""Register each PDF floor plan (gray architecture) to the DWG base floor plan.
usage: python3 mep_register.py BASE.dxf OUT.json PDF..."""
import sys, json
import numpy as np
from scipy import ndimage, optimize
sys.path.insert(0, sys.path[0])
from mep_common import load_base, base_segments, pdf_items, item_polyline

base_path, out_path, pdfs = sys.argv[1], sys.argv[2], sys.argv[3:]
doc = load_base(base_path)
RES = 2.0       # cm per DT pixel
PAD = 400.0
TRUNC = 25.0

dts = {}
for fl in ("1F", "2F", "3F"):
    S = base_segments(doc, fl)
    xmin, ymin = S[:, [0, 2]].min() - PAD, S[:, [1, 3]].min() - PAD
    xmax, ymax = S[:, [0, 2]].max() + PAD, S[:, [1, 3]].max() + PAD
    W, H = int((xmax - xmin) / RES) + 1, int((ymax - ymin) / RES) + 1
    grid = np.ones((H, W), bool)
    for x0, y0, x1, y1 in S:
        n = int(max(abs(x1 - x0), abs(y1 - y0)) / (RES * 0.5)) + 2
        xs = np.linspace(x0, x1, n); ys = np.linspace(y0, y1, n)
        grid[((ys - ymin) / RES).astype(int), ((xs - xmin) / RES).astype(int)] = False
    dt = ndimage.distance_transform_edt(grid) * RES
    core = S[(np.abs(S[:, 0]) < 1200) & (np.abs(S[:, 1]) < 800)]
    dts[fl] = dict(dt=dt, x0=xmin, y0=ymin, W=W, H=H,
                   bbox=(core[:, [0, 2]].min(), core[:, [1, 3]].min(), core[:, [0, 2]].max(), core[:, [1, 3]].max()))
    print(fl, 'base segs', len(S), 'bbox', [round(v) for v in dts[fl]['bbox']])


def cost(T, P, D):
    s, tx, ty = T
    X = s * P[:, 0] + tx; Y = -s * P[:, 1] + ty
    ix = ((X - D['x0']) / RES).astype(int); iy = ((Y - D['y0']) / RES).astype(int)
    ok = (ix >= 0) & (ix < D['W']) & (iy >= 0) & (iy < D['H'])
    d = np.full(len(P), TRUNC)
    d[ok] = np.minimum(D['dt'][iy[ok], ix[ok]], TRUNC)
    return d.mean()


result = {}
for pdf in pdfs:
    its = [it for it in pdf_items(pdf) if it['color'] == (0.5, 0.5, 0.5)]
    pts = []
    for it in its:
        pl = np.array(item_polyline(it))
        for a, b in zip(pl, pl[1:]):
            n = int(np.hypot(*(b - a)) / 0.6) + 2
            pts.append(np.linspace(a, b, n))
    P = np.vstack(pts)
    # split floors by vertical gaps
    ys = np.sort(P[:, 1]); gaps = np.where(np.diff(ys) > 25)[0]
    cuts = [ys[0] - 1] + [(ys[g] + ys[g + 1]) / 2 for g in gaps] + [ys[-1] + 1]
    groups = [P[(P[:, 1] > cuts[i]) & (P[:, 1] <= cuts[i + 1])] for i in range(len(cuts) - 1)]
    groups = [g for g in groups if len(g) > 500]
    assert len(groups) == 3, (pdf, [len(g) for g in groups])
    name = pdf.split('/')[-1]
    result[name] = {}
    for fl, G in zip(("3F", "2F", "1F"), groups):            # top of page = 3F
        D = dts[fl]
        G = G[::max(1, len(G) // 6000)]
        bx0, by0, bx1, by1 = D['bbox']
        best = None
        for s in np.arange(2.20, 2.44, 0.01):
            # align right/top extents first (car on the left of 1F skews the bbox)
            tx0 = bx1 - s * G[:, 0].max(); ty0 = by1 + s * G[:, 1].min()
            for dx in np.arange(-150, 151, 8):
                for dy in np.arange(-150, 151, 8):
                    c = cost((s, tx0 + dx, ty0 + dy), G, D)
                    if best is None or c < best[0]:
                        best = (c, (s, tx0 + dx, ty0 + dy))
        r = optimize.minimize(lambda T: cost(T, G, D), best[1], method='Nelder-Mead',
                              options=dict(xatol=0.05, fatol=1e-4, initial_simplex=[best[1],
                                           (best[1][0] + 0.01, best[1][1], best[1][2]),
                                           (best[1][0], best[1][1] + 6, best[1][2]),
                                           (best[1][0], best[1][1], best[1][2] + 6)]))
        T = [float(v) for v in r.x]
        # fraction of points within 4 cm
        s, tx, ty = T
        X = s * G[:, 0] + tx; Y = -s * G[:, 1] + ty
        ix = ((X - D['x0']) / RES).astype(int); iy = ((Y - D['y0']) / RES).astype(int)
        ok = (ix >= 0) & (ix < D['W']) & (iy >= 0) & (iy < D['H'])
        near = (D['dt'][iy[ok], ix[ok]] < 4).mean()
        result[name][fl] = dict(T=T, cost=float(r.fun), near4cm=float(near),
                                ybounds=[float(G[:, 1].min()), float(G[:, 1].max())])
        print(name, fl, 'T', [round(v, 3) for v in T], 'cost', round(r.fun, 2), 'within4cm', round(near, 3))
json.dump(result, open(out_path, 'w'), indent=1)
