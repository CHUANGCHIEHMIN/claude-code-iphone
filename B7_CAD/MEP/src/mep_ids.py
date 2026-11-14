import sys
sys.path.insert(0, sys.path[0])
from mep_paths import paths
pdf = sys.argv[1]; x0, y0, x1, y1 = map(float, sys.argv[2:6])
for i, p in enumerate(paths(pdf)):
    b = p['bbox']
    if b[0] >= x0 and b[1] >= y0 and b[2] <= x1 and b[3] <= y1:
        print(i, p['color'], p['fill'], p['type'], len(p['P']), [round(v, 1) for v in b])
