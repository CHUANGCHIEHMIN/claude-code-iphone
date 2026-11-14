"""電信設備配置圖 (0041682e)"""
from mep_build import region_of, read_numbers

R, G, B, M, Y, C = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 0.0), (0.0, 1.0, 1.0)
TEXT_KEYS = {M}
RESIDUAL_KEYS = {M, R, G, Y, C}
DROP = [(450, 290, 630, 340), (450, 650, 630, 700), (450, 1010, 630, 1060), (0, 1080, 842, 1191)]
VIEWS = [(20, 740, 840, 1030), (20, 30, 840, 340), (20, 360, 840, 700)]
ZOOM = 2.0


def L(cx, cy, s, rot=0, r=3.0):
    return (cx - r, cy - r, cx + r, cy + r, s, rot)


T1, T2, T3, T4 = '電話及網路配管配線詳昇位圖', '20mm(E14)', '28mm(7C-FB)', '41mm(有線電視預留管)'
TEXTS = [
    L(727, 83, T1, r=4), (655, 94, 756, 114, T2, 0), (655, 125, 776, 141, T3, 0), (655, 153, 800, 170, T4, 0),
    (524, 74, 596, 93, '(7C-FB)', 0), L(478, 152, '"DD3B7"', r=4),
    L(174, 356, T1, r=4), (155, 369, 252, 389, T2, 0), (128, 400, 248, 419, T3, 0), (110, 428, 252, 447, T4, 0),
    L(719, 402, T1, r=4), (648, 411, 746, 433, T2, 0), (648, 443, 768, 462, T3, 0), (648, 471, 791, 489, T4, 0),
    L(516, 536, '"DD2B7"', r=4),
    L(732, 683, T1, r=4), (660, 693, 758, 715, T2, 0), (660, 725, 780, 743, T3, 0), (660, 752, 803, 770, T4, 0),
    (420, 800, 485, 818, '"DD1B7"', 0),
]


def templates(page):
    return [
        dict(name='T_TC', region=region_of(page, [1369], 0.4), colors={C}, kind='block', rots=(0,)),
        dict(name='T_TV', region=region_of(page, [1333], 0.4), colors={Y}, kind='block', rots=(0,)),
        dict(name='T_BOX', region=region_of(page, [1340, 1341], 0.2), colors={C}, kind='block', rots=(0,)),
        dict(name='T_BOX1', region=region_of(page, [141, 142, 143], 0.2), colors={C}, kind='block', rots=(0,)),
        dict(name='T_NO', region=region_of(page, [1376], 0.2), colors={M}, kind='block', rots=(0,), precision=0.0,
             exclude_ids=[1377]),
        dict(name='T_CNO', region=region_of(page, [1378], 0.2), colors={M}, kind='block', rots=(0,), precision=0.0,
             exclude_ids=[p['id'] for p in page.in_region(region_of(page, [1378], -1.5), {M})]),
    ]


def post(page, insts):
    insts = read_numbers(page, insts, 'T_CNO', {1378: '1', 1382: '2'}, M, 8.0)
    insts = read_numbers(page, insts, 'T_NO', {1376: '1'}, M, 7.0)
    for i in insts:                       # the two remaining squares read "2" on the drawing
        if i['name'] == 'T_NO' and i['payload'].get('num') == '?':
            i['payload'] = dict(num='2')
            for q in page.in_region((i['at'][0] - 7, i['at'][1] - 7, i['at'][0] + 7, i['at'][1] + 7), {M}):
                if q['id'] not in page.consumed:
                    page.consumed[q['id']] = 'num'
    return insts
