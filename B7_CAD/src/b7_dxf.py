import math
import sys
import ezdxf
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import box
from shapely.ops import unary_union

sys.path.insert(0, sys.argv[1])
from b7_model import (BEAMS, WINDER_X, COLUMNS, FLOORS, F1, F2, F3, BAND1, BAND2, CENTER, LANDING_X,
                      FLIGHT_A, FLIGHT_B, FLIGHT_C, FLIGHT_D, LEVELS)

OUT = sys.argv[2]
OFFSETS = {"1F": 0, "2F": 1900, "3F": 3700}

doc = ezdxf.new("R2010", setup=True)
doc.header["$INSUNITS"] = 5          # centimetres
doc.header["$MEASUREMENT"] = 1
doc.header["$LTSCALE"] = 8
msp = doc.modelspace()

LAYERS = {
    "A-WALL": 7, "A-WALL-PATT": 8, "A-WALL-LOW": 4, "A-DOOR": 3, "A-WIND": 4,
    "A-STAIR": 2, "A-FIXT": 6, "A-HIDDEN": 8, "A-ANNO-DIMS": 1, "A-ANNO-TEXT": 7,
    "A-ANNO-TAG": 2, "S-COLS": 7, "S-COLS-PATT": 250, "S-BEAM": 8, "A-SITE": 8, "A-SITE-PL": 1, "A-SITE-FENCE": 7, "A-TITLE": 7,
}
for name, color in LAYERS.items():
    doc.layers.add(name, color=color)
doc.layers.get("A-HIDDEN").dxf.linetype = "DASHED"
doc.layers.get("A-SITE-PL").dxf.linetype = "DASHDOT"
doc.layers.get("S-BEAM").dxf.linetype = "DASHED"

cht = doc.styles.add("CHT", font="msjh.ttc")
cht.set_extended_font_data(family="Microsoft JhengHei")
doc.styles.add("DIMTXT", font="arial.ttf")

ds = doc.dimstyles.new("ARCH_CM")
ds.dxf.dimtxt = 11
ds.dxf.dimasz = 5
ds.dxf.dimblk = "ARCHTICK"
ds.dxf.dimexe = 4
ds.dxf.dimexo = 3
ds.dxf.dimgap = 2
ds.dxf.dimdec = 0
ds.dxf.dimtad = 1
ds.dxf.dimtih = 0
ds.dxf.dimtoh = 0
ds.dxf.dimtxsty = "DIMTXT"
ds.dxf.dimclrd = 1
ds.dxf.dimclre = 1
ds.dxf.dimclrt = 7
ds.dxf.dimtix = 0
ds.dxf.dimtmove = 0


def P(fl, x, y):
    return (x + OFFSETS[fl], y)


def text(fl, x, y, s, h=16, layer="A-ANNO-TEXT", rot=0, style="CHT"):
    t = msp.add_text(s, height=h, rotation=rot, dxfattribs={"layer": layer, "style": style})
    t.set_placement(P(fl, x, y), align=TextEntityAlignment.MIDDLE_CENTER)
    return t


def pline(fl, pts, layer, closed=False, **kw):
    return msp.add_lwpolyline([P(fl, *p) for p in pts], close=closed,
                              dxfattribs={"layer": layer, **kw})


def rect(fl, x0, y0, x1, y1, layer, **kw):
    return pline(fl, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer, closed=True, **kw)


def line(fl, a, b, layer, **kw):
    return msp.add_line(P(fl, *a), P(fl, *b), dxfattribs={"layer": layer, **kw})


def circle(fl, c, r, layer):
    return msp.add_circle(P(fl, *c), r, dxfattribs={"layer": layer})


def ellipse(fl, c, rx, ry, layer):
    if rx >= ry:
        return msp.add_ellipse(P(fl, *c), major_axis=(rx, 0), ratio=ry / rx, dxfattribs={"layer": layer})
    return msp.add_ellipse(P(fl, *c), major_axis=(0, ry), ratio=rx / ry, dxfattribs={"layer": layer})


def tag(fl, x, y, s):
    circle(fl, (x, y), 14, "A-ANNO-TAG")
    text(fl, x, y, s, h=9 if len(s) > 2 else 10, layer="A-ANNO-TAG", style="DIMTXT")


