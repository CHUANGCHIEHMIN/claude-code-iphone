"""Output config: 照明設備配置圖"""
R, G, B, M, Y, C = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 0.0), (0.0, 1.0, 1.0)
PDF = 'bc80426b-B7__.pdf'
TITLE = '照明設備配置圖'
LAYERS = {
    'E-照明': (2, 'Continuous'), 'E-照明-配線': (4, 'Continuous'), 'E-照明-開關': (2, 'Continuous'),
    'E-盤箱': (1, 'Continuous'), 'E-迴路編號': (6, 'Continuous'), 'E-註記': (6, 'Continuous'),
}
BLOCK_NAME = {'L_STAIR': 'L_WALL'}
BLOCK_ROT = {'E_PANEL': 180}
BLOCK_LAYER = {'*': 'E-照明', 'E_PANEL': 'E-盤箱', 'E_CKT': 'E-迴路編號', 'L_SW': 'E-照明-開關'}
TEXT_LAYER = {M: 'E-註記', Y: 'E-照明-開關', R: 'E-盤箱', '*': 'E-註記'}
ROUTE_LAYER = {C: 'E-照明-配線', Y: 'E-照明', M: 'E-註記', R: 'E-盤箱'}
DASHED_KEYS = {}
LEGEND_ORDER = ['L_LIGHT', 'L_WALL', 'L_FAN', 'L_LIGHT_J', 'L_SW', 'E_PANEL', 'E_CKT']
LINE_LEGEND = [('E-照明-配線', '照明分路配線', '短劃數為導線根數，線徑/管徑依單線圖', None)]
BANDS = [('3F', -1e9, 340), ('2F', 340, 690), ('1F', 690, 1e9)]
