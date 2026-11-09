import sys
import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy, ColorPolicy

src, outdir = sys.argv[1], sys.argv[2]
doc = ezdxf.readfile(src)
doc.styles.get("CHT").dxf.font = "wqy-zenhei.ttc"
doc.styles.get("DIMTXT").dxf.font = "DejaVuSans.ttf"
msp = doc.modelspace()
# preview-only recolour for white paper (DXF keeps standard CAD colours)
for name, col in {"A-ANNO-TAG": 30, "A-STAIR": 30, "A-WIND": 5, "A-WALL-LOW": 5,
                  "A-DOOR": 94, "A-FIXT": 6, "A-ANNO-TEXT": 7, "A-SITE": 8}.items():
    doc.layers.get(name).color = col

cfg = Configuration(background_policy=BackgroundPolicy.WHITE,
                    color_policy=ColorPolicy.COLOR, lineweight_scaling=1.2,
                    min_lineweight=0.12)
fig = plt.figure(figsize=(16.54, 11.69))  # A3 landscape
ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
ctx = RenderContext(doc)
Frontend(ctx, MatplotlibBackend(ax, adjust_figure=False), config=cfg).draw_layout(msp, finalize=True)

ax.set_aspect("equal", adjustable="box")
views = {
    "1F": (-140, 1720, -440, 820),
    "2F": (1900 + 200, 1900 + 1720, -200, 820),
    "3F": (3700 + 200, 3700 + 1720, -200, 820),
}
with PdfPages(f"{outdir}/B7_plans_preview.pdf") as pdf:
    for fl, (x0, x1, y0, y1) in views.items():
        w, h = x1 - x0, y1 - y0
        # keep A3 aspect
        target = 16.54 * 0.96 / (11.69 * 0.96)
        if w / h < target:
            pad = (h * target - w) / 2; x0 -= pad; x1 += pad
        else:
            pad = (w / target - h) / 2; y0 -= pad; y1 += pad
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
        fig.savefig(f"{outdir}/B7_{fl}_preview.png", dpi=200)
        pdf.savefig(fig)
    fig.set_size_inches(24, 6.2); ax.set_position([0.01, 0.01, 0.98, 0.98])
    ax.set_xlim(-200, 5500); ax.set_ylim(-400, 1080)
    fig.savefig(f"{outdir}/B7_all_preview.png", dpi=120)
print("ok")