def dim(fl, p1, p2, base, vertical=False):
    d = msp.add_linear_dim(base=P(fl, *base), p1=P(fl, *p1), p2=P(fl, *p2),
                           angle=90 if vertical else 0, dimstyle="ARCH_CM",
                           dxfattribs={"layer": "A-ANNO-DIMS"})
    d.render()


def hchain(fl, xs, y, y_ref):
    for a, b in zip(xs, xs[1:]):
        dim(fl, (a, y_ref), (b, y_ref), (a, y))


def vchain(fl, ys, x, x_ref):
    for a, b in zip(ys, ys[1:]):
        dim(fl, (x_ref, a), (x_ref, b), (x, a), vertical=True)


def poly_to_dxf(fl, geom, layer, hatch_layer, pattern):
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    for pg in polys:
        rings = [list(pg.exterior.coords)] + [list(r.coords) for r in pg.interiors]
        for r in rings:
            pline(fl, r[:-1], layer, closed=True)
        h = msp.add_hatch(color=8 if pattern == "SOLID" else 4, dxfattribs={"layer": hatch_layer})
        if pattern != "SOLID":
            h.set_pattern_fill(pattern, scale=1.5)
        for i, r in enumerate(rings):
            h.paths.add_polyline_path([P(fl, *p) for p in r[:-1]], is_closed=True,
                                      flags=1 if i == 0 else 0)


# ---------------------------------------------------------------- walls & openings
def draw_walls(F):
    fl = F["name"]
    holes = unary_union([box(*o["rect"]) for o in F["openings"]])
    cols = [box(*c) for c in COLUMNS.values()]
    full = unary_union([box(*w["rect"]) for w in F["walls"] if w["kind"] != "low"] + cols).difference(holes)
    low = unary_union([box(*w["rect"]) for w in F["walls"] if w["kind"] == "low"]).difference(
        unary_union([box(*w["rect"]) for w in F["walls"] if w["kind"] != "low"]))
    poly_to_dxf(fl, full.simplify(0.01), "A-WALL", "A-WALL-PATT", "SOLID")
    poly_to_dxf(fl, low.simplify(0.01), "A-WALL-LOW", "A-WALL-LOW", "ANSI31")
    for name, (x0, y0, x1, y1) in COLUMNS.items():          # RC columns: outline + dark fill
        rect(fl, x0, y0, x1, y1, "S-COLS")
        h = msp.add_hatch(color=250, dxfattribs={"layer": "S-COLS-PATT"})
        h.paths.add_polyline_path([P(fl, x0, y0), P(fl, x1, y0), P(fl, x1, y1), P(fl, x0, y1)], is_closed=True)


def opening_axes(o):
    x0, y0, x1, y1 = o["rect"]
    if (x1 - x0) < (y1 - y0):   # vertical wall, run along Y
        return "V", (y0, y1), (x0, x1)
    return "H", (x0, x1), (y0, y1)


def xy(orient, run, off):
    return (off, run) if orient == "V" else (run, off)


def draw_opening(fl, o):
    orient, (s0, s1), (f0, f1) = opening_axes(o)
    width = s1 - s0
    if o["type"] == "window":
        for off in (f0, f1, (f0 + f1) / 2 - 1.5, (f0 + f1) / 2 + 1.5):
            line(fl, xy(orient, s0, off), xy(orient, s1, off), "A-WIND")
    elif o["type"] == "dw":
        c = (f0 + f1) / 2
        m = (s0 + s1) / 2
        for off in (f0, f1):
            line(fl, xy(orient, s0, off), xy(orient, s1, off), "A-WIND")
        for (a, b, o0, o1) in ((s0, m + 5, c - 3.5, c - 0.5), (m - 5, s1, c + 0.5, c + 3.5)):
            p = [xy(orient, a, o0), xy(orient, b, o0), xy(orient, b, o1), xy(orient, a, o1)]
            pline(fl, p, "A-WIND", closed=True)
    else:  # swing door
        sw = o["swing"]
        face = f1 if sw > 0 else f0
        hs = s0 if o["hinge"] == "start" else s1
        other = s1 if o["hinge"] == "start" else s0
        hinge = xy(orient, hs, face)
        open_end = xy(orient, hs, face + sw * width)
        line(fl, hinge, open_end, "A-DOOR")
        closed_end = xy(orient, other, face)
        a1 = math.degrees(math.atan2(closed_end[1] - hinge[1], closed_end[0] - hinge[0])) % 360
        a2 = math.degrees(math.atan2(open_end[1] - hinge[1], open_end[0] - hinge[0])) % 360
        start, end = (a1, a2) if (a2 - a1) % 360 == 90 else (a2, a1)
        msp.add_arc(P(fl, *hinge), width, start, end, dxfattribs={"layer": "A-DOOR"})


