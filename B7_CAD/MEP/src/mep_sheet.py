"""Contact sheet of unassigned text candidates (rendered from PDF vectors).
usage: python3 mep_sheet.py PDF OUT.json OUT.png [maxw]"""
import sys, json
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
pdf, js, out = sys.argv[1:4]
maxw = float(sys.argv[4]) if len(sys.argv) > 4 else 1e9
FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
d = json.load(open(js))
cands = [t for t in d['unassigned'] if (t['box'][2] - t['box'][0]) <= maxw]
cands.sort(key=lambda t: (t['box'][1], t['box'][0]))
page = fitz.open(pdf)[0]
tiles = []
for t in cands:
    b = t['box']; pad = 3
    clip = fitz.Rect(b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
    z = min(14, 220 / max(clip.width, clip.height))
    pm = page.get_pixmap(matrix=fitz.Matrix(z, z), clip=clip)
    im = Image.frombytes('RGB', (pm.width, pm.height), pm.samples)
    lab = f"{(b[0]+b[2])/2:.0f},{(b[1]+b[3])/2:.0f}"
    tile = Image.new('RGB', (max(im.width, 110), im.height + 18), 'white')
    tile.paste(im, (0, 18)); ImageDraw.Draw(tile).text((2, 1), lab, fill=(200, 0, 0), font=FONT)
    tiles.append(tile)
W = 1900; x = y = rowh = 0; pos = []
for t in tiles:
    if x + t.width > W:
        x = 0; y += rowh + 6; rowh = 0
    pos.append((x, y)); x += t.width + 6; rowh = max(rowh, t.height)
sheet = Image.new('RGB', (W, y + rowh + 4), (230, 230, 230))
for t, p in zip(tiles, pos):
    sheet.paste(t, p)
sheet.save(out); print(len(tiles), sheet.size)
