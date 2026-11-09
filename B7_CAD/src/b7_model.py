"""B7 unit geometry (cm).  rev.3 (columns added)
X: from west property line (east = +).  Y: from B6/B7 party-wall centreline (north = +).
All dimension-chain values are WALL CENTRELINES; every wall is 15 cm (h = 7.5 each side).
North wall: CL Y=534 west of axis X968, CL Y=509 east of it (25 cm step, per photos).
Shared by the 2D (DXF) generator and the 3D generator."""

T = 15.0
H = T / 2
TREAD = 25.0
LEVELS = {"GL": 0, "1F": 30, "2F": 390, "3F": 710, "RF": 1030}
PARAPET_TOP = 1030 + 140
RISERS = {"1F": (19, 18.95), "2F": (17, 18.82)}

N_W, N_E, X_STEP = 534.0, 509.0, 968.0   # north wall CLs and the step axis


def W(x0, y0, x1, y1, kind="full", h=None):
    return dict(rect=(x0, y0, x1, y1), kind=kind, h=h)


def wv(x, y0, y1, kind="full", h=None):          # vertical wall on centreline x
    return W(x - H, y0, x + H, y1, kind, h)


def wh(y, x0, x1, kind="full", h=None):          # horizontal wall on centreline y
    return W(x0, y - H, x1, y + H, kind, h)


def door(tag, rect, hinge, swing, head=210):
    return dict(type="door", tag=tag, rect=rect, hinge=hinge, swing=swing, sill=0, head=head)


def win(tag, rect, sill=90, head=210):
    return dict(type="window", tag=tag, rect=rect, sill=sill, head=head)


def dw(tag, rect, head=220):
    return dict(type="dw", tag=tag, rect=rect, sill=0, head=head)


def on_v(x, a, b):   # opening rect in a vertical wall on CL x
    return (x - H, a, x + H, b)


def on_h(y, a, b):   # opening rect in a horizontal wall on CL y
    return (a, y - H, b, y + H)


# Structural columns read from the plan photos (rev.3, sizes estimated from drawing scale).
# A/C columns centred on the column axes X460 / X1392 (the 1F chain 460|932 runs column-to-column).
COLUMNS = {
    "A1": (430, -15, 490, 15),          # 60x30, on party wall
    "A2": (430, 511.5, 490, 541.5),     # 60x30, flush with north face
    "B1": (908, -15, 968, 15),          # 60x30, on party wall
    "B2": (935.5, 481.5, 975.5, 541.5), # 40x60, at the 25 cm north-wall step
    "C1": (1362, -17.5, 1422, 17.5),    # 60x35, on party wall
    "C2": (1362, 481.5, 1422, 516.5),   # 60x35, flush with east-part north face
    "C3": (1392, 276.5, 1422, 311.5),   # 30x35, end of partition Y294
}
# 30 cm wing walls / beams from the column A line out to the balcony face X311 (the "34" on 1F)
WINGS = [W(311 - H, 511.5, 430, 541.5), W(311 - H, -15, 430, 15)]


def north_walls(x_west):
    return WINGS + [wh(N_W, 430, X_STEP + H), wh(N_E, X_STEP - H, 1392 + H),
                    wv(X_STEP, N_E - H, N_W + H)]


# ---------------------------------------------------------------- 1F  (FL +30, storey 360)
F1 = dict(
    name="1F", title="B7 一層平面圖", level=30,
    walls=north_walls(311 - H) + [
        wv(460, -H, N_W + H),                   # front wall (W2 / D1), CL 460
        wv(1392, 294 - H, N_E + H),             # east wall at toilet / stair
        wh(0, 311 - H, 1392 + H, "party"),      # party wall to B6
        wv(1225, 294 - H, N_E + H, "int"),      # toilet west
        wh(294, 1225 - H, 1392 + H, "int"),     # toilet south
        wv(1302, -H, 294 + H, "int"),           # kitchen / service-yard wall
    ],
    openings=[
        win("W2", on_v(460, 218, 488), sill=90, head=230),
        door("D1", on_v(460, 40, 190), hinge="start", swing=-1, head=230),
        win("W7", on_v(1392, 395, 465), sill=150, head=210),
        door("D4", on_v(1225, 294 + H, 376), hinge="start", swing=+1),
        door("D2", on_v(1302, 206, 281), hinge="start", swing=+1),
        win("W4", on_v(1302, 68, 173), sill=105, head=210),
    ],
)