# ---------------------------------------------------------------- fixtures
def wc(fl, tank, bowl_c, horizontal=False):
    rect(fl, *tank, "A-FIXT")
    if horizontal:
        ellipse(fl, bowl_c, 24, 18, "A-FIXT")
    else:
        ellipse(fl, bowl_c, 18, 24, "A-FIXT")


def basin(fl, r, c, rx=20, ry=15):
    rect(fl, *r, "A-FIXT")
    ellipse(fl, c, rx, ry, "A-FIXT")
    circle(fl, c, 2, "A-FIXT")


def stair_flight(fl, risers, band, layer, upto=None):
    for i, x in enumerate(risers):
        lay = layer if (upto is None or x <= upto) else "A-HIDDEN"
        line(fl, (x, band[0]), (x, band[1]), lay)


def arrow_path(fl, pts, label, label_pos):
    pline(fl, pts, "A-STAIR")
    circle(fl, pts[0], 3, "A-STAIR")
    (xa, ya), (xb, yb) = pts[-2], pts[-1]
    ang = math.atan2(yb - ya, xb - xa)
    L, Wd = 12, 4
    bx, by = xb - L * math.cos(ang), yb - L * math.sin(ang)
    nx, ny = -math.sin(ang) * Wd, math.cos(ang) * Wd
    s = msp.add_solid([P(fl, xb, yb), P(fl, bx + nx, by + ny), P(fl, bx - nx, by - ny)],
                      dxfattribs={"layer": "A-STAIR"})
    text(fl, *label_pos, label, h=13, layer="A-STAIR")


def break_line(fl, x, band):
    y0, y1 = band
    ym = (y0 + y1) / 2
    pline(fl, [(x - 12, y0), (x - 2, ym - 6), (x + 4, ym + 6), (x + 14, y1)], "A-STAIR")


