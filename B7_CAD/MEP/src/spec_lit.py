"""照明設備配置圖 (bc80426b)"""
from mep_build import region_of
import spec_rec

R, G, B, M, Y, C = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 0.0), (0.0, 1.0, 1.0)
TEXT_KEYS = {M, Y, R}
RESIDUAL_KEYS = {M, R, Y, C}
DROP = [(540, 280, 760, 330), (540, 640, 760, 700), (540, 1020, 760, 1070), (0, 1080, 842, 1191)]
VIEWS = [(60, 690, 760, 1030), (60, 20, 760, 330), (60, 360, 760, 690)]
ZOOM = 2.4
CKT_DIGITS = {742: '1', 744: '6', 746: '7'}


def L(cx, cy, s, rot=0, r=2.5):
    return (cx - r, cy - r, cx + r, cy + r, s, rot)


SW = lambda t: '@L_SW:' + t
TEXTS = [
    (112, 86, 275, 104, 'TO MP-3(1F~3F,景觀)', 0), (112, 455, 275, 473, 'TO MP-3(1F~3F,景觀)', 0),
    (70, 700, 230, 717, 'TO MP-3(1F~3F,景觀)', 0),
    L(616, 170, '3LB7', r=4), L(563, 515, '2LB7', r=4), (495, 758, 530, 772, '1LB7', 0),
    L(439, 59, SW('S'), 90), L(390, 99, SW('SF'), r=3), (535, 108, 546, 130, SW('S3S'), 90), L(607, 134, SW('SS3'), r=3),
    L(599, 150, SW('S3')), L(554, 194, SW('S'), 90), (535, 192, 546, 207, SW('SF'), 90), L(329, 257, SW('SS3'), r=3),
    L(681, 265, SW('S3S'), r=3),
    L(463, 450, SW('S'), 90), L(414, 483, SW('SF'), r=3), (535, 477, 546, 500, SW('S3S'), 90), L(605, 501, SW('S3S3'), r=3),
    L(599, 519, SW('S3')), L(554, 586, SW('S'), 90), (535, 585, 546, 600, SW('SF'), 90), L(329, 626, SW('SS3'), r=3),
    L(681, 634, SW('S3S'), r=3),
    L(541, 805, SW('S3S3'), r=3), L(667, 888, SW('SS'), r=3), (324, 907, 334, 928, SW('SS3'), 90), L(541, 988, SW('SS'), r=3),
]


def templates(page):
    return [
        dict(name='E_PANEL', region=region_of(page, [1097, 1098, 1099, 1100], 0.3), colors={R}, kind='block', rots=(0,)),
        dict(name='L_FAN', region=region_of(page, list(range(721, 729)), 0.3), colors={Y}, kind='block'),
        dict(name='L_FAN', region=region_of(page, [168, 169, 170], 0.3), colors={Y}, kind='block', rots=(0,)),
        dict(name='L_WALL', region=region_of(page, [819, 820], 0.3), colors={C}, kind='block'),
        dict(name='L_STAIR', region=region_of(page, list(range(769, 779)), 0.3), colors={Y}, kind='block'),
        dict(name='L_LIGHT_J', region=region_of(page, [1087], 0.4), colors={Y}, kind='block', rots=(0,), precision=0.5),
        dict(name='L_LIGHT', region=region_of(page, [797], 0.3), colors={Y}, kind='block', rots=(0,)),
        dict(name='E_CKT', region=region_of(page, [742], 0.2), colors={M}, kind='block', rots=(0,), precision=0.0,
             exclude_ids=[p['id'] for p in page.in_region(region_of(page, [742], -1.5), {M})]),
    ]


def post(page, insts):
    insts = spec_rec.post(page, insts, CKT_DIGITS, M)
    return wire_ticks(page, insts)


def wire_ticks(page, insts):
    """group magenta tick strokes crossing a lighting wire -> L_WIRE{n} blocks (導線根數)."""
    import math
    import numpy as np
    ctree = page.trees[C][0]
    ticks = []
    for p in page.paths:
        if p['id'] in page.consumed or p['key'] != M or p['type'] != 'line' or not (3.0 <= p['len'] <= 9.5):
            continue
        a, b = p['P'][0], p['P'][-1]
        mid = (a + b) / 2; d = (b - a) / np.hypot(*(b - a))
        if not ctree.query_ball_point(mid, 1.3):
            continue
        ticks.append(dict(id=p['id'], mid=mid, d=d, len=p['len'], ang=math.degrees(math.atan2(d[1], d[0])) % 180))
    n = len(ticks); parent = list(range(n))
    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            ti, tj = ticks[i], ticks[j]
            da = abs(ti['ang'] - tj['ang']); da = min(da, 180 - da)
            disp = tj['mid'] - ti['mid']
            if da < 8 and abs(ti['len'] - tj['len']) < 1.5 and np.hypot(*disp) < 3.2 and abs(np.dot(disp, ti['d'])) < 1.0:
                parent[f(i)] = f(j)
    groups = {}
    for i in range(n):
        groups.setdefault(f(i), []).append(ticks[i])
    for g in groups.values():
        if len(g) < 2:
            continue
        mid = np.mean([t['mid'] for t in g], axis=0); d = g[0]['d']
        tick_paper = math.degrees(math.atan2(-d[1], d[0]))
        for t in g:
            page.consumed[t['id']] = 'wire'
        insts.append(dict(name=f'L_WIRE{min(len(g), 6)}', kind='block', payload={}, rot=(tick_paper - 90) % 180, at=mid,
                          cons=[t['id'] for t in g], score=(1, 1)))
    return insts
