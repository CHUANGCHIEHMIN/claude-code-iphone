"""B7 3D model builder + exporters (GLB, OBJ, DAE, 3D-DXF, IFC, USDZ).
Model units: cm, Z up, X east, Y north (same as the plan DXF)."""
import sys, os, math, json
import numpy as np
import trimesh
from shapely.geometry import box, Polygon
from shapely.ops import unary_union

sys.path.insert(0, sys.argv[1])
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)
from b7_model import (F1, F2, F3, FLOORS, COLUMNS, BEAMS, WINGS, BAND1, BAND2, CENTER, LANDING_X,
                      WINDER_X, FLIGHT_A, FLIGHT_B, FLIGHT_C, FLIGHT_D, H)

SLAB_T = 15.0
LV = {"1F": 30.0, "2F": 390.0, "3F": 710.0, "RF": 1030.0}
NEXT = {"1F": "2F", "2F": "3F", "3F": "RF"}
PARAPET_H = 140.0
R1, R2 = 360 / 19, 320 / 17          # riser heights 18.95 / 18.82
BEAM_D = 60.0

MAT = {  # name: RGBA 0-255
    "wall": (238, 235, 228, 255), "parapet": (228, 224, 216, 255), "slab": (196, 196, 196, 255),
    "column": (150, 150, 152, 255), "beam": (172, 172, 175, 255), "stair": (198, 172, 132, 255),
    "glass": (150, 195, 225, 90), "door": (140, 96, 58, 255), "fixture": (250, 250, 250, 255),
    "counter": (212, 206, 196, 255), "deco": (92, 92, 96, 255), "ground": (160, 168, 150, 255),
    "paving": (135, 135, 135, 255), "fence": (205, 198, 186, 255), "rail": (80, 80, 80, 255),
}
IFC_CLASS = {"wall": "IfcWall", "parapet": "IfcWall", "slab": "IfcSlab", "column": "IfcColumn",
             "beam": "IfcBeam", "stair": "IfcStairFlight", "glass": "IfcWindow", "door": "IfcDoor",
             "fixture": "IfcSanitaryTerminal", "counter": "IfcFurniture", "deco": "IfcCovering",
             "ground": "IfcGeographicElement", "paving": "IfcSlab", "fence": "IfcWall", "rail": "IfcRailing"}

parts = []   # dict(name, storey, cat, mesh)


def add(name, storey, cat, mesh):
    if mesh is not None and len(mesh.faces):
        parts.append(dict(name=name, storey=storey, cat=cat, mesh=mesh))


def bx(x0, y0, x1, y1, z0, z1):
    if x1 - x0 <= 1e-6 or y1 - y0 <= 1e-6 or z1 - z0 <= 1e-6:
        return None
    return trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0],
                                transform=trimesh.transformations.translation_matrix(
                                    [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]))


def ext(geom, z0, z1):
    if geom is None or geom.is_empty or z1 - z0 <= 1e-6:
        return None
    ms = []
    for p in getattr(geom, "geoms", [geom]):
        if p.geom_type != "Polygon" or p.area < 1e-3:
            continue
        m = trimesh.creation.extrude_polygon(p.buffer(0), z1 - z0)
        m.apply_translation([0, 0, z0])
        ms.append(m)
    return trimesh.util.concatenate(ms) if ms else None


def cat(ms):
    ms = [m for m in ms if m is not None]
    return trimesh.util.concatenate(ms) if ms else None


# ------------------------------------------------------------------ floors
def outline(fl):
    if fl == "1F":
        return unary_union([box(452.5, -7.5, 1399.5, 516.5), box(452.5, 516.5, 975.5, 541.5)])
    return unary_union([box(303.5, -7.5, 1399.5, 516.5), box(303.5, 516.5, 975.5, 541.5),
                        box(1392.5, -7.5, 1407.5, 294)])


STAIR_HOLE = {
    "2F": unary_union([box(1102, BAND1[0], 1384.5, BAND1[1]), box(1177, BAND2[0], 1384.5, BAND2[1]),
                       box(1302, BAND2[0], 1384.5, BAND1[1])]),
    "3F": unary_union([box(1102, BAND1[0], 1384.5, BAND1[1]), box(1127, BAND2[0], 1384.5, BAND2[1]),
                       box(1302, BAND2[0], 1384.5, BAND1[1])]),
}

