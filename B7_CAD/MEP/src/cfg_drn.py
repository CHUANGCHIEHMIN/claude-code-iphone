"""Output config: 排水設備配置圖"""
R, G, B, M, Y, C = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 0.0), (0.0, 1.0, 1.0)
O, GN, BG = (1.0, 0.5, 0.0), (0.0, 1.0, 0.5), (0.5, 0.62, 1.0)
PDF = '6ec10515-B7__.pdf'
TITLE = '排水設備配置圖'
LAYERS = {'P-排水-汙水SP': (30, 'Continuous'), 'P-排水-雜排水WP': (2, 'Continuous'), 'P-排水-通氣VP': (3, 'Continuous'),
          'P-排水-雨水RP': (4, 'Continuous'), 'P-排水-冷氣ACP': (1, 'Continuous'), 'P-排水-VTR': (3, 'Continuous'),
          'P-排水-套管': (5, 'Continuous')}
BLOCK_NAME = {'D_FD_C': 'D_FD', 'D_FD_Y': 'D_FD', 'D_CO_O1': 'D_CO', 'D_CO_O2': 'D_CO', 'D_CO_Y': 'D_CO'}
BLOCK_ROT = {}
BLOCK_LAYER = {'*': 'P-排水-汙水SP', 'D_ACP': 'P-排水-冷氣ACP', 'D_VTR': 'P-排水-VTR', 'D_FD': 'P-排水-雜排水WP'}
INST_LAYER = {'D_FD_C': 'P-排水-雨水RP', 'D_FD_Y': 'P-排水-雜排水WP', 'D_CO_Y': 'P-排水-雜排水WP', 'D_CO_O1': 'P-排水-汙水SP',
              'D_GV': 'P-排水-汙水SP', 'D_MH': 'P-排水-汙水SP', 'D_SPOUT': 'P-排水-汙水SP'}
TEXT_LAYER = {O: 'P-排水-汙水SP', Y: 'P-排水-雜排水WP', GN: 'P-排水-通氣VP', C: 'P-排水-雨水RP', R: 'P-排水-冷氣ACP',
              G: 'P-排水-VTR', '*': 'P-排水-汙水SP'}
ROUTE_LAYER = {O: 'P-排水-汙水SP', Y: 'P-排水-雜排水WP', GN: 'P-排水-通氣VP', C: 'P-排水-雨水RP', R: 'P-排水-冷氣ACP',
               G: 'P-排水-VTR', BG: 'P-排水-套管'}
DASHED_KEYS = {C: 'DASHDOT', GN: 'DASHED', Y: 'DASHED'}
LEGEND_ORDER = ['D_FD', 'D_CO', 'D_ACP', 'D_SPOUT', 'D_MH', 'D_GV', 'D_VTR']
LINE_LEGEND = [('P-排水-汙水SP', '汙水管(SP)', '管徑依註記', None), ('P-排水-雜排水WP', '雜排水管(WP)', '管徑依註記', None),
               ('P-排水-通氣VP', '通氣管(VP)', '管徑依註記', None), ('P-排水-雨水RP', '雨水管(RP)', '管徑依註記', None),
               ('P-排水-冷氣ACP', '冷氣排水管(ACP)', '管徑依註記', None)]
BANDS = [('3F', -1e9, 345), ('2F', 345, 725), ('1F', 725, 1e9)]
LEGEND_NAME = {'D_FD': ('地板落水頭(FD)', '陽台(雨水)青色、浴室(雜排水)黃色'), 'D_CO': ('清潔口(CO)', '管徑依註記'),
               'D_SPOUT': ('馬桶排水口', '接汙水管SP'), 'D_MH': ('排水陰井', '4"SP FU:20、4"WP FU:35')}
