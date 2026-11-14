"""Taiwan-style MEP symbol blocks (units: cm, drawn for 1/100 sheets) + legend metadata."""
import math
from ezdxf.enums import TextEntityAlignment

TXT = 'CHT'
LEGEND = {}   # block -> (名稱, 說明, 系統)


def _c(b, r, x=0, y=0):
    b.add_circle((x, y), r, dxfattribs={'layer': '0'})


def _l(b, a, c):
    b.add_line(a, c, dxfattribs={'layer': '0'})


def _pl(b, pts, close=False):
    b.add_lwpolyline(pts, close=close, dxfattribs={'layer': '0'})


def _t(b, s, h, x=0, y=0, rot=0):
    t = b.add_text(s, height=h, rotation=rot, dxfattribs={'layer': '0', 'style': TXT, 'width': 0.85})
    t.set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)


def _fill(b, pts):
    h = b.add_hatch(dxfattribs={'layer': '0'}); h.set_solid_fill(color=256)
    h.paths.add_polyline_path(pts, is_closed=True)


def _att(b, tag, h, x=0, y=0, default=''):
    a = b.add_attdef(tag, (x, y), dxfattribs={'layer': '0', 'height': h, 'style': TXT, 'width': 0.85})
    a.set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)
    a.dxf.text = default


def define(doc, name, title, note, system):
    b = doc.blocks.new(name)
    LEGEND[name] = (title, note, system)
    return b