COLFOOT = unary_union([box(*c) for c in COLUMNS.values()])
BEAMFOOT = unary_union([box(*b) for b in BEAMS.values()])
BEAM_D_ = 60.0

# slabs (column footprints removed so faces never overlap)
add("1F_Slab", "1F", "slab", ext(outline("1F").difference(COLFOOT), 0, LV["1F"]))
for fl in ("2F", "3F"):
    add(f"{fl}_Slab", fl, "slab", ext(outline(fl).difference(STAIR_HOLE[fl]).difference(COLFOOT), LV[fl] - SLAB_T, LV[fl]))
roof = unary_union([box(303.5, -7.5, 1407.5, 516.5), box(303.5, 516.5, 975.5, 541.5)])
add("RF_Slab", "RF", "slab", ext(roof.difference(COLFOOT), LV["RF"] - SLAB_T, LV["RF"]))

# roof parapet (15 cm, top RFL+140)
rp = unary_union([box(303.5, -7.5, 318.5, 541.5), box(303.5, 526.5, 975.5, 541.5),
                  box(960.5, 501.5, 975.5, 541.5), box(960.5, 501.5, 1407.5, 516.5),
                  box(1392.5, -7.5, 1407.5, 516.5), box(303.5, -7.5, 1407.5, 7.5)])
add("RF_Parapet", "RF", "parapet", ext(rp, LV["RF"], LV["RF"] + PARAPET_H))

# walls with openings; height-limited zones where 1F toilet walls run under the stair
LIMITS = {"1F": [(box(1219.5, 409.5, 1232.5, 516.5), 138.0),      # under flight A
                 (box(1219.5, 286.5, 1232.5, 409.5), 280.0)]}     # under flight B


def opening_axes(o):
    x0, y0, x1, y1 = o["rect"]
    if (x1 - x0) < (y1 - y0):
        return "V", (y0, y1), (x0, x1)
    return "H", (x0, x1), (y0, y1)


def rect_xy(orient, s0, s1, f0, f1):
    return (f0, s0, f1, s1) if orient == "V" else (s0, f0, s1, f1)


ifc_walls = []   # per-rect walls for IFC: (name, storey, cls, mesh)
ifc_open = []    # per-opening doors / windows for IFC

