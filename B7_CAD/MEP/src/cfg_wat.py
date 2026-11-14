"""Output config: 給水設備配置圖"""
R, G, B, M, Y, C, BG = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 0.0), (0.0, 1.0, 1.0), (0.5, 0.62, 1.0)
PDF = '0eaea1e2-B7__.pdf'
TITLE = '給水設備配置圖'
LAYERS = {'P-給水-冷水': (4, 'Continuous'), 'P-給水-熱水': (1, 'Continuous'), 'P-給水-設備': (4, 'Continuous'),
          'P-給水-水表': (2, 'Continuous'), 'P-給水-註記': (4, 'Continuous'), 'P-給水-熱水註記': (1, 'Continuous'),
          'P-給水-套管': (5, 'Continuous')}
BLOCK_NAME = {'P_OUT_C': 'P_OUT', 'P_OUT_H': 'P_OUT'}
BLOCK_ROT = {}
BLOCK_LAYER = {'*': 'P-給水-設備', 'P_EH': 'P-給水-熱水', 'P_GV': 'P-給水-水表', 'P_WM': 'P-給水-水表'}
INST_LAYER = {'P_OUT_C': 'P-給水-冷水', 'P_OUT_H': 'P-給水-熱水'}
TEXT_LAYER = {C: 'P-給水-註記', R: 'P-給水-熱水註記', Y: 'P-給水-水表', '*': 'P-給水-註記'}
ROUTE_LAYER = {C: 'P-給水-冷水', R: 'P-給水-熱水', Y: 'P-給水-水表', BG: 'P-給水-套管'}
DASHED_KEYS = {C: 'DASHDOT', R: 'DASHDOT'}
LEGEND_ORDER = ['P_OUT', 'P_EH', 'P_HTR', 'P_GV', 'P_WM', 'P_PUMP']
LINE_LEGEND = [('P-給水-冷水', '冷水管(CW)', '管徑依註記', None), ('P-給水-熱水', '熱水管(HW)', '管徑依註記', None),
               ('P-給水-套管', '穿樑/穿版套管', '', None)]
BANDS = [('3F', -1e9, 380), ('2F', 380, 715), ('1F', 715, 1e9)]
LEGEND_NAME = {'P_GV': ('閥件(GV/CV/BV)', '水表組：3/4"CV,WM,BV + 3/4"GV')}