# ---------------------------------------------------------------- 1F
def draw_1f():
    fl = "1F"
    F = F1
    draw_walls(F)
    for o in F["openings"]:
        draw_opening(fl, o)
    # stair flight A: 2 winders in the corner X968-1052 (enter from the south, turn east),
    # straight R3..R13 (t=25); plan cut after R8, upper part / landing / flight B dashed
    wx0, wx1 = WINDER_X
    b2_south = COLUMNS["B2"][1]
    line(fl, (wx0, CENTER[0]), (wx1, CENTER[0]), "A-STAIR")                 # R1 (first riser)
    line(fl, (wx0, b2_south), (wx1, CENTER[1]), "A-STAIR")                 # R2 (winder)
    line(fl, (wx0, CENTER[0]), (wx0, b2_south), "A-STAIR")                 # open west edge on axis X968
    stair_flight(fl, FLIGHT_A, BAND1, "A-STAIR", upto=FLIGHT_A[5])
    break_line(fl, FLIGHT_A[5] + 12, BAND1)
    rect(fl, wx1, CENTER[0], 1225 - 7.5, CENTER[1], "A-STAIR")             # handrail / stringer
    stair_flight(fl, FLIGHT_B, BAND2, "A-HIDDEN")
    rect(fl, FLIGHT_B[0], BAND2[0], LANDING_X[0], BAND2[1], "A-HIDDEN")
    rect(fl, LANDING_X[0], BAND2[0], LANDING_X[1], BAND1[1], "A-HIDDEN")
    arrow_path(fl, [(1010, CENTER[0] + 5), (1010, 452), (FLIGHT_A[5] + 2, 452)], "上19", (1000, 375))
    # 2F balcony above the rear service yard
    rect(fl, 1309.5, 7.5, 1407.5, 286.5, "A-HIDDEN")
    # kitchen
    rect(fl, 1000, 15, 1070, 88, "A-FIXT")
    line(fl, (1000, 15), (1070, 88), "A-FIXT"); line(fl, (1000, 88), (1070, 15), "A-FIXT")
    text(fl, 1035, 100, "冰箱", h=9, layer="A-FIXT")
    rect(fl, 1073, 7.5, 1294.5, 68, "A-FIXT")
    rect(fl, 1085, 15, 1165, 60, "A-FIXT"); circle(fl, (1125, 38), 3, "A-FIXT")
    rect(fl, 1198, 14, 1272, 62, "A-FIXT")
    circle(fl, (1216, 38), 10, "A-FIXT"); circle(fl, (1254, 38), 10, "A-FIXT")
    # toilet
    wc(fl, (1308, 481.5, 1358, 501.5), (1333, 458))
    basin(fl, (1340, 326, 1384.5, 382), (1362, 354), rx=15, ry=19)
    # site context
    rect(fl, 0, 7.5, 452.5, 526.5, "A-SITE")
    pline(fl, [(25, 300), (420, 300), (430, 315), (430, 445), (420, 460), (25, 460), (15, 445), (15, 315)],
          "A-SITE", closed=True)
    rect(fl, 257, 214, 394, 496, "A-HIDDEN")
    text(fl, 325, 355, "汙水處理設備(6人份)", h=10, layer="A-SITE", rot=90)
    text(fl, 220, 120, "停車位", h=20, layer="A-SITE")
    k = 0.052   # property-line slope (from photo, schematic)
    pline(fl, [(0, 615), (1500, 615 - k * 1500)], "A-SITE-PL")
    line(fl, (1500, 615 - k * 1500), (1500, -40), "A-SITE-PL")
    text(fl, 1000, 585, "地界線(位置示意)", h=11, layer="A-SITE-PL", rot=-3)
    pline(fl, [(0, 615), (460, 615 - k * 460), (460, 541.5), (444, 541.5), (444, 615 - k * 444 - 16), (0, 599)],
          "A-SITE-FENCE", closed=True)
    text(fl, 150, 575, "圍牆 H200 t16", h=10, layer="A-SITE", rot=-3)
    rect(fl, 1484, 0, 1500, 517, "A-SITE-FENCE")
    text(fl, 1530, 260, "圍牆 H200 t16  L=517", h=10, layer="A-SITE", rot=90)
    text(fl, 1450, 160, "後側空地", h=11, layer="A-SITE", rot=90)
    # room labels
    text(fl, 700, 300, "客廳", h=22); text(fl, 1090, 250, "餐廳", h=20)
    text(fl, 1160, 110, "廚房", h=20); text(fl, 1290, 470, "廁所", h=15)
    text(fl, 1356, 150, "後院/工作陽台", h=10)
    circle(fl, (760, 200), 30, "A-ANNO-TEXT"); text(fl, 760, 200, "B7", h=24, style="DIMTXT")
    text(fl, 760, 145, "住宅 +30", h=16)
    for t, x, y in (("W2", 505, 350), ("D1", 505, 115), ("W7", 1432, 430), ("D4", 1195, 340),
                    ("D2", 1270, 243), ("W4", 1268, 120)):
        tag(fl, x, y, t)
    # dimensions (wall centrelines, as on original sheet)
    hchain(fl, [0, 1500], 760, 534)
    hchain(fl, [0, 460, 1392, 1500], 715, 534)
    hchain(fl, [311, 460, 968, 1225, 1392, 1500], 670, 534)
    vchain(fl, [0, 294, 509, 534], 1590, 1408)
    vchain(fl, [0, 534], 1640, 1408)
    vchain(fl, [0, 534], -60, 0)
    hchain(fl, [1302, 1392], 200, 200)