for F in FLOORS:
    fl = F["name"]
    z0, z1 = LV[fl], LV[NEXT[fl]] - SLAB_T
    holes = unary_union([box(*o["rect"]) for o in F["openings"]])
    full_rects = [w for w in F["walls"] if w["kind"] != "low"]
    low_rects = [w for w in F["walls"] if w["kind"] == "low"]
    full = unary_union([box(*w["rect"]) for w in full_rects]).difference(holes).difference(COLFOOT)
    zb = LV[NEXT[fl]] - BEAM_D_                         # beam soffit above this floor
    limited = unary_union([g for g, _ in LIMITS.get(fl, [])]) if fl in LIMITS else None
    free = full.difference(limited) if limited is not None else full
    ms = [ext(free.difference(BEAMFOOT), z0, z1), ext(free.intersection(BEAMFOOT), z0, zb)]
    for g, hmax in LIMITS.get(fl, []):
        ms.append(ext(full.intersection(g), z0, z0 + hmax))
    # infill above heads / below sills
    for o in F["openings"]:
        x0, y0, x1, y1 = o["rect"]
        if o["sill"] > 0:
            ms.append(bx(x0, y0, x1, y1, z0, z0 + o["sill"]))
        top = zb if box(*o["rect"]).intersection(BEAMFOOT).area > 1 else z1
        for g, hmax in LIMITS.get(fl, []):
            if g.intersects(box(*o["rect"])):
                top = min(top, z0 + hmax)
        if z0 + o["head"] < top:
            ms.append(bx(x0, y0, x1, y1, z0 + o["head"], top))
    add(f"{fl}_Walls", fl, "wall", cat(ms))
    low = unary_union([box(*w["rect"]) for w in low_rects]).difference(
        unary_union([box(*w["rect"]) for w in full_rects])).difference(COLFOOT)
    add(f"{fl}_Parapets", fl, "parapet", ext(low, z0, z0 + 110))
    # IFC: one element per wall rectangle (openings cut, infills attached to host)
    for i, w in enumerate(F["walls"]):
        g = box(*w["rect"]).difference(holes)
        hh = 110 if w["kind"] == "low" else z1 - z0
        wm = [ext(g, z0, z0 + hh)]
        for o in F["openings"]:
            if box(*w["rect"]).contains(box(*o["rect"]).buffer(-0.1)):
                x0, y0, x1, y1 = o["rect"]
                if o["sill"] > 0:
                    wm.append(bx(x0, y0, x1, y1, z0, z0 + o["sill"]))
                if z0 + o["head"] < z1:
                    wm.append(bx(x0, y0, x1, y1, z0 + o["head"], z1))
        ifc_walls.append((f"{fl}_Wall_{i + 1:02d}", fl, "parapet" if w["kind"] == "low" else "wall", cat(wm)))

    # glass / doors
    glass, doors = [], []
    for o in F["openings"]:
        orient, (s0, s1), (f0, f1) = opening_axes(o)
        c = (f0 + f1) / 2
        n0 = len(glass) + len(doors)
        if o["type"] == "window":
            glass.append(bx(*rect_xy(orient, s0, s1, c - 1, c + 1), z0 + o["sill"], z0 + o["head"]))
        elif o["type"] == "dw":
            m = (s0 + s1) / 2
            glass.append(bx(*rect_xy(orient, s0, m + 5, c - 3, c - 1), z0, z0 + o["head"]))
            glass.append(bx(*rect_xy(orient, m - 5, s1, c + 1, c + 3), z0, z0 + o["head"]))
        else:
            w = s1 - s0
            sw = o["swing"]
            face = f1 if sw > 0 else f0
            hs = s0 if o["hinge"] == "start" else s1
            a, b = (hs, hs + 4) if o["hinge"] == "start" else (hs - 4, hs)
            lo, hi = sorted((face, face + sw * w))
            doors.append(bx(*rect_xy(orient, a, b, lo, hi), z0, z0 + o["head"]))
        if o["type"] == "door":
            ifc_open.append((f"{fl}_{o['tag']}_{len(ifc_open) + 1:02d}", fl, "door", doors[-1]))
        else:
            ifc_open.append((f"{fl}_{o['tag']}_{len(ifc_open) + 1:02d}", fl, "glass",
                             cat(glass[-2:] if o["type"] == "dw" else glass[-1:])))
    add(f"{fl}_Glass", fl, "glass", cat(glass))
    add(f"{fl}_Doors", fl, "door", cat(doors))

# wings at 1F already in F1 walls; decorative louvers on 2F/3F
for F in (F2, F3):
    fl, be = F["name"], F["bal_end"]
    z0, z1 = LV[fl], LV[NEXT[fl]] - SLAB_T
    fins, y = [], be + 15
    while y < 508:
        fins.append(bx(331, y - 1.5, 344.5, y + 1.5, z0, z1)); y += 8
    add(f"{fl}_Louver", fl, "deco", cat(fins))

# ------------------------------------------------------------------ structure
for name, (x0, y0, x1, y1) in COLUMNS.items():
    for fl, za, zb in (("1F", 0, LV["2F"]), ("2F", LV["2F"], LV["3F"]), ("3F", LV["3F"], LV["RF"])):
        add(f"Column_{name}_{fl}", fl, "column", bx(x0, y0, x1, y1, za, zb))
for lvl in ("2F", "3F", "RF"):
    top = LV[lvl]
    for name, (x0, y0, x1, y1) in BEAMS.items():
        add(f"Beam_{name}_{lvl}", lvl, "beam", bx(x0, y0, x1, y1, top - BEAM_D, top - SLAB_T))

# ------------------------------------------------------------------ stairs
def step(poly, top, riser, base):
    return ext(poly, max(base, top - riser - 12), top)


def flight_rect(xa, xb, band):
    return box(min(xa, xb), band[0], max(xa, xb), band[1])


z = LV["1F"]
A = []
wx0, wx1 = WINDER_X
b2s = COLUMNS["B2"][1]
A.append(step(Polygon([(wx0, CENTER[0]), (wx1, CENTER[0]), (wx1, CENTER[1]), (wx0, b2s)]), z + R1, R1, z))
A.append(step(Polygon([(wx0, b2s), (wx1, CENTER[1]), (wx1, BAND1[1]), (COLUMNS["B2"][2], BAND1[1]),
                       (COLUMNS["B2"][2], b2s)]), z + 2 * R1, R1, z))
