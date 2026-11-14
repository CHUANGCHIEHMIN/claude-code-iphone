"""插座設備配置圖 (2e7b6ce6)"""
import numpy as np
from scipy.spatial import cKDTree
from mep_build import region_of

R, G, B, M, Y, C = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 0.0), (0.0, 1.0, 1.0)
TEXT_KEYS = {M, G, R, Y, C}
RESIDUAL_KEYS = {M, G, R, Y, C, B}
DROP = [(440, 300, 600, 345), (440, 660, 600, 700), (440, 1020, 600, 1060), (0, 1080, 842, 1191)]
VIEWS = [(20, 760, 700, 1030), (140, 40, 700, 345), (140, 400, 700, 700)]
ZOOM = 2.6
CKT_DIGITS = {805: '2', 807: '3', 812: '5', 814: '6', 809: '4', 816: '7', 1015: '11', 2529: '10', 2525: '8', 1764: '9'}

def L(cx, cy, s, rot=0, r=2.5):
    return (cx - r, cy - r, cx + r, cy + r, s, rot)


TEXTS = [
    (80, 72, 168, 88, '儲熱式電能熱水器', 0), (115, 88, 168, 103, '1φ4KW', 0),
    (80, 434, 168, 450, '儲熱式電能熱水器', 0), (115, 450, 168, 465, '1φ4KW', 0),
    L(517, 194, '3LB7', r=4), L(501, 540, '2LB7', r=4), (400, 764, 440, 778, '1LB7', 0),
    L(201, 755, '動力插座', r=4), (175, 764, 252, 778, '1φ220V 7HP', 0),
    (75, 774, 150, 788, '1φKWHB7', 0), L(105, 798, '電氣系統接地系統', r=4), (112, 807, 148, 821, '同A7戶', 0),
    L(734, 810, '自來水揚水泵', r=4), (700, 816, 815, 830, '1φ220V 0.5HP', 0),
    L(231, 791, 'W'), L(208, 171, 'W', 90), L(607, 261, 'W', 90), L(208, 527, 'W', 90), L(607, 618, 'W', 90),
    L(607, 961, 'W', 90), L(607, 984, 'W', 90),
    L(206, 130, 'A', 270), L(610, 180, 'A', 270), L(206, 488, 'A', 270), L(610, 538, 'A', 270),
    L(649, 830, 'A', 270), L(649, 848, 'A', 270), L(586, 992, 'A'),
    L(323, 97, 'H', 90), L(347, 464, 'H', 90), L(414, 193, 'H'), L(415, 566, 'H'),
    L(491, 159, 'T'), L(491, 516, 'T'), L(438, 800, 'T'),
    L(549, 1003, 'K'), L(587, 1003, 'K'),
]


def templates(page):
    def circ(i, pad=1.6):
        return region_of(page, [i], pad)
    return [
        dict(name='E_PANEL', region=region_of(page, [138, 139, 140, 141], 0.3), colors={R}, kind='block', rots=(0,)),
        dict(name='E_KWH', region=region_of(page, [846], 0.3), colors={R}, kind='block', rots=(0, 90)),
        dict(name='E_GND', region=region_of(page, [970], 0.3), colors={R}, kind='block', rots=(0,)),
        dict(name='E_MOTOR', region=region_of(page, list(range(1118, 1126)), 0.3), colors={G}, kind='block', rots=(0, 90)),
        dict(name='E_HOUT', region=circ(2140, 0.4), colors={G}, kind='block', rots=(0,)),
        dict(name='E_J', region=circ(1083, 0.4), colors={Y}, kind='block', rots=(0,)),
        dict(name='E_J', region=circ(208, 0.4), colors={G}, kind='block', rots=(0,)),
        dict(name='E_RECD', region=circ(1004, 0.4), colors={G}, kind='block'),
        dict(name='E_REC2', region=circ(204), colors={G}, kind='block', rots=(0, 90)),
        dict(name='E_REC1', region=circ(153), colors={G}, kind='block', rots=(0, 90)),
        dict(name='E_CKT', region=circ(805, 0.2), colors={M}, kind='block', rots=(0,), precision=0.0,
             exclude_ids=[p['id'] for p in page.in_region(region_of(page, [805], -1.5), {M})]),
    ]


def _inner(page, c, r, key):
    out = []
    for p in page.paths:
        if p['id'] in page.consumed or p['key'] != key:
            continue
        b = p['bbox']
        if b[0] >= c[0] - r and b[2] <= c[0] + r and b[1] >= c[1] - r and b[3] <= c[1] + r:
            out.append(p)
    return out


def post(page, insts, digits=None, key=M):
    digits = digits or CKT_DIGITS
    ex = {}
    for cid, num in digits.items():
        p = page.paths[cid]; c = np.array([(p['bbox'][0] + p['bbox'][2]) / 2, (p['bbox'][1] + p['bbox'][3]) / 2])
        inn = [q for q in page.paths if q['id'] != cid and q['key'] == key and
               q['bbox'][0] >= c[0] - p['r'] + 1 and q['bbox'][2] <= c[0] + p['r'] - 1 and
               q['bbox'][1] >= c[1] - p['r'] + 1 and q['bbox'][3] <= c[1] + p['r'] - 1]
        ex[num] = np.vstack([q['S'] for q in inn]) - c
    for i in insts:
        if i['name'] != 'E_CKT':
            continue
        c = i['at']; r = 8.0
        inn = _inner(page, c, r, key)
        if not inn:
            continue
        P = np.vstack([q['S'] for q in inn]) - c
        tp = cKDTree(P); best = None
        for num, E in ex.items():
            d1 = cKDTree(E).query(P)[0].mean(); d2 = tp.query(E)[0].mean()
            d = max(d1, d2)
            if best is None or d < best[0]:
                best = (d, num)
        if best[0] < 0.5:
            i['payload'] = dict(num=best[1])
            for q in inn:
                page.consumed[q['id']] = 'ckt'
        else:
            i['payload'] = dict(num='?', dist=float(best[0]))
    return insts
