"""Write one MEP sheet DXF: base plan + blocks + texts + routes + legend frame."""
import sys, json, math, importlib
import numpy as np
import ezdxf
from ezdxf.enums import TextEntityAlignment
sys.path.insert(0, sys.path[0])
from mep_common import load_base, FLOOR_ORIGIN
import mep_blocks

FLOORS = ("1F", "2F", "3F")
TEXT_SCALE = 0.85


def fit_width(text, h, avail, wmax=0.85, wmin=0.45):
    """width factor so the TrueType text roughly fits the original (SHX) extent."""
    est = sum(1.0 if ord(ch) > 0x2E80 else 0.58 for ch in text) * h
    return round(max(wmin, min(wmax, avail / est if est > 0 else wmax)), 3)


BANDS = None


def floor_of(reg, y):
    if BANDS:
        for fl, y0, y1 in BANDS:
            if y0 <= y < y1:
                return fl
    best = None
    for fl in FLOORS:
        y0, y1 = reg[fl]['ybounds']
        d = 0 if y0 - 5 <= y <= y1 + 5 else min(abs(y - y0), abs(y - y1))
        if best is None or d < best[0]:
            best = (d, fl)
    return best[1]


def to_base(reg, fl, x, y):
    s, tx, ty = reg[fl]['T']; ox, oy = FLOOR_ORIGIN[fl]
    return (s * x + tx + ox, -s * y + ty + oy)


def write(cfg, base_path, reg_path, data_path, out_path, legend_rows_extra=()):
    global BANDS
    BANDS = getattr(cfg, 'BANDS', None)
    doc = load_base(base_path)
    reg = json.load(open(reg_path))[cfg.PDF]
    data = json.load(open(data_path))
    if 'CHT' not in doc.styles:
        st = doc.styles.add('CHT', font='msjh.ttc'); st.set_extended_font_data(family='Microsoft JhengHei')
    for lt in ('DASHED', 'HIDDEN', 'CENTER', 'DASHDOT', 'PHANTOM'):
        if lt not in doc.linetypes:
            from ezdxf.tools.standards import linetypes
            for name, desc, pattern in linetypes():
                if name == lt:
                    doc.linetypes.add(name, pattern=pattern, description=desc)
    doc.header['$LTSCALE'] = 20
    mep_blocks.build(doc)
    for lname, (aci, lt) in cfg.LAYERS.items():
        if lname not in doc.layers:
            doc.layers.add(lname, color=aci, linetype=lt)
    msp = doc.modelspace()
    s_of = {fl: reg[fl]['T'][0] for fl in FLOORS}
    used = {}
    # ---- symbols
    for ins in data['insts']:
        if ins['kind'] != 'block':
            continue
        x, y = ins['at']; fl = floor_of(reg, y)
        bname = cfg.BLOCK_NAME.get(ins['name'], ins['name'])
        layer = getattr(cfg, 'INST_LAYER', {}).get(ins['name']) or cfg.BLOCK_LAYER.get(bname, cfg.BLOCK_LAYER.get('*'))
        rotation = (ins['rot'] + cfg.BLOCK_ROT.get(ins['name'], 0)) % 360
        e = msp.add_blockref(bname, to_base(reg, fl, x, y), dxfattribs={'layer': layer, 'rotation': rotation})
        attrs = {}
        if bname in ('E_CKT', 'T_NO'):
            attrs['NO'] = str(ins['payload'].get('num', ''))
        if bname == 'L_SW':
            attrs['TYPE'] = ins['payload'].get('type', 'S')
        if attrs:
            e.add_auto_attribs(attrs)
            for a in e.attribs:           # keep attribute text upright
                a.dxf.rotation = 0 if bname != 'L_SW' else ins['payload'].get('trot', 0)
        used[bname] = used.get(bname, 0) + 1
    # ---- texts
    for t in data['texts']:
        b = t['box']; cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2; fl = floor_of(reg, cy)
        s = s_of[fl]; r = t.get('rot', 0) or 0
        h = ((b[3] - b[1]) if r % 180 == 0 else (b[2] - b[0])) * s * 0.92
        key = eval(t['key'])
        layer = cfg.TEXT_LAYER.get(key, cfg.TEXT_LAYER.get('*'))
        if t['text'].startswith('@'):                 # symbol given as text label, e.g. '@L_SW:S3'
            bname, _, val = t['text'][1:].partition(':')
            e = msp.add_blockref(bname, to_base(reg, fl, cx, cy), dxfattribs={'layer': cfg.BLOCK_LAYER.get(bname, layer)})
            e.add_auto_attribs({'TYPE': val} if bname == 'L_SW' else {'NO': val})
            for a in e.attribs:
                a.dxf.rotation = r
            used[bname] = used.get(bname, 0) + 1
            continue
        h *= TEXT_SCALE
        if '\n' in t['text']:                       # stacked lines inside one box
            lines = t['text'].split('\n'); n = len(lines); lh = (b[3] - b[1]) / n
            for k, line in enumerate(lines):
                yk = b[1] + lh * (k + 0.5)
                hh = round(lh * s * 0.92 * TEXT_SCALE, 1)
                e = msp.add_text(line, height=hh, dxfattribs={'layer': layer, 'style': 'CHT', 'width': fit_width(line, hh, (b[2] - b[0]) * s)})
                e.set_placement(to_base(reg, fl, b[0], yk), align=TextEntityAlignment.MIDDLE_LEFT)
            continue
        avail = ((b[2] - b[0]) if r % 180 == 0 else (b[3] - b[1])) * s
        wf = fit_width(t['text'], h, avail) if len(t['text']) > 1 else 0.85
        e = msp.add_text(t['text'], height=round(h, 1), rotation=r, dxfattribs={'layer': layer, 'style': 'CHT', 'width': wf})
        if r % 360 == 0 and len(t['text']) > 1:
            e.set_placement(to_base(reg, fl, b[0], cy), align=TextEntityAlignment.MIDDLE_LEFT)
        else:
            e.set_placement(to_base(reg, fl, cx, cy), align=TextEntityAlignment.MIDDLE_CENTER)
    # ---- residual routes / leaders (floor by vertices inside a plan; else inherit from a touching assigned line)
    items = []
    for rsd in data['residual']:
        key = eval(rsd['key']); pts = rsd['pts']
        layer = cfg.ROUTE_LAYER.get(key)
        if layer is None or len(pts) < 2:
            continue
        inside = {f: sum(1 for p in pts if reg[f]['ybounds'][0] + 8 <= p[1] <= reg[f]['ybounds'][1] - 8) for f in FLOORS}
        fbest = max(inside, key=inside.get)
        items.append([rsd, key, layer, fbest if inside[fbest] > 0 else None])
    from scipy.spatial import cKDTree
    known = [(np.array(it[0]['pts']), it[3]) for it in items if it[3]]
    if known:
        allp = np.vstack([k[0] for k in known]); owner = np.concatenate([[k[1]] * len(k[0]) for k in known])
        tree = cKDTree(allp)
        for it in items:
            if it[3] is None:
                d, j = tree.query(np.array(it[0]['pts']))
                k = int(np.argmin(d))
                it[3] = owner[j[k]] if d[k] < 3.0 else floor_of(reg, float(np.mean([p[1] for p in it[0]['pts']])))
    for rsd, key, layer, fl in items:
        P = [to_base(reg, fl, x, y) for x, y in rsd['pts']]
        if rsd['fill'] and len(P) >= 3:
            h = msp.add_hatch(dxfattribs={'layer': layer}); h.set_solid_fill(color=256)
            h.paths.add_polyline_path(P, is_closed=True)
            continue
        att = {'layer': layer}
        if rsd['dashed'] and key in cfg.DASHED_KEYS:
            att['linetype'] = cfg.DASHED_KEYS[key]
        msp.add_lwpolyline(P, dxfattribs=att)
    # ---- titles
    for e in msp.query('TEXT'):
        txt = e.dxf.text
        if txt.endswith('平面圖(原設計)'):
            e.dxf.text = txt.replace('平面圖(原設計)', cfg.TITLE)
    # ---- legend frame (to the right of 3F)
    X0, Y0, X1, Y1 = 7819, 324, 9919, 1789
    lay = 'A-圖例'
    if lay not in doc.layers:
        doc.layers.add(lay, color=7)
    msp.add_lwpolyline([(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)], close=True, dxfattribs={'layer': 'Defpoints'})
    t = msp.add_text(f'圖例表 — {cfg.TITLE}', height=45, dxfattribs={'layer': lay, 'style': 'CHT'})
    t.set_placement((X0 + 120, Y1 - 110), align=TextEntityAlignment.MIDDLE_LEFT)
    LN = getattr(cfg, 'LEGEND_NAME', {})
    rows = [(b, *LN.get(b, mep_blocks.LEGEND[b][:2]), used[b]) for b in cfg.LEGEND_ORDER if b in used]
    rows += [('__line__', *r) for r in cfg.LINE_LEGEND]
    rows += list(legend_rows_extra)
    draw_table(msp, lay, rows, X0 + 120, Y1 - 200, cfg)
    doc.saveas(out_path)
    return used


