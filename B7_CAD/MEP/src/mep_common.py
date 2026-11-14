"""Shared helpers: base DWG geometry, PDF vector extraction, registration."""
import io, contextlib, json, math
import numpy as np
import ezdxf
from ezdxf import recover, path as ezpath
import pymupdf as fitz

FLOOR_ORIGIN = {"1F": (635.4, 777.0), "2F": (3235.4, 777.0), "3F": (5835.4, 777.0)}
FRAME_X = {"1F": (19, 2119), "2F": (2619, 4719), "3F": (5219, 7319)}


def load_base(path):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        doc, _ = recover.readfile(path)
    return doc


def _segments_of(entity, out, depth=0):
    t = entity.dxftype()
    if t in ("INSERT",):
        try:
            for ve in entity.virtual_entities():
                _segments_of(ve, out, depth + 1)
        except Exception:
            pass
        return
    if t in ("TEXT", "MTEXT", "HATCH", "DIMENSION", "ATTDEF", "ATTRIB", "POINT"):
        return
    if t == "MLINE":
        try:
            for ve in entity.virtual_entities():
                _segments_of(ve, out, depth + 1)
        except Exception:
            pass
        return
    try:
        p = ezpath.make_path(entity)
    except Exception:
        return
    pts = list(p.flattening(1.0))
    for a, b in zip(pts, pts[1:]):
        out.append((a.x, a.y, b.x, b.y))


def base_segments(doc, floor):
    """line segments of the base plan for one floor, in floor-local coords (cm)."""
    x0, x1 = FRAME_X[floor]
    ox, oy = FLOOR_ORIGIN[floor]
    segs = []
    for e in doc.modelspace():
        if e.dxftype() in ("TEXT", "DIMENSION", "MTEXT"):
            continue
        if e.dxf.layer in ("Defpoints", "46_文字", "50_其他尺寸"):
            continue
        tmp = []
        _segments_of(e, tmp)
        for s in tmp:
            if x0 <= s[0] <= x1 and x0 <= s[2] <= x1:
                segs.append((s[0] - ox, s[1] - oy, s[2] - ox, s[3] - oy))
    return np.array(segs, dtype=float)


def pdf_items(pdf_path):
    """all vector items: list of dict(color, fill, width, kind, pts)."""
    p = fitz.open(pdf_path)[0]
    items = []
    for d in p.get_drawings():
        col = d.get("color"); fill = d.get("fill")
        key = None if col is None else tuple(round(x, 2) for x in col)
        fkey = None if fill is None else tuple(round(x, 2) for x in fill)
        for it in d["items"]:
            k = it[0]
            if k == "l":
                pts = [(it[1].x, it[1].y), (it[2].x, it[2].y)]
            elif k == "c":
                pts = [(q.x, q.y) for q in (it[1], it[2], it[3], it[4])]
            elif k == "re":
                r = it[1]; pts = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)]
            elif k == "qu":
                q = it[1]; pts = [(v.x, v.y) for v in (q.ul, q.ur, q.lr, q.ll, q.ul)]
            else:
                continue
            items.append(dict(color=key, fill=fkey, width=d.get("width") or 0, kind=k, pts=pts,
                              closed=bool(d.get("closePath")), seqno=d.get("seqno")))
    return items


def bezier(pts, n=8):
    p0, p1, p2, p3 = [np.array(p) for p in pts]
    t = np.linspace(0, 1, n)[:, None]
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t * t * p2 + (t ** 3) * p3


def item_polyline(it):
    if it["kind"] == "c":
        return [tuple(v) for v in bezier(it["pts"])]
    return it["pts"]


def apply_T(T, pts):
    s, tx, ty = T
    return [(s * x + tx, -s * y + ty) for x, y in pts]
