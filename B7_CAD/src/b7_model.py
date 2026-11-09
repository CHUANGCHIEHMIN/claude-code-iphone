"""B7 unit geometry (cm). X: from west property line (east = +). Y: from B6/B7 party-wall
centreline (north = +). North exterior wall outer face at Y=534.
Shared by the 2D (DXF) generator and the later 3D generator."""

TREAD = 25.0
LEVELS = {"GL": 0, "1F": 30, "2F": 390, "3F": 710, "RF": 1030}
PARAPET_TOP = 1030 + 140
RISERS = {"1F": (19, 18.95), "2F": (17, 18.82)}


def W(x0, y0, x1, y1, kind="full", h=None):
    return dict(rect=(x0, y0, x1, y1), kind=kind, h=h)


def door(tag, rect, hinge, swing, head=210):
    return dict(type="door", tag=tag, rect=rect, hinge=hinge, swing=swing, sill=0, head=head)


def win(tag, rect, sill=90, head=210):
    return dict(type="window", tag=tag, rect=rect, sill=sill, head=head)


def dw(tag, rect, head=220):
    return dict(type="dw", tag=tag, rect=rect, sill=0, head=head)


# ---------------------------------------------------------------- 1F
F1 = dict(
    name="1F", title="B7 一層平面圖", level=30,
    walls=[
        W(311, 509, 1408, 534),            # north exterior (stub to X311 supports 2F balcony end)
        W(450, -10, 470, 534),             # west exterior (front, W2 / D1)
        W(1392, 294, 1408, 534),           # east exterior at toilet / stair
        W(1392, -10, 1408, 294, "low", 110),  # east parapet of rear service balcony (推估)
        W(450, -10, 1408, 10, "party"),    # party wall to B6
        W(1219, 294, 1231, 509, "int"),    # toilet west
        W(1219, 288, 1392, 300, "int"),    # toilet south
        W(1296, 10, 1308, 288, "int"),     # kitchen / service-balcony wall
    ],
    openings=[
        win("W2", (450, 240, 470, 480), sill=60, head=240),
        door("D1", (450, 95, 470, 205), hinge="start", swing=-1, head=220),
        win("W7", (1392, 400, 1408, 470), sill=150, head=210),
        door("D4", (1219, 330, 1231, 402), hinge="start", swing=+1),
        door("D2", (1296, 205, 1308, 285), hinge="end", swing=+1),
        win("W4", (1296, 75, 1308, 175), sill=110, head=210),
    ],
)

# ---------------------------------------------------------------- 2F / 3F common
def upper(name, title, level, bal_end, bath1_s, bath1_e, bath2_w, bath2_n,
          w5, d4a, d4b):
    return dict(
        name=name, title=title, level=level,
        walls=[
            W(311, 509, 1408, 534),                       # north exterior + overhang to balcony face
            W(431, -10, 451, 534),                        # west exterior
            W(1392, 294, 1408, 534),                      # east exterior (stair)
            W(1392, -10, 1408, 294, "low", 110),          # east balcony parapet
            W(311, -10, 1408, 10, "party"),               # party wall incl. balcony divider
            W(311, 10, 323, bal_end - 10, "low", 110),    # west balcony parapet
            W(311, bal_end - 10, 431, bal_end + 10),      # balcony north end wall
            W(451, bath1_s - 6, bath1_e + 6, bath1_s + 6, "int"),   # bath1 south
            W(bath1_e - 6, bath1_s - 6, bath1_e + 6, 509, "int"),   # bath1 east
            W(bath2_w - 6, 10, bath2_w + 6, bath2_n + 6, "int"),    # bath2 west
            W(bath2_w - 6, bath2_n - 6, 962, bath2_n + 6, "int"),   # bath2 north
            W(962, 10, 974, 509, "int"),                  # partition X968
            W(962, 288, 1392, 300, "int"),                # partition Y294 (stair | bedroom)
            W(1296, 10, 1308, 288, "int"),                # bedroom / east balcony (DW2)
        ],
        openings=[
            win("W5", (431, w5[0], 451, w5[1]), sill=120, head=210),
            dw("DW1", (431, 30, 451, 335)),
            door("D4", (d4a[0], bath1_s - 6, d4a[1], bath1_s + 6), hinge="end", swing=+1),
            door("D3", (962, 374, 974, 459), hinge="end", swing=-1),
            door("D4", (962, d4b[0], 974, d4b[1]), hinge="end", swing=-1),
            door("D3", (974, 288, 1054, 300), hinge="start", swing=-1),
            win("W8", (1312, 288, 1386, 300), sill=100, head=210),
            dw("DW2", (1296, 80, 1308, 240)),
        ],
        bal_end=bal_end, bath1_s=bath1_s, bath1_e=bath1_e, bath2_w=bath2_w, bath2_n=bath2_n,
    )


F2 = upper("2F", "B7 二層平面圖", 390, bal_end=365, bath1_s=344, bath1_e=765,
           bath2_w=805, bath2_n=244, w5=(379, 479), d4a=(684, 759), d4b=(164, 239))
F3 = upper("3F", "B7 三層平面圖", 710, bal_end=360, bath1_s=374, bath1_e=711,
           bath2_w=791, bath2_n=270, w5=(394, 484), d4a=(630, 705), d4b=(186, 261))

FLOORS = [F1, F2, F3]

# Stair (U-shaped): band1 north (Y404-509), band2 south (Y300-392), centre wall Y392-404,
# landing X1302-1392.  Risers listed as X of each riser nosing line.
BAND1 = (404, 509)
BAND2 = (300, 392)
CENTER = (392, 404)
LANDING_X = (1302, 1392)
FLIGHT_A = [1002 + TREAD * i for i in range(13)]        # 1F -> landing, band1, 13 risers
FLIGHT_B = [1177 + TREAD * i for i in range(6)]         # landing -> 2F, band2, 6 risers
FLIGHT_C = [1102 + TREAD * i for i in range(9)]         # 2F -> landing, band1, 9 risers
FLIGHT_D = [1127 + TREAD * i for i in range(8)]         # landing -> 3F, band2, 8 risers