def draw_table(msp, lay, rows, x, ytop, cfg, rh=70, widths=(260, 560, 900, 140)):
    heads = ['圖例', '名稱', '說明', '數量']
    W = sum(widths)
    y = ytop
    def hline(yy):
        msp.add_line((x, yy), (x + W, yy), dxfattribs={'layer': lay})
    hline(y)
    xx = x
    for w, hname in zip(widths, heads):
        t = msp.add_text(hname, height=26, dxfattribs={'layer': lay, 'style': 'CHT'})
        t.set_placement((xx + w / 2, y - rh / 2), align=TextEntityAlignment.MIDDLE_CENTER); xx += w
    y -= rh; hline(y)
    for r in rows:
        cy = y - rh / 2
        if r[0] == '__line__':
            _, layer, name, note = r[:4]
            att = {'layer': layer}
            if len(r) > 4 and r[4]:
                att['linetype'] = r[4]
            msp.add_line((x + 30, cy), (x + widths[0] - 30, cy), dxfattribs=att)
            cols = [name, note, '']
        else:
            b, name, note, n = r
            msp.add_blockref(b, (x + widths[0] / 2, cy), dxfattribs={'layer': cfg.BLOCK_LAYER.get(b, cfg.BLOCK_LAYER.get('*'))})
            cols = [name, note, str(n)]
        xx = x + widths[0]
        for w, c, align in zip(widths[1:], cols, ('L', 'L', 'C')):
            t = msp.add_text(c, height=22, dxfattribs={'layer': lay, 'style': 'CHT', 'width': 0.9})
            if align == 'L':
                t.set_placement((xx + 15, cy), align=TextEntityAlignment.MIDDLE_LEFT)
            else:
                t.set_placement((xx + w / 2, cy), align=TextEntityAlignment.MIDDLE_CENTER)
            xx += w
        y -= rh; hline(y)
    xx = x
    for w in (0,) + tuple(np.cumsum(widths)):
        msp.add_line((x + w, ytop), (x + w, y), dxfattribs={'layer': lay})
    return y


if __name__ == '__main__':
    cfgname, base, regp, datap, outp = sys.argv[1:6]
    cfg = importlib.import_module(cfgname)
    print(write(cfg, base, regp, datap, outp))