# ---------------------------------------------------------------- 2F / 3F
def upper(name, title, level, bal_end, bath1_s, bath1_e, bath2_w, bath2_n, w5, d4b):
    return dict(
        name=name, title=title, level=level,
        walls=north_walls(311 - H) + [
            wv(441, -H, N_W + H),                              # west wall CL 441
            wv(1392, 294 - H, N_E + H),                        # east wall (stair)
            W(1400 - H, H, 1400 + H, 294 - H, "low", 110),     # east balcony parapet CL 1400
            wh(0, 311 - H, 1400 + H, "party"),                 # party wall incl. balcony divider
            W(311 - H, H, 311 + H, bal_end - H, "low", 110),   # west balcony parapet CL 311
            wh(bal_end, 311 - H, 441 + H),                     # balcony north end wall
            wh(bath1_s, 441 + H, bath1_e + H, "int"),          # bath1 south
            wv(bath1_e, bath1_s - H, N_W - H, "int"),          # bath1 east
            wv(bath2_w, H, bath2_n + H, "int"),                # bath2 west
            wh(bath2_n, bath2_w - H, X_STEP, "int"),           # bath2 north
            wv(X_STEP, H, N_E - H, "int"),                     # partition X968
            wh(294, X_STEP - H, 1400 + H, "int"),              # partition Y294 (stair | bedroom)
            wv(1302, H, 294 - H, "int"),                       # bedroom / east balcony (DW2)
        ],
        openings=[
            win("W5", on_v(441, *w5), sill=120, head=210),
            dw("DW1", on_v(441, 60, 275)),
            door("D4", on_v(bath1_e, bath1_s + H, bath1_s + H + 75), hinge="start", swing=-1),
            door("D3", on_v(X_STEP, 372, 457), hinge="end", swing=-1),
            door("D4", on_v(X_STEP, *d4b), hinge="end", swing=-1),
            door("D3", on_h(294, X_STEP + H, X_STEP + H + 82), hinge="start", swing=-1),
            win("W8", on_h(294, 1310, 1370), sill=100, head=210),
            dw("DW2", on_v(1302, 77, 227)),
        ],
        bal_end=bal_end, bath1_s=bath1_s, bath1_e=bath1_e, bath2_w=bath2_w, bath2_n=bath2_n,
    )


F2 = upper("2F", "B7 二層平面圖", 390, bal_end=365, bath1_s=334, bath1_e=765,
           bath2_w=805, bath2_n=244, w5=(393, 473), d4b=(164, 236))
F3 = upper("3F", "B7 三層平面圖", 710, bal_end=360, bath1_s=374, bath1_e=711,
           bath2_w=791, bath2_n=270, w5=(398, 478), d4b=(190, 262))

FLOORS = [F1, F2, F3]

# U-shaped stair between east north wall (inner face 501.5) and partition Y294 (face 301.5)
BAND1 = (409.5, N_E - H)      # north flight
CENTER = (394.5, 409.5)       # 15 cm centre wall
BAND2 = (294 + H, 394.5)      # south flight
LANDING_X = (1302, 1392 - H)
FLIGHT_A = [1002 + TREAD * i for i in range(13)]   # 1F -> landing, band1, 13 risers
FLIGHT_B = [1177 + TREAD * i for i in range(6)]    # landing -> 2F, band2, 6 risers
FLIGHT_C = [1102 + TREAD * i for i in range(9)]    # 2F -> landing, band1, 9 risers
FLIGHT_D = [1127 + TREAD * i for i in range(8)]    # landing -> 3F, band2, 8 risers