for k in range(3, 13):
    A.append(step(flight_rect(FLIGHT_A[k - 3], FLIGHT_A[k - 2], BAND1), z + k * R1, R1, z))
add("1F_Stair_FlightA", "1F", "stair", cat(A))
add("1F_Stair_Landing", "1F", "stair", bx(LANDING_X[0], BAND2[0], LANDING_X[1], BAND1[1],
                                          z + 13 * R1 - SLAB_T, z + 13 * R1))
B = [step(flight_rect(FLIGHT_B[18 - k], FLIGHT_B[19 - k], BAND2), z + k * R1, R1, z) for k in range(14, 19)]
add("1F_Stair_FlightB", "1F", "stair", cat(B))
add("1F_Stair_CentreWall", "1F", "wall", bx(wx1, CENTER[0], 1217.5, CENTER[1], z, LV["2F"] - SLAB_T))

z = LV["2F"]
C = [step(flight_rect(FLIGHT_C[k - 1], FLIGHT_C[k], BAND1), z + k * R2, R2, z) for k in range(1, 9)]
add("2F_Stair_FlightC", "2F", "stair", cat(C))
add("2F_Stair_Landing", "2F", "stair", bx(LANDING_X[0], BAND2[0], LANDING_X[1], BAND1[1],
                                          z + 9 * R2 - SLAB_T, z + 9 * R2))
D = [step(flight_rect(FLIGHT_D[16 - k], FLIGHT_D[17 - k], BAND2), z + k * R2, R2, z) for k in range(10, 17)]
add("2F_Stair_FlightD", "2F", "stair", cat(D))
for fl in ("2F", "3F"):
    add(f"{fl}_Stair_CentreWall", fl, "wall",
        bx(1095, CENTER[0], LANDING_X[0], CENTER[1], LV[fl], LV[NEXT[fl]] - SLAB_T))
add("3F_Stair_Guard", "3F", "rail", bx(FLIGHT_C[0] - 6, BAND1[0], FLIGHT_C[0], BAND1[1], LV["3F"], LV["3F"] + 110))

# ------------------------------------------------------------------ fixtures (simple blocks)
def wc(tank, bowl, fl, horizontal=False):
    z = LV[fl]
    t = bx(*tank, z, z + 80)
    cyl = trimesh.creation.cylinder(radius=18, height=40, sections=24)
    cyl.apply_translation([bowl[0], bowl[1], z + 20])
    return cat([t, cyl])


fx = {"1F": [], "2F": [], "3F": []}
ct = {"1F": [], "2F": [], "3F": []}
z = LV["1F"]
ct["1F"] += [bx(1000, 15, 1070, 88, z, z + 180), bx(1073, 7.5, 1294.5, 68, z, z + 85)]
fx["1F"] += [wc((1308, 481.5, 1358, 501.5), (1333, 458), "1F"), bx(1340, 326, 1384.5, 382, z, z + 80)]
for F in (F2, F3):
    fl = F["name"]; z = LV[fl]; bw, bn, b1e = F["bath2_w"], F["bath2_n"], F["bath1_e"]
    fx[fl] += [bx(bw + 7.5, bn - 55, bw + 50, bn - 7.5, z, z + 80),
               wc((bw + 7.5, bn - 125, bw + 27.5, bn - 75), (bw + 51, bn - 100), fl)]
    if fl == "2F":
        fx[fl] += [bx(449, 348, 519, 505, z, z + 55), wc((615, 506.5, 665, 526.5), (640, 482), fl),
                   bx(690, 472, b1e - 7.5, 526.5, z, z + 80)]
    else:
        fx[fl] += [wc((570, 506.5, 620, 526.5), (595, 482), fl), bx(630, 476, b1e - 7.5, 526.5, z, z + 80)]
for fl in fx:
    add(f"{fl}_Sanitary", fl, "fixture", cat(fx[fl]))
    add(f"{fl}_Kitchen", fl, "counter", cat(ct[fl]))