# ---------------------------------------------------------------- 2F / 3F
def draw_upper(F):
    fl = F["name"]
    draw_walls(F)
    for o in F["openings"]:
        draw_opening(fl, o)
    be = F["bal_end"]
    # decorative louver panel (裝飾板) on CL X341
    rect(fl, 337.5, be + 7.5, 344.5, 511.5, "A-FIXT")
    y = be + 15
    while y < 508:
        line(fl, (331, y), (337.5, y), "A-FIXT"); y += 8
    # stair centre wall + landing
    rect(fl, 1095, CENTER[0], LANDING_X[0], CENTER[1], "A-STAIR")
    line(fl, (LANDING_X[0], BAND2[0]), (LANDING_X[0], BAND1[1]), "A-STAIR")
    if fl == "2F":
        stair_flight(fl, FLIGHT_C, BAND1, "A-STAIR", upto=FLIGHT_C[4])
        break_line(fl, FLIGHT_C[4] + 12, BAND1)
        stair_flight(fl, FLIGHT_B, BAND2, "A-STAIR")
        arrow_path(fl, [(FLIGHT_C[0] + 12, 470), (FLIGHT_C[4] + 2, 470)], "上17", (FLIGHT_C[0] - 22, 470))
        arrow_path(fl, [(FLIGHT_B[0] + 12, 345), (1345, 345), (1345, 455), (FLIGHT_C[5] + 14, 455)],
                   "下19", (FLIGHT_B[0] - 22, 345))
        lvl = "+390"
    else:
        stair_flight(fl, FLIGHT_C, BAND1, "A-STAIR")
        stair_flight(fl, FLIGHT_D, BAND2, "A-STAIR")
        rect(fl, FLIGHT_C[0] - 6, BAND1[0], FLIGHT_C[0], BAND1[1], "A-STAIR")   # guard rail at void edge
        arrow_path(fl, [(FLIGHT_D[0] + 12, 345), (1345, 345), (1345, 455), (FLIGHT_C[0] + 14, 455)],
                   "下17", (FLIGHT_D[0] - 22, 345))
        rect(fl, 1310, 20, 1390, 97, "A-HIDDEN")
        line(fl, (1310, 20), (1390, 97), "A-HIDDEN"); line(fl, (1310, 97), (1390, 20), "A-HIDDEN")
        text(fl, 1350, 110, "設備位置(推估)", h=8, layer="A-FIXT")
        lvl = "+710"
    # bath 1
    b1s, b1e = F["bath1_s"], F["bath1_e"]
    if fl == "2F":
        rect(fl, 449, 348, 519, 505, "A-FIXT")                                  # bathtub 70x157
        rect(fl, 456, 356, 512, 497, "A-FIXT")
        circle(fl, (484, 366), 3, "A-FIXT")
        line(fl, (599, b1s + 7.5), (599, 526.5), "A-FIXT")                      # glass screen
        wc(fl, (615, 506.5, 665, 526.5), (640, 482))
        basin(fl, (690, 472, b1e - 7.5, 526.5), (724, 499))
    else:
        line(fl, (543, b1s + 7.5), (543, 488), "A-FIXT")                         # shower screen
        circle(fl, (497, 445), 4, "A-FIXT"); circle(fl, (497, 515), 3, "A-FIXT")
        wc(fl, (570, 506.5, 620, 526.5), (595, 482))
        basin(fl, (630, 476, b1e - 7.5, 526.5), (667, 501), rx=18, ry=13)
    # bath 2
    bw, bn = F["bath2_w"], F["bath2_n"]
    basin(fl, (bw + 7.5, bn - 55, bw + 50, bn - 7.5), (bw + 29, bn - 31), rx=15, ry=17)
    wc(fl, (bw + 7.5, bn - 125, bw + 27.5, bn - 75), (bw + 51, bn - 100), horizontal=True)
    line(fl, (bw + 7.5, 104), (920, 104), "A-FIXT")
    circle(fl, (bw + 22, 40), 4, "A-FIXT"); circle(fl, (900, 55), 3, "A-FIXT")
    # labels
    text(fl, 610, 190, "臥室", h=22); text(fl, 1150, 170, "臥室", h=22)
    text(fl, 560 if fl == "2F" else 600, 420 if fl == "2F" else 430, "浴廁", h=15)
    text(fl, 905, bn - 85, "浴廁", h=15)
    text(fl, 372, 180, "陽台", h=18); text(fl, 1350, 175, "陽台", h=15)
    text(fl, 388, 480, "裝飾板", h=12)
    circle(fl, (866, 400), 28, "A-ANNO-TEXT"); text(fl, 866, 400, "B7", h=22, style="DIMTXT")
    text(fl, 866, 345, "住宅 " + lvl, h=15)
    w5c = sum(o["rect"][1] + o["rect"][3] for o in F["openings"] if o["tag"] == "W5") / 2
    d4 = [o for o in F["openings"] if o["tag"] == "D4"]
    for t, x, y in (("W5", 388, w5c - 25), ("DW1", 490, 170), ("D4", b1e + 35, b1s + 45),
                    ("D3", 1005, 415), ("D4", 1005, (d4[1]["rect"][1] + d4[1]["rect"][3]) / 2),
                    ("D3", 1090, 250), ("W8", 1340, 330), ("DW2", 1265, 150)):
        tag(fl, x, y, t)
    # dimensions (as on original sheets)
    hchain(fl, [311, 441, 1392], 720, 534)
    hchain(fl, [341, 441, 711, 968, 1392, 1500], 675, 534)
    vchain(fl, [0, 294, 509, 534], 1590, 1408)
    vchain(fl, [0, 534], 1640, 1408)
    vchain(fl, [0, be, 534], 250, 311)
    hchain(fl, [1302, 1392], 340, 340)
    hchain(fl, [1302, 1400, 1500], 200, 200)
    if fl == "3F":
        vchain(fl, [0, 374, 534], 556, 556)
        vchain(fl, [270, 534], 822, 822)


