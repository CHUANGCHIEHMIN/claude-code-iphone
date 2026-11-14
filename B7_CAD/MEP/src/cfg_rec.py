"""Output config: 插座設備配置圖"""
R, G, B, M, Y, C = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 0.0), (0.0, 1.0, 1.0)
PDF = '2e7b6ce6-B7__.pdf'
TITLE = '插座設備配置圖'
LAYERS = {
    'E-插座': (3, 'Continuous'), 'E-插座-分路配線': (5, 'Continuous'), 'E-幹線': (2, 'Continuous'),
    'E-盤箱': (1, 'Continuous'), 'E-迴路編號': (6, 'Continuous'), 'E-註記': (6, 'Continuous'),
    'E-插座-註記': (3, 'Continuous'), 'E-接地': (1, 'Continuous'),
}
BLOCK_NAME = {}
BLOCK_ROT = {}
BLOCK_LAYER = {'*': 'E-插座', 'E_PANEL': 'E-盤箱', 'E_KWH': 'E-盤箱', 'E_GND': 'E-接地', 'E_CKT': 'E-迴路編號',
               'E_J': 'E-幹線'}
TEXT_LAYER = {M: 'E-註記', G: 'E-插座-註記', R: 'E-盤箱', Y: 'E-幹線', '*': 'E-註記'}
ROUTE_LAYER = {B: 'E-插座-分路配線', Y: 'E-幹線', M: 'E-註記', G: 'E-插座', R: 'E-接地', C: 'E-註記'}
DASHED_KEYS = {B: 'HIDDEN', R: 'HIDDEN'}
LEGEND_ORDER = ['E_REC2', 'E_REC1', 'E_RECD', 'E_HOUT', 'E_MOTOR', 'E_J', 'E_PANEL', 'E_KWH', 'E_GND', 'E_CKT']
LINE_LEGEND = [('E-插座-分路配線', '插座分路配線', '線徑/管徑依單線圖', 'HIDDEN'),
               ('E-幹線', '幹線', '電表至分電盤，規格依單線圖', None),
               ('E-接地', '接地線', '接至接地極', 'HIDDEN')]
BANDS = [('3F', -1e9, 360), ('2F', 360, 715), ('1F', 715, 1e9)]
