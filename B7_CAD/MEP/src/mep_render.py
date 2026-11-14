"""Render a sheet DXF to PNGs (full + per-frame) for checking."""
import sys, io, contextlib
import ezdxf, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf import recover
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy, ColorPolicy

src, outp = sys.argv[1], sys.argv[2]
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    doc, _ = recover.readfile(src)
for s in doc.styles:
    s.dxf.font = 'wqy-zenhei.ttc'
# yellow is invisible on white: darken for preview only
for l in doc.layers:
    if l.color == 2: l.color = 40
    if l.color == 4: l.color = 140
    if l.color == 3: l.color = 94
fig = plt.figure(figsize=(26, 4.2)); ax = fig.add_axes([0, 0, 1, 1])
cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.COLOR, lineweight_scaling=0.6)
Frontend(RenderContext(doc), MatplotlibBackend(ax, adjust_figure=False), config=cfg).draw_layout(doc.modelspace(), finalize=True)
ax.set_aspect('equal'); ax.set_xlim(0, 9950); ax.set_ylim(300, 1810)
fig.savefig(outp + '_all.png', dpi=110)
frames = {'1F': (0, 2140), '2F': (2600, 4740), '3F': (5200, 7340), 'LEG': (7800, 9940)}
for k, (x0, x1) in frames.items():
    fig.set_size_inches(16, 11.3); ax.set_position([0, 0, 1, 1])
    ax.set_xlim(x0, x1); ax.set_ylim(300, 1810)
    fig.savefig(f'{outp}_{k}.png', dpi=100)
print('ok')