def build(doc):
    LEGEND.clear()
    # ---------------- 電力 / 插座
    b = define(doc, 'E_REC1', '單插座', '旁註字母依原圖標示', '插座')
    _c(b, 15); _l(b, (0, -15), (0, 15))
    b = define(doc, 'E_REC2', '雙插座', '旁註W/K/A/T/H依原圖標示', '插座')
    _c(b, 15); _l(b, (-4.5, -14.3), (-4.5, 14.3)); _l(b, (4.5, -14.3), (4.5, 14.3))
    b = define(doc, 'E_RECD', '專用插座', '專用回路', '插座')
    _c(b, 15); _pl(b, [(0, 10), (-8.7, -5), (8.7, -5)], close=True)
    b = define(doc, 'E_HOUT', '電熱水器專用出線口', '容量依註記', '插座')
    _c(b, 26); _t(b, 'H', 20)
    b = define(doc, 'E_J', '接線盒(出線匣)', '', '共用')
    _c(b, 15); _t(b, 'J', 16)
    b = define(doc, 'E_KWH', '電度表(電表箱)', '戶號依註記', '插座')
    _pl(b, [(-17.5, -12.5), (17.5, -12.5), (17.5, 12.5), (-17.5, 12.5)], close=True)
    _l(b, (-17.5, -12.5), (17.5, 12.5)); _l(b, (-17.5, 12.5), (17.5, -12.5))
    b = define(doc, 'E_PANEL', '電燈分電盤', '盤名依註記(如1LB7)', '共用')
    _pl(b, [(-20, -10), (20, -10), (20, 10), (-20, 10)], close=True); _l(b, (-20, 10), (20, -10))
    _fill(b, [(-20, 10), (20, 10), (20, -10)])
    b = define(doc, 'E_GND', '接地', '依原圖註記', '插座')
    _l(b, (0, 15), (0, 0)); _l(b, (-15, 0), (15, 0)); _l(b, (-10, -5), (10, -5)); _l(b, (-5, -10), (5, -10))
    b = define(doc, 'E_MOTOR', '電動機出線口(揚水泵)', '容量依註記', '插座')
    _c(b, 15); _t(b, 'M', 16)
    b = define(doc, 'E_CKT', '迴路編號', '數字為分路編號，箭頭指向分電盤', '共用')
    _c(b, 22.5); _att(b, 'NO', 22, default='1')
    # ---------------- 照明
    b = define(doc, 'L_LIGHT', '燈具出線口(吸頂燈)', '燈具型式依室內設計', '照明')
    _c(b, 10)
    b = define(doc, 'L_LIGHT_J', '接線盒(景觀照明)', '', '照明')
    _c(b, 15); _t(b, 'J', 16)
    b = define(doc, 'L_FAN', '排風機', '', '照明')
    _pl(b, [(-15, -15), (15, -15), (15, 15), (-15, 15)], close=True)
    _pl(b, [(-12, -12), (12, -12), (12, 12), (-12, 12)], close=True); _t(b, 'F', 16)
    b = define(doc, 'L_WALL', '壁燈', '', '照明')
    _c(b, 10); _fill(b, [(0, -10)] + [(10 * math.cos(math.radians(a)), 10 * math.sin(math.radians(a))) for a in range(-90, 91, 15)])
    b = define(doc, 'L_SW', '開關', 'S:單切 S3:三路 SF:排風機，多字為多連', '照明')
    _att(b, 'TYPE', 15, default='S')
    # ---------------- 電信
    b = define(doc, 'T_TC', '電信出線口(TC)', '電話/網路', '電信')
    _c(b, 15); _t(b, 'TC', 11)
    b = define(doc, 'T_TV', '有線電視出線口(TVC)', '', '電信')
    _c(b, 15); _t(b, 'TVC', 8.5)
    b = define(doc, 'T_BOX', '電信箱', '箱名依註記(如DD1B7)', '電信')
    _pl(b, [(-22.5, -5.5), (22.5, -5.5), (22.5, 5.5), (-22.5, 5.5)], close=True); _fill(b, [(-22.5, -5.5), (22.5, -5.5), (22.5, 5.5), (-22.5, 5.5)])
    b = define(doc, 'T_NO', '出線口編號', '', '電信')
    _pl(b, [(-18, -18), (18, -18), (18, 18), (-18, 18)], close=True); _att(b, 'NO', 22, default='1')
    # ---------------- 給水
    b = define(doc, 'P_OUT', '給水栓/器具給水出口', '冷水(CW)藍、熱水(HW)紅', '給水')
    _c(b, 6.5); _l(b, (-6.5, 0), (-18, 0)); _l(b, (-13, -6), (-13, 6))
    b = define(doc, 'P_EH', '儲熱式電能熱水器', '1φ220V 4KW', '給水')
    _c(b, 25); _t(b, 'EH', 18)
    b = define(doc, 'P_HTR', '電熱水器(廚下/小型)', '', '給水')
    _pl(b, [(-12, -15), (12, -15), (12, 15), (-12, 15)], close=True); _t(b, 'H', 16)
    b = define(doc, 'P_GV', '閘閥(GV)', '', '給水')
    _pl(b, [(-10, -7), (10, 7), (10, -7), (-10, 7)], close=True)
    b = define(doc, 'P_CV', '逆止閥(CV)', '', '給水')
    _pl(b, [(-10, -7), (10, 7), (10, -7), (-10, 7)], close=True); _fill(b, [(0, 0), (10, 7), (10, -7)])
    b = define(doc, 'P_WM', '水表(WM)', '', '給水')
    _c(b, 9); _c(b, 4)
    b = define(doc, 'P_PUMP', '加壓/揚水泵', '容量依註記', '給水')
    _c(b, 14); _pl(b, [(-8, -7), (12, 0), (-8, 7)], close=True)
    # ---------------- 排水
    b = define(doc, 'D_FD', '地板落水頭(FD)', '', '排水')
    _pl(b, [(-9, -9), (9, -9), (9, 9), (-9, 9)], close=True); _l(b, (-9, -9), (9, 9)); _l(b, (-9, 9), (9, -9))
    b = define(doc, 'D_CO', '清潔口(CO)', '', '排水')
    _c(b, 12); _l(b, (-12, 0), (12, 0)); _l(b, (0, -12), (0, 12))
    b = define(doc, 'D_ACP', '冷氣排水口(ACP)', '', '排水')
    _c(b, 8); _l(b, (-5.7, -5.7), (5.7, 5.7)); _l(b, (-5.7, 5.7), (5.7, -5.7))
    b = define(doc, 'D_GV', '閘閥(GV)', '', '排水')
    _pl(b, [(-10, -7), (10, 7), (10, -7), (-10, 7)], close=True)
    b = define(doc, 'D_RISER', '排水/通氣/雨水立管', '管別依註記(SP/WP/VP/RP/ACP)', '排水')
    _c(b, 8)
    b = define(doc, 'D_VTR', '通氣管出屋頂(VTR)', '置於頂板', '排水')
    _c(b, 10); _l(b, (-14, 0), (14, 0)); _l(b, (0, -14), (0, 14)); _c(b, 4)
    b = define(doc, 'D_SPOUT', '馬桶排水口', '', '排水')
    _c(b, 7); _l(b, (-4, 0), (4, 0)); _l(b, (0, -4), (0, 4))
    b = define(doc, 'D_MH', '排水陰井', '', '排水')
    _c(b, 19); _c(b, 14)
    b = define(doc, 'D_TRAP', '存水彎(P-TRAP)', '', '排水')
    _pl(b, [(-8, 8), (-8, -4), (0, -8), (8, -4), (8, 8)])
    return LEGEND