# ------------------------------------------------------------------ site
add("Site_Ground", "GL", "ground", bx(-200, -150, 1650, 640, -3, 0))
add("Site_Parking", "GL", "paving", bx(0, 7.5, 452.5, 526.5, 0, 2))
k = 0.052
fence_n = Polygon([(0, 615), (460, 615 - k * 460), (460, 541.5), (444, 541.5), (444, 615 - k * 444 - 16), (0, 599)])
add("Site_Fence", "GL", "fence", cat([ext(fence_n, 0, 200), bx(1484, 0, 1500, 517, 0, 200)]))

print("parts:", len(parts), " triangles:", sum(len(p["mesh"].faces) for p in parts))
if False: json.dump({"parts": [(p["name"], p["storey"], p["cat"], len(p["mesh"].faces)) for p in parts]},
          open(os.path.join(OUT, "_parts.json"), "w"), ensure_ascii=False, indent=0)

# ================================================================== EXPORTS
Y_UP = np.array([[0.01, 0, 0, 0], [0, 0, 0.01, 0], [0, -0.01, 0, 0], [0, 0, 0, 1]])  # cm Z-up -> m Y-up


def flat(m):
    m = m.copy(); m.unmerge_vertices(); return m


def pbr(c):
    r, g, b, a = c
    return trimesh.visual.material.PBRMaterial(
        name=None, baseColorFactor=[r, g, b, a], metallicFactor=0.0, roughnessFactor=0.85,
        alphaMode="BLEND" if a < 255 else "OPAQUE", doubleSided=a < 255)


# merge per (storey, category) for viewer formats
groups = {}
for p in parts:
    groups.setdefault((p["storey"], p["cat"]), []).append(p["mesh"])
scene = trimesh.Scene()
for (st, c), ms in sorted(groups.items()):
    m = flat(trimesh.util.concatenate(ms))
    m.apply_transform(Y_UP)
    mat = pbr(MAT[c]); mat.name = c
    m.visual = trimesh.visual.TextureVisuals(material=mat)
    scene.add_geometry(m, node_name=f"{st}_{c}", geom_name=f"{st}_{c}")
scene.export(os.path.join(OUT, "B7_model.glb"))
print("glb ok")

# OBJ (+MTL), meters, Y up -- own writer (one material per category)
with open(os.path.join(OUT, "B7_model.mtl"), "w") as fm:
    for c, (r, g, b, a) in MAT.items():
        fm.write(f"newmtl {c}\nKa {r/255:.4f} {g/255:.4f} {b/255:.4f}\nKd {r/255:.4f} {g/255:.4f} {b/255:.4f}\n"
                 f"Ks 0.05 0.05 0.05\nNs 10\nd {a/255:.3f}\nillum 2\n\n")
with open(os.path.join(OUT, "B7_model.obj"), "w") as fo:
    fo.write("# B7 model, units: meters, Y up\nmtllib B7_model.mtl\n")
    vo = no = 0
    for (st, c), ms in sorted(groups.items()):
        m = flat(trimesh.util.concatenate(ms)); m.apply_transform(Y_UP)
        fo.write(f"o {st}_{c}\nusemtl {c}\n")
        fo.write("".join(f"v {x:.4f} {y:.4f} {z:.4f}\n" for x, y, z in m.vertices))
        fo.write("".join(f"vn {x:.4f} {y:.4f} {z:.4f}\n" for x, y, z in m.face_normals))
        fo.write("".join(f"f {vo+t[0]+1}//{no+i+1} {vo+t[1]+1}//{no+i+1} {vo+t[2]+1}//{no+i+1}\n"
                         for i, t in enumerate(m.faces)))
        vo += len(m.vertices); no += len(m.faces)
print("obj ok")

# Collada for SketchUp: meters, Z up, colours per category
import collada
from collada import source, geometry, material, scene as cscene, asset
col = collada.Collada()
col.assetInfo.upaxis = asset.UP_AXIS.Z_UP
col.assetInfo.unitmeter = 1.0
col.assetInfo.unitname = "meter"
cmats = {}
for c, (r, g, b, a) in MAT.items():
    eff = material.Effect(f"eff_{c}", [], "lambert", diffuse=(r / 255, g / 255, b / 255, 1.0),
                          transparent=(1.0, 1.0, 1.0, 1.0), transparency=a / 255, double_sided=a < 255)
    mt = material.Material(f"mat_{c}", c, eff)
    col.effects.append(eff); col.materials.append(mt); cmats[c] = mt
