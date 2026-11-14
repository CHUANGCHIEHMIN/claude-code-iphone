"""Joint registration: shared scale for all floors of the reference PDF, then exact PDF->PDF mapping
for the other PDFs via identical gray-architecture extents.
usage: python3 mep_register2.py BASE.dxf REG_IN.json REG_OUT.json REF_PDF PDF..."""
import sys, json
import numpy as np
from scipy import ndimage, optimize
sys.path.insert(0, sys.path[0])
from mep_common import load_base, base_segments, pdf_items, item_polyline

base_path, reg_in, reg_out, ref_pdf = sys.argv[1:5]
pdfs = sys.argv[5:]
doc = load_base(base_path)
prev = json.load(open(reg_in))
RES, PAD, TRUNC = 2.0, 400.0, 25.0
dts = {}
for fl in ("1F", "2F", "3F"):
    S = base_segments(doc, fl)
    xmin, ymin = S[:, [0, 2]].min() - PAD, S[:, [1, 3]].min() - PAD
    xmax, ymax = S[:, [0, 2]].max() + PAD, S[:, [1, 3]].max() + PAD
    W, H = int((xmax - xmin) / RES) + 1, int((ymax - ymin) / RES) + 1
    grid = np.ones((H, W), bool)
    for x0, y0, x1, y1 in S:
        n = int(max(abs(x1 - x0), abs(y1 - y0)) / (RES * 0.5)) + 2
        grid[((np.linspace(y0, y1, n) - ymin) / RES).astype(int), ((np.linspace(x0, x1, n) - xmin) / RES).astype(int)] = False
    dts[fl] = dict(dt=ndimage.distance_transform_edt(grid) * RES, x0=xmin, y0=ymin, W=W, H=H)


def floors_of(pdf):
    its = [it for it in pdf_items(pdf) if it['color'] == (0.5, 0.5, 0.5)]
    pts = []
    for it in its:
        pl = np.array(item_polyline(it))
        for a, b in zip(pl, pl[1:]):
            pts.append(np.linspace(a, b, int(np.hypot(*(b - a)) / 0.6) + 2))
    P = np.vstack(pts)
    ys = np.sort(P[:, 1]); gaps = np.where(np.diff(ys) > 25)[0]
    cuts = [ys[0] - 1] + [(ys[g] + ys[g + 1]) / 2 for g in gaps] + [ys[-1] + 1]
    groups = [P[(P[:, 1] > cuts[i]) & (P[:, 1] <= cuts[i + 1])] for i in range(len(cuts) - 1)]
    groups = [g for g in groups if len(g) > 500]
    out = {}
    for fl, G in zip(("3F", "2F", "1F"), groups):
        out[fl] = dict(P=G, x0=G[:, 0].min(), x1=G[:, 0].max(), y0=G[:, 1].min(), y1=G[:, 1].max())
    return out


def cost(T, P, D):
    s, tx, ty = T
    X = s * P[:, 0] + tx; Y = -s * P[:, 1] + ty
    ix = ((X - D['x0']) / RES).astype(int); iy = ((Y - D['y0']) / RES).astype(int)
    ok = (ix >= 0) & (ix < D['W']) & (iy >= 0) & (iy < D['H'])
    d = np.full(len(P), TRUNC); d[ok] = np.minimum(D['dt'][iy[ok], ix[ok]], TRUNC)
    return d.mean()


refname = ref_pdf.split('/')[-1]
RF = floors_of(ref_pdf)
best = None
for s in np.arange(2.290, 2.345, 0.002):
    tot, Ts = 0.0, {}
    for fl in ("1F", "2F", "3F"):
        G = RF[fl]['P'][::max(1, len(RF[fl]['P']) // 6000)]
        t0 = prev[refname][fl]['T']
        r = optimize.minimize(lambda v: cost((s, v[0], v[1]), G, dts[fl]), [t0[1], t0[2]], method='Nelder-Mead',
                              options=dict(xatol=0.05, fatol=1e-4, initial_simplex=[[t0[1], t0[2]], [t0[1] + 5, t0[2]], [t0[1], t0[2] + 5]]))
        tot += r.fun; Ts[fl] = (s, float(r.x[0]), float(r.x[1]))
    if best is None or tot < best[0]:
        best = (tot, Ts)
print('ref shared scale', round(best[1]['1F'][0], 4), 'total cost', round(best[0], 3))
result = {refname: {fl: dict(T=list(best[1][fl]), ybounds=[float(RF[fl]['y0']), float(RF[fl]['y1'])]) for fl in RF}}
for pdf in pdfs:
    name = pdf.split('/')[-1]
    if name == refname:
        continue
    OF = floors_of(pdf); result[name] = {}
    for fl in ("1F", "2F", "3F"):
        r, o = RF[fl], OF[fl]
        k = (r['x1'] - r['x0']) / (o['x1'] - o['x0'])
        s, tx, ty = best[1][fl]
        T = (s * k, s * (r['x0'] - k * o['x0']) + tx, ty - s * (r['y1'] - k * o['y1']))
        G = o['P'][::max(1, len(o['P']) // 6000)]
        result[name][fl] = dict(T=[float(v) for v in T], ybounds=[float(o['y0']), float(o['y1'])])
        print(name, fl, 'k', round(k, 4), 'T', [round(v, 3) for v in T], 'cost', round(cost(T, G, dts[fl]), 2))
json.dump(result, open(reg_out, 'w'), indent=1)