draw_1f()
draw_upper(F2)
draw_upper(F3)

# beams (dashed long edges) + per-plan disclaimers
for F in FLOORS:
    fl = F["name"]
    for name, (x0, y0, x1, y1) in BEAMS.items():
        if (x1 - x0) >= (y1 - y0):
            segs = [((x0, y0), (x1, y0)), ((x0, y1), (x1, y1))]
        else:
            segs = [((x0, y0), (x0, y1)), ((x1, y0), (x1, y1))]
        for a, b in segs:
            line(fl, a, b, "S-BEAM", ltscale=2.5)
    text(fl, 750, -185, "※ 柱：依圖面比例繪製，非實際尺寸　　梁（虛線）：30x60", h=14, layer="A-TITLE")

# column labels
for F in FLOORS:
    for name, (x0, y0, x1, y1) in COLUMNS.items():
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        oy = 32 if cy < 270 else -32
        text(F["name"], cx, cy + oy, name, h=8, layer="S-COLS", style="DIMTXT")

# titles
for F in FLOORS:
    fl = F["name"]
    text(fl, 750, -130, F["title"] + "   S=1/50", h=34, layer="A-TITLE")
    line(fl, (380, -158), (1120, -158), "A-TITLE")

NOTES = (
    "B7戶 平面圖 rev.4（依原圖照片判讀重繪，非原始CAD）\\P"
    "1. 單位：cm。尺寸鍊均為牆中心線（依原圖）；原圖無標註者依圖面比例量取。\\P"
    "2. 外牆、分戶牆、隔間牆、女兒牆厚度均為15。\\P"
    "3. 北側外牆於X=968處退縮25：X968以西中心線Y=534，以東中心線Y=509（即右側尺寸鍊25/215/294）。\\P"
    "4. 西側外牆：1F中心線X=460（149=311→460），2F/3F中心線X=441（130=311→441），二三樓外牆較一樓外推19。\\P"
    "5. 高程：GL±0、1FL+30、2FL+390、3FL+710、RFL+1030；1F層高360、2F/3F層高320；女兒牆頂約+1170。\\P"
    "6. 樓梯：1F→2F 19級@18.95=360（1F起步2階扇形踏步，自X=968轉向東）；2F→3F 17級@18.82=320；踏面25；梯寬約92。\\P"
    "7. 柱：依圖面比例繪製，非實際尺寸（A、B、C柱以柱中心線X=460/968/1392定位），請依結構圖修正。\\P"
    "8. 梁（虛線，S-BEAM圖層）：30x60。\\P"
    "9. 門窗寬度依圖面比例量取，請以門窗表核對。"
)
mt = msp.add_mtext(NOTES, dxfattribs={"layer": "A-TITLE", "style": "CHT", "char_height": 14})
mt.set_location((OFFSETS["1F"], -230))
mt.dxf.width = 1750

doc.saveas(OUT)
print("saved", OUT)