nodes = []
for (st, c), ms in sorted(groups.items()):
    nm = f"{st}_{c}"
    m = flat(trimesh.util.concatenate(ms)); m.apply_scale(0.01)          # cm -> m, keep Z up
    vs = source.FloatSource(f"{nm}-v", np.asarray(m.vertices, dtype=float).flatten(), ("X", "Y", "Z"))
    ns = source.FloatSource(f"{nm}-n", np.asarray(m.face_normals, dtype=float).flatten(), ("X", "Y", "Z"))
    geo = geometry.Geometry(col, f"geo_{nm}", nm, [vs, ns])
    il = source.InputList(); il.addInput(0, "VERTEX", f"#{nm}-v"); il.addInput(1, "NORMAL", f"#{nm}-n")
    nidx = np.repeat(np.arange(len(m.faces)), 3)
    idx = np.column_stack([m.faces.flatten(), nidx]).flatten()
    geo.primitives.append(geo.createTriangleSet(idx, il, f"ref_{c}"))
    col.geometries.append(geo)
    nodes.append(cscene.Node(nm, children=[cscene.GeometryNode(geo, [cscene.MaterialNode(f"ref_{c}", cmats[c], inputs=[])])]))
sc = cscene.Scene("B7", nodes); col.scenes.append(sc); col.scene = sc
col.write(os.path.join(OUT, "B7_model.dae"))
print("dae ok")

# ------------------------------------------------------------------ 3D DXF (cm, Z up)
import ezdxf
ddoc = ezdxf.new("R2010", setup=True)
ddoc.header["$INSUNITS"] = 5
ACI = {"wall": 7, "parapet": 9, "slab": 8, "column": 252, "beam": 251, "stair": 42, "glass": 4,
       "door": 32, "fixture": 6, "counter": 6, "deco": 250, "ground": 82, "paving": 8, "fence": 9, "rail": 250}
dmsp = ddoc.modelspace()
for (st, c), ms in sorted(groups.items()):
    lay = f"3D-{c.upper()}"
    if lay not in ddoc.layers:
        ddoc.layers.add(lay, color=ACI[c])
    m = trimesh.util.concatenate(ms); m.merge_vertices()
    e = dmsp.add_mesh(dxfattribs={"layer": lay})
    with e.edit_data() as md:
        md.vertices = [tuple(map(float, v)) for v in m.vertices]
        md.faces = [tuple(map(int, f)) for f in m.faces]
ddoc.saveas(os.path.join(OUT, "B7_model_3D.dxf"))
print("dxf ok")

# ------------------------------------------------------------------ IFC4 (mm, Z up)
import ifcopenshell, ifcopenshell.api
import ifcopenshell.api.root, ifcopenshell.api.unit, ifcopenshell.api.context, ifcopenshell.api.project
import ifcopenshell.api.aggregate, ifcopenshell.api.spatial, ifcopenshell.api.geometry, ifcopenshell.api.style
f = ifcopenshell.api.project.create_file(version="IFC4")
proj = ifcopenshell.api.root.create_entity(f, ifc_class="IfcProject", name="B7")
ifcopenshell.api.unit.assign_unit(f)
ctx = ifcopenshell.api.context.add_context(f, context_type="Model")
body = ifcopenshell.api.context.add_context(f, context_type="Model", context_identifier="Body",
                                            target_view="MODEL_VIEW", parent=ctx)
site = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSite", name="Site")
bldg = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuilding", name="B7")
ifcopenshell.api.aggregate.assign_object(f, products=[site], relating_object=proj)
ifcopenshell.api.aggregate.assign_object(f, products=[bldg], relating_object=site)
storeys = {}
for nm, el in (("1F", 30), ("2F", 390), ("3F", 710), ("RF", 1030)):
    s = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuildingStorey", name=nm)
    s.Elevation = el * 10.0
    storeys[nm] = s
ifcopenshell.api.aggregate.assign_object(f, products=list(storeys.values()), relating_object=bldg)
for s in storeys.values():
    ifcopenshell.api.geometry.edit_object_placement(f, product=s)
