"""Master legend (圖例表) DXF covering all five MEP sheets + audit of each sheet."""
import sys, io, contextlib, importlib
from collections import Counter
import ezdxf
from ezdxf import recover
from ezdxf.enums import TextEntityAlignment
sys.path.insert(0, sys.path[0])
import mep_blocks
from mep_write import draw_table

SHEETS = [('rec', '插座'), ('lit', '照明'), ('tel', '電信'), ('wat', '給水'), ('drn', '排水')]
dxfdir, out = sys.argv[1], sys.argv[2]

rows_by_sys = []
for key, name in SHEETS:
    cfg = importlib.import_module('cfg_' + key)
    path = f'{dxfdir}/B7_{name}設備配置圖.dxf'
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        doc, aud = recover.readfile(path)
    msp = doc.modelspace()
    cnt = Counter(e.dxf.name for e in msp.query('INSERT') if e.dxf.name in mep_blocks.LEGEND or True
                  if e.dxf.insert.x < 7800)
    auditor = doc.audit()
    print(f'{name}: audit errors {len(auditor.errors)} fixes {len(auditor.fixes)}; inserts',
          {b: n for b, n in cnt.items() if b in cfg.LEGEND_ORDER}, 'texts', len(msp.query('TEXT')),
          'polylines', len(msp.query('LWPOLYLINE')))
    LN = getattr(cfg, 'LEGEND_NAME', {})
    rows = []
    for b in cfg.LEGEND_ORDER:
        if cnt.get(b):
            t, n = LN.get(b, mep_blocks.LEGEND.get(b, ('', ''))[:2]) if b in LN else (None, None)
            rows.append((b, t, n, cnt[b], cfg))
    rows_by_sys.append((name, cfg, rows))

doc = ezdxf.new('R2018', setup=True)
doc.header['$INSUNITS'] = 5
st = doc.styles.add('CHT', font='msjh.ttc'); st.set_extended_font_data(family='Microsoft JhengHei')
mep_blocks.build(doc)
from ezdxf.tools.standards import linetypes
for nm, desc, pat in linetypes():
    if nm in ('DASHDOT', 'HIDDEN', 'DASHED') and nm not in doc.linetypes:
        doc.linetypes.add(nm, pattern=pat, description=desc)
doc.header['$LTSCALE'] = 20
msp = doc.modelspace()
doc.layers.add('A-圖例', color=7)
x0 = 0
for name, cfg, rows in rows_by_sys:
    for ln, (aci, lt) in cfg.LAYERS.items():
        if ln not in doc.layers:
            doc.layers.add(ln, color=aci, linetype=lt)
    LN = getattr(cfg, 'LEGEND_NAME', {})
    trows = []
    for b, t, n, c, _ in rows:
        title, note = LN.get(b, mep_blocks.LEGEND[b][:2])
        trows.append((b, title, note, c))
    trows += [('__line__', *r) for r in cfg.LINE_LEGEND]
    H = 200 + 70 * (len(trows) + 1) + 80
    msp.add_lwpolyline([(x0, 0), (x0 + 2100, 0), (x0 + 2100, -H), (x0, -H)], close=True, dxfattribs={'layer': 'A-圖例'})
    t = msp.add_text(f'B7 {name}設備 圖例表', height=45, dxfattribs={'layer': 'A-圖例', 'style': 'CHT'})
    t.set_placement((x0 + 120, -100), align=TextEntityAlignment.MIDDLE_LEFT)
    draw_table(msp, 'A-圖例', trows, x0 + 120, -180, cfg)
    x0 += 2300
note = msp.add_mtext('註：1. 圖例依台灣建築電氣/給排水設計慣用圖例繪製，相同圖例均為圖塊(BLOCK)，可整批修改。\\P'
                     '2. 迴路編號、開關型式、出線口編號為圖塊屬性(ATTRIB)，可直接編輯。\\P'
                     '3. 數量為各配置圖(1F~3F)圖塊統計。單位：cm，比例 1/100。',
                     dxfattribs={'layer': 'A-圖例', 'style': 'CHT', 'char_height': 26})
note.set_location((0, 200)); note.dxf.width = 6000
doc.saveas(out)
print('legend saved', out)
