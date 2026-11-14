"""Output config: 電信設備配置圖"""
R, G, B, M, Y, C = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 0.0), (0.0, 1.0, 1.0)
PDF = '0041682e-B7__.pdf'
TITLE = '電信設備配置圖'
LAYERS = {'T-電信': (4, 'Continuous'), 'T-有線電視': (2, 'Continuous'), 'T-配管-電話網路': (3, 'Continuous'),
          'T-配管-有線電視': (1, 'Continuous'), 'T-電信箱': (4, 'Continuous'), 'T-註記': (6, 'Continuous')}
BLOCK_NAME = {'T_BOX1': 'T_BOX', 'T_CNO': 'E_CKT'}
BLOCK_ROT = {}
BLOCK_LAYER = {'*': 'T-電信', 'T_TV': 'T-有線電視', 'T_BOX': 'T-電信箱', 'T_NO': 'T-註記', 'E_CKT': 'T-註記'}
TEXT_LAYER = {M: 'T-註記', '*': 'T-註記'}
ROUTE_LAYER = {G: 'T-配管-電話網路', R: 'T-配管-有線電視', C: 'T-電信', Y: 'T-有線電視', M: 'T-註記'}
DASHED_KEYS = {}
LEGEND_ORDER = ['T_TC', 'T_TV', 'T_BOX', 'E_CKT', 'T_NO']
LINE_LEGEND = [('T-配管-電話網路', '電話/網路配管', '20mm(E14)、28mm(7C-FB)，詳昇位圖', None),
               ('T-配管-有線電視', '有線電視配管', '41mm 有線電視預留管，詳昇位圖', None)]
BANDS = [('3F', -1e9, 345), ('2F', 345, 675), ('1F', 675, 1e9)]
LEGEND_NAME = {'E_CKT': ('出線口編號(圓)', '電信出線口編號'), 'T_NO': ('出線口編號(方)', '有線電視出線口編號')}