styles = {}
for c, (r, g, b, a) in MAT.items():
    st = ifcopenshell.api.style.add_style(f, name=c)
    ifcopenshell.api.style.add_surface_style(f, style=st, ifc_class="IfcSurfaceStyleShading", attributes={
        "SurfaceColour": {"Name": None, "Red": r / 255, "Green": g / 255, "Blue": b / 255},
        "Transparency": round(1 - a / 255, 2)})
    styles[c] = st

ifc_items = [(n, s, c, m) for (n, s, c, m) in ifc_walls + ifc_open if m is not None]
ifc_items += [(p["name"], p["storey"], p["cat"], p["mesh"]) for p in parts
              if (p["cat"] not in ("wall", "parapet", "glass", "door"))
              or p["name"].startswith("RF_") or "CentreWall" in p["name"]]
for name, st, c, m in ifc_items:
    m = m.copy(); m.merge_vertices()
    el = ifcopenshell.api.root.create_entity(f, ifc_class=IFC_CLASS[c], name=name)
    if c == "slab" and name.startswith(("2F", "3F", "RF", "1F")):
        el.PredefinedType = "ROOF" if name.startswith("RF") else ("BASESLAB" if name.startswith("1F") else "FLOOR")
    if "Landing" in name:
        el = ifcopenshell.api.root.reassign_class(f, product=el, ifc_class="IfcSlab"); el.PredefinedType = "LANDING"
    rep = ifcopenshell.api.geometry.add_mesh_representation(
        f, context=body, vertices=[[tuple(v * 0.01) for v in m.vertices]], faces=[[list(map(int, t)) for t in m.faces]])
    ifcopenshell.api.style.assign_representation_styles(f, shape_representation=rep, styles=[styles[c]])
    ifcopenshell.api.geometry.assign_representation(f, product=el, representation=rep)
    ifcopenshell.api.geometry.edit_object_placement(f, product=el)
    holder = storeys.get(st, storeys["1F"]) if st != "GL" else site
    if st == "GL":
        ifcopenshell.api.aggregate.assign_object(f, products=[el], relating_object=site) if False else \
            ifcopenshell.api.spatial.assign_container(f, products=[el], relating_structure=site)
    else:
        ifcopenshell.api.spatial.assign_container(f, products=[el], relating_structure=holder)
f.write(os.path.join(OUT, "B7_model.ifc"))
print("ifc ok", len(ifc_items), "elements")

# ------------------------------------------------------------------ USDZ (m, Y up) for iPhone AR Quick Look
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Vt, UsdUtils
usdc = os.path.join(OUT, "_B7_model.usdc")
stage = Usd.Stage.CreateNew(usdc)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)
root = UsdGeom.Xform.Define(stage, "/B7"); stage.SetDefaultPrim(root.GetPrim())
mats = {}
for c, (r, g, b, a) in MAT.items():
    mt = UsdShade.Material.Define(stage, f"/B7/Looks/{c}")
    sh = UsdShade.Shader.Define(stage, f"/B7/Looks/{c}/PBR")
    sh.CreateIdAttr("UsdPreviewSurface")
    sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(r / 255, g / 255, b / 255))
    sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.85)
    sh.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    sh.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(a / 255)
    mt.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
    mats[c] = mt
for (st, c), ms in sorted(groups.items()):
    m = flat(trimesh.util.concatenate(ms)); m.apply_transform(Y_UP)
    mesh = UsdGeom.Mesh.Define(stage, f"/B7/{'L' + st if st[0].isdigit() else st}_{c}")
    mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float, v)) for v in m.vertices]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3] * len(m.faces)))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray([int(i) for i in m.faces.flatten()]))
    nrm = np.repeat(m.face_normals, 3, axis=0)
    na = mesh.CreateNormalsAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float, n)) for n in nrm]))
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    mesh.CreateDoubleSidedAttr(MAT[c][3] < 255)
    lo, hi = m.bounds
    mesh.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float, lo)), Gf.Vec3f(*map(float, hi))]))
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mats[c])
stage.GetRootLayer().Save()
UsdUtils.CreateNewARKitUsdzPackage(usdc, os.path.join(OUT, "B7_model.usdz"))
os.remove(usdc)
print("usdz ok")
