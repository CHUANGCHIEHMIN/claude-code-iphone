"""Render colored PDF paths in a region at high zoom with circle ids and a pt grid.
usage: python3 mep_view.py PDF OUT.png x0 y0 x1 y1 [zoom]"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, sys.path[0])
from mep_paths import paths

pdf, out = sys.argv[1], sys.argv[2]
x0, y0, x1, y1 = map(float, sys.argv[3:7])
Z = float(sys.argv[7]) if len(sys.argv) > 7 else 5
import pymupdf as fitz
page = fitz.open(pdf)[0]
W, H = int((x1 - x0) * Z), int((y1 - y0) * Z)
im = Image.new('RGB', (W, H), 'white'); g = ImageDraw.Draw(im)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
# gray architecture first, light
for d in page.get_drawings():
    c = d.get('color')
    if c is None or tuple(round(v, 2) for v in c) != (0.5, 0.5, 0.5):
        continue
    for it in d['items']:
        if it[0] == 'l':
            g.line([((it[1].x - x0) * Z, (it[1].y - y0) * Z), ((it[2].x - x0) * Z, (it[2].y - y0) * Z)], fill=(200, 200, 200))
# grid every 10 pt
for gx in np.arange(np.ceil(x0 / 10) * 10, x1, 10):
    g.line([((gx - x0) * Z, 0), ((gx - x0) * Z, H)], fill=(235, 235, 255) if gx % 50 else (190, 190, 255))
    if gx % 50 == 0: g.text(((gx - x0) * Z + 2, 2), str(int(gx)), fill=(80, 80, 200), font=font)
for gy in np.arange(np.ceil(y0 / 10) * 10, y1, 10):
    g.line([(0, (gy - y0) * Z), (W, (gy - y0) * Z)], fill=(235, 235, 255) if gy % 50 else (190, 190, 255))
    if gy % 50 == 0: g.text((2, (gy - y0) * Z + 2), str(int(gy)), fill=(80, 80, 200), font=font)
ps = paths(pdf)
for i, p in enumerate(ps):
    P = p['P']
    if P[:, 0].max() < x0 or P[:, 0].min() > x1 or P[:, 1].max() < y0 or P[:, 1].min() > y1:
        continue
    c = p['color'] or p['fill'] or (0, 0, 0)
    col = tuple(int(v * 200) for v in c)
    pts = [((x - x0) * Z, (y - y0) * Z) for x, y in P]
    if p['fill'] is not None and len(pts) > 2:
        g.polygon(pts, fill=tuple(int(v * 200) for v in p['fill']))
    elif len(pts) > 1:
        g.line(pts, fill=col, width=2)
    if p['type'] == 'circle':
        cx, cy = p['c']; g.text(((cx - x0) * Z + p['r'] * Z * 0.7, (cy - y0) * Z - p['r'] * Z - 12), f'#{i}', fill=(0, 0, 0), font=font)
im.save(out)
print(W, H)
