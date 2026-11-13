"""B7 1F entry view, photoreal pass with Poly Haven CC0 assets.
usage: python3 b7_cycles2.py GLB OUT.png W H SAMPLES LENS BEARING EXPOSURE PH_ROOT"""
import sys, math, os
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix

GLB, OUT = sys.argv[1], sys.argv[2]
W, H, SPP = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
LENS, BEARING, EXPO = float(sys.argv[6]), float(sys.argv[7]), float(sys.argv[8])
PH = sys.argv[9]
CAM = (4.72, 1.70, 1.88)
F = 0.30   # 1F floor level (m)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
sc = bpy.context.scene
for o in list(bpy.data.objects):
    if o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o, do_unlink=True)


def wb(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


def mnames(o):
    return {s.material.name for s in o.material_slots if s.material}


# ------------------------------------------------------------------ remove placeholders that get real models
def inbox(o, x0, x1, y0, y1, zmax):
    lo, hi = wb(o); c = (lo + hi) / 2
    return x0 <= c.x <= x1 and y0 <= c.y <= y1 and hi.z <= zmax


rm = []
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    mn = mnames(o)
    if ('boucle' in mn or 'leaf' in mn
            or (inbox(o, 6.85, 8.75, 0.15, 0.75, 1.2) and mn & {'linen', 'oakLight'})         # dining chairs
            or (inbox(o, 9.9, 11.3, 2.4, 2.9, 1.0) and 'oakLight' in mn)                     # stools
            or (inbox(o, 6.6, 7.6, 3.7, 4.6, 0.9) and mn & {'oakLight', 'cabinet', 'pot'})    # coffee table + vase
            or (inbox(o, 8.4, 8.9, 2.75, 3.25, 0.9) and mn & {'oakLight', 'wire'})           # side table
            or (inbox(o, 4.7, 5.4, 4.6, 5.2, 2.2) and mn & {'pot', 'wire'})                  # plant pot
            or (inbox(o, 7.6, 8.0, 1.0, 1.3, 1.4) and 'pot' in mn)                           # centrepiece
            or (inbox(o, 6.0, 6.5, 2.9, 3.2, 1.0) and 'linen' in mn)):                       # throw cushion
        rm.append(o)
for o in rm:
    bpy.data.objects.remove(o, do_unlink=True)
print('removed placeholders:', len(rm))


# ------------------------------------------------------------------ node helpers
def N(nt, t, **kw):
    n = nt.nodes.new(t)
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def bsdf_of(mat):
    for n in mat.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n


def setin(n, name, val):
    if name in n.inputs:
        n.inputs[name].default_value = val


def load(path, color=True):
    im = bpy.data.images.load(path, check_existing=True)
    im.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    return im


def mean_lum(im):
    px = np.array(im.pixels[:], dtype=np.float32).reshape(-1, 4)[::131, :3]
    return float((px @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)).mean())


def tex(name, kind):
    return os.path.join(PH, 'tex', name, f'{name}_{kind}_2k.jpg')


def recolor(nt, src_socket, target, k, detail=1.0):
    """target colour, modulated by the source texture's luminance (normalised by k), detail in 0..1"""
    bw = N(nt, 'ShaderNodeRGBToBW'); nt.links.new(src_socket, bw.inputs[0])
    m1 = N(nt, 'ShaderNodeMath', operation='MULTIPLY'); m1.inputs[1].default_value = k
    nt.links.new(bw.outputs[0], m1.inputs[0])
    m2 = N(nt, 'ShaderNodeMath', operation='MULTIPLY_ADD', use_clamp=False)
    m2.inputs[1].default_value = detail; m2.inputs[2].default_value = 1 - detail
    nt.links.new(m1.outputs[0], m2.inputs[0])
    mix = N(nt, 'ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY'); mix.inputs[0].default_value = 1.0
    mix.inputs[6].default_value = (*target, 1)
    nt.links.new(m2.outputs[0], mix.inputs[7])
    return mix.outputs[2]


def pbr(mat, name, size, coords='OBJECT', target=None, detail=1.0, hsv=None, rough=(1.0, 0.0),
        bump=0.0, normal=0.0, coat=0.0, sheen=0.0, base=None):
    mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear()
    out = N(nt, 'ShaderNodeOutputMaterial'); b = N(nt, 'ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    tc = N(nt, 'ShaderNodeTexCoord'); mp = N(nt, 'ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1 / size, 1 / size, 1 / size)
    nt.links.new(tc.outputs['UV' if coords == 'UV' else 'Object'], mp.inputs['Vector'])

    def img(kind, color):
        t = N(nt, 'ShaderNodeTexImage'); t.image = load(tex(name, kind), color)
        if coords != 'UV':
            t.projection = 'BOX'; t.projection_blend = 0.3
        nt.links.new(mp.outputs['Vector'], t.inputs['Vector']); return t
    d = img('diff', True); r = img('rough', False)
    col = d.outputs['Color']
    if target is not None:
        col = recolor(nt, col, target, 1 / max(mean_lum(d.image), 0.02), detail)
    elif hsv is not None:
        hs = N(nt, 'ShaderNodeHueSaturation'); hs.inputs['Saturation'].default_value = hsv[0]
        hs.inputs['Value'].default_value = hsv[1]; nt.links.new(col, hs.inputs['Color']); col = hs.outputs['Color']
    if base is not None:
        setin(b, 'Base Color', (*base, 1))
    else:
        nt.links.new(col, b.inputs['Base Color'])
    rm = N(nt, 'ShaderNodeMath', operation='MULTIPLY_ADD', use_clamp=True)
    rm.inputs[1].default_value, rm.inputs[2].default_value = rough
    nt.links.new(r.outputs['Color'], rm.inputs[0]); nt.links.new(rm.outputs[0], b.inputs['Roughness'])
    nrm = None
    if normal > 0 and coords == 'UV':
        n = img('nor_gl', False); nm = N(nt, 'ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = normal
        nt.links.new(n.outputs['Color'], nm.inputs['Color']); nrm = nm.outputs['Normal']
    if bump > 0:
        bp = N(nt, 'ShaderNodeBump'); bp.inputs['Strength'].default_value = bump; bp.inputs['Distance'].default_value = 0.002
        nt.links.new(r.outputs['Color'], bp.inputs['Height'])
        if nrm is not None:
            nt.links.new(nrm, bp.inputs['Normal'])
        nrm = bp.outputs['Normal']
    if nrm is not None:
        nt.links.new(nrm, b.inputs['Normal'])
    setin(b, 'Coat Weight', coat); setin(b, 'Coat Roughness', 0.3)
    setin(b, 'Sheen Weight', sheen); setin(b, 'Sheen Roughness', 0.5)
    return b


def add_bevel(mat, radius):
    nt = mat.node_tree; b = bsdf_of(mat)
    bev = N(nt, 'ShaderNodeBevel'); bev.inputs['Radius'].default_value = radius; bev.samples = 6
    if b.inputs['Normal'].is_linked:
        nt.links.new(b.inputs['Normal'].links[0].from_socket, bev.inputs['Normal'])
    nt.links.new(bev.outputs['Normal'], b.inputs['Normal'])


def glass_mat(name, color=(1, 1, 1, 1), rough=0.0, ior=1.45, shadow=(0.93, 0.93, 0.93, 1)):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = N(nt, 'ShaderNodeOutputMaterial'); g = N(nt, 'ShaderNodeBsdfPrincipled')
    setin(g, 'Base Color', color); setin(g, 'Roughness', rough); setin(g, 'IOR', ior); setin(g, 'Transmission Weight', 1.0)
    tr = N(nt, 'ShaderNodeBsdfTransparent'); tr.inputs['Color'].default_value = shadow
    lp = N(nt, 'ShaderNodeLightPath'); mx = N(nt, 'ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Shadow Ray'], mx.inputs['Fac'])
    nt.links.new(g.outputs[0], mx.inputs[1]); nt.links.new(tr.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs['Surface'])
    return m


def plain(mat, color, rough, metal=0.0, coat=0.0, bevel=0.0, noise_bump=0.0, noise_scale=60):
    mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear()
    out = N(nt, 'ShaderNodeOutputMaterial'); b = N(nt, 'ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    setin(b, 'Base Color', (*color, 1)); setin(b, 'Roughness', rough); setin(b, 'Metallic', metal); setin(b, 'Coat Weight', coat)
    if noise_bump > 0:
        nz = N(nt, 'ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = noise_scale
        bp = N(nt, 'ShaderNodeBump'); bp.inputs['Strength'].default_value = noise_bump; bp.inputs['Distance'].default_value = 0.001
        nt.links.new(nz.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    if bevel > 0:
        add_bevel(mat, bevel)
    return b


def emissive(mat, color, strength):
    plain(mat, (1, 1, 1), 0.3)
    b = bsdf_of(mat); setin(b, 'Emission Color', (*color, 1)); setin(b, 'Emission Strength', strength)


# ------------------------------------------------------------------ scene materials
M = {m.name: m for m in bpy.data.materials}
pbr(M['floor'], 'laminate_floor_02', 1.70, coords='UV', hsv=(0.85, 1.12), rough=(0.7, 0.05), normal=0.6, coat=0.08)
for nm, cc in (('plaster', (0.90, 0.885, 0.85)), ('ceiling', (0.92, 0.91, 0.88))):
    pbr(M[nm], 'white_plaster_02', 1.0, base=cc, rough=(0.3, 0.65), bump=0.06)
pbr(M['oakLight'], 'oak_veneer_01', 1.83, target=(0.83, 0.69, 0.50), detail=0.8, rough=(0.6, 0.15), bump=0.05); add_bevel(M['oakLight'], 0.003)
pbr(M['log'], 'oak_wood_planks', 1.2, hsv=(0.9, 1.05), rough=(0.6, 0.1), bump=0.08, coat=0.15); add_bevel(M['log'], 0.004)
pbr(M['leather'], 'leather_white', 0.30, target=(0.84, 0.78, 0.69), detail=0.6, rough=(0.5, 0.2), bump=0.25, coat=0.1)
pbr(M['linen'], 'rough_linen', 0.27, target=(0.83, 0.79, 0.72), detail=0.5, rough=(0.2, 0.8), bump=0.3, sheen=0.4)
pbr(M['rug'], 'poly_wool_herringbone', 0.27, target=(0.80, 0.76, 0.69), detail=0.7, rough=(0.2, 0.8), bump=0.5, sheen=0.5)
plain(M['cabinet'], (0.85, 0.84, 0.81), 0.38, bevel=0.003)
plain(M['stone'], (0.90, 0.89, 0.87), 0.14, coat=0.2, bevel=0.003, noise_bump=0.01, noise_scale=400)
plain(M['blackGlass'], (0.01, 0.01, 0.01), 0.1)
plain(M['steel'], (0.8, 0.8, 0.8), 0.22, metal=1.0); plain(M['sinkDark'], (0.7, 0.7, 0.7), 0.3, metal=1.0)
plain(M['champagne'], (0.80, 0.73, 0.62), 0.3, metal=0.85, bevel=0.003)
plain(M['ceramic'], (0.93, 0.93, 0.92), 0.06, coat=0.3)
plain(M['pot'], (0.86, 0.84, 0.80), 0.6, noise_bump=0.1, noise_scale=150)
plain(M['wire'], (0.05, 0.05, 0.05), 0.4, metal=0.6)
emissive(M['lampGlow'], (1.0, 0.84, 0.62), 14)
emissive(M['downlight'], (1.0, 0.88, 0.72), 60)
gl = glass_mat('win_glass')
for o in bpy.data.objects:
    for s in o.material_slots:
        if s.material and s.material.name == 'glassClear':
            s.material = gl

# ------------------------------------------------------------------ reeded glass as real geometry
for o in list(bpy.data.objects):
    if o.type == 'MESH' and 'fluted' in mnames(o):
        bpy.data.objects.remove(o, do_unlink=True)
y0, y1, z0, z1 = 0.115, 1.47, 0.42, 3.69
x_back, x_core, bulge, pitch, seg = 5.904, 5.896, 0.006, 0.022, 8
nr = round((y1 - y0) / pitch); pitch = (y1 - y0) / nr
prof = [(x_core - bulge * math.sin(math.pi * k / seg), y0 + (i + k / seg) * pitch) for i in range(nr) for k in range(seg)]
prof += [(x_core, y1), (x_back, y1), (x_back, y0)]
bm = bmesh.new()
bot = [bm.verts.new((x, y, z0)) for x, y in prof]; top = [bm.verts.new((x, y, z1)) for x, y in prof]
n = len(prof)
for i in range(n):
    f = bm.faces.new((bot[i], bot[(i + 1) % n], top[(i + 1) % n], top[i])); f.smooth = i < n - 3
bm.faces.new(list(reversed(bot))); bm.faces.new(top); bm.normal_update()
me = bpy.data.meshes.new('reeded_glass'); bm.to_mesh(me); bm.free()
ob = bpy.data.objects.new('reeded_glass', me); sc.collection.objects.link(ob)
me.materials.append(glass_mat('reeded', (0.97, 0.99, 0.98, 1), 0.02, 1.5, (0.80, 0.82, 0.80, 1)))

# ------------------------------------------------------------------ Poly Haven models
cache = {}


def load_model(name):
    d = os.path.join(PH, 'models', name); f = [p for p in os.listdir(d) if p.endswith('.gltf')][0]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(d, f))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    roots = [o for o in new if o.parent is None]
    cache[name] = (roots, (lo + hi) / 2, lo.z, new)
    return cache[name]


def place(name, x, y, z=F, rot=0.0, recol=None):
    if name in cache:
        roots0, c, zmin, objs0 = cache[name]
        mapping = {}
        for o in objs0:
            mapping[o] = o.copy(); sc.collection.objects.link(mapping[o])
        for o in objs0:
            if o.parent in mapping:
                mapping[o].parent = mapping[o.parent]
        roots = [mapping[r] for r in roots0]
        for r, r0 in zip(roots, roots0):
            r.matrix_world = r0.matrix_world.copy()
    else:
        roots, c, zmin, objs0 = load_model(name)
        if recol:
            mats = {s.material for o in objs0 if o.type == 'MESH' for s in o.material_slots if s.material}
            for m in mats:
                recol(m)
        for r in roots:
            r['base'] = [list(row) for row in r.matrix_world]
    T = Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(rot), 4, 'Z') @ Matrix.Translation((-c.x, -c.y, -zmin))
    for r in roots:
        base = Matrix(r['base']) if 'base' in r else r.matrix_world.copy()
        r.matrix_world = T @ base
    return roots


def recol_fn(target, detail=0.7, only=None, skip=None, rough=None):
    def f(m):
        if only and not any(s in m.name.lower() for s in only):
            return
        if skip and any(s in m.name.lower() for s in skip):
            return
        nt = m.node_tree; b = bsdf_of(m)
        if not b or not b.inputs['Base Color'].is_linked:
            return
        src = b.inputs['Base Color'].links[0].from_socket
        im = next((n.image for n in nt.nodes if n.type == 'TEX_IMAGE' and n.image and 'diff' in n.image.name.lower()), None)
        k = 1 / max(mean_lum(im), 0.03) if im else 1.0
        nt.links.new(recolor(nt, src, target, k, detail), b.inputs['Base Color']); print('RECOL', m.name, round(k, 2))
        if rough is not None:
            if b.inputs['Roughness'].is_linked:
                nt.links.remove(b.inputs['Roughness'].links[0])
            setin(b, 'Roughness', rough)
    return f


place('modern_arm_chair_01', 8.60, 3.93, rot=-90,
      recol=lambda m: recol_fn((0.82, 0.78, 0.71), 0.5, only=['pillow'], rough=0.85)(m) or
      recol_fn((0.72, 0.58, 0.42), 0.9, only=['legs'])(m))
place('modern_coffee_table_01', 6.95, 4.05, rot=90, recol=recol_fn((0.74, 0.62, 0.47), 0.9))
place('side_table_01', 8.45, 2.92, recol=None)
place('throw_pillows_01', 6.30, 2.97, z=F + 0.47, rot=180, recol=recol_fn((0.80, 0.75, 0.66), 0.35, rough=0.9))
for i, x in enumerate((7.15, 7.80, 8.45)):
    place('dining_chair_02', x, 0.42, rot=180, recol=recol_fn((0.80, 0.76, 0.69), 0.6, rough=0.75) if i == 0 else None)
for i, x in enumerate((10.30, 11.00)):
    place('bar_chair_round_01', x, 2.66, rot=0, recol=recol_fn((0.84, 0.70, 0.52), 0.8) if i == 0 else None)
place('potted_plant_01', 9.40, 4.52, rot=30, recol=recol_fn((0.86, 0.84, 0.80), 0.5, only=['_pot']))
place('potted_plant_04', 7.50, 1.15, z=1.05)
place('ceramic_vase_01', 8.10, 1.10, z=1.05)
place('ceramic_vase_03', 5.80, 5.07, z=0.82)
place('book_encyclopedia_set_01', 8.62, 5.10, z=0.82)
place('wooden_bowl_01', 10.85, 1.82, z=1.20)


# small stack of books on the coffee table
def book(loc, size, color, rot):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object
    o.scale = size; o.rotation_euler[2] = rot
    m = bpy.data.materials.new('book'); plain(m, color, 0.6, bevel=0.002); o.data.materials.append(m)
book((6.70, 4.02, 0.705), (0.26, 0.19, 0.03), (0.78, 0.74, 0.66), 0.12)
book((6.71, 4.02, 0.735), (0.23, 0.17, 0.028), (0.55, 0.60, 0.58), 0.02)

# ------------------------------------------------------------------ world: HDRI (sun clamped out) + matching sun lamp
world = bpy.data.worlds.new('hdri'); sc.world = world; world.use_nodes = True
wn = world.node_tree; wn.nodes.clear()
wo = N(wn, 'ShaderNodeOutputWorld'); bg = N(wn, 'ShaderNodeBackground'); bg.inputs['Strength'].default_value = 1.0
tc = N(wn, 'ShaderNodeTexCoord'); mp = N(wn, 'ShaderNodeMapping'); mp.inputs['Rotation'].default_value = (0, 0, math.radians(132))
env = N(wn, 'ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(PH, 'hdri', 'pretville_street_2k.hdr'))
sep = N(wn, 'ShaderNodeSeparateColor'); com = N(wn, 'ShaderNodeCombineColor')
wn.links.new(tc.outputs['Generated'], mp.inputs['Vector']); wn.links.new(mp.outputs['Vector'], env.inputs['Vector'])
wn.links.new(env.outputs['Color'], sep.inputs['Color'])
for i in range(3):
    mn = N(wn, 'ShaderNodeMath', operation='MINIMUM'); mn.inputs[1].default_value = 25.0
    wn.links.new(sep.outputs[i], mn.inputs[0]); wn.links.new(mn.outputs[0], com.inputs[i])
wn.links.new(com.outputs['Color'], bg.inputs['Color']); wn.links.new(bg.outputs[0], wo.inputs['Surface'])

sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 5.0; sun.angle = math.radians(0.55); sun.color = (1.0, 0.92, 0.82)
so = bpy.data.objects.new('sun', sun); sc.collection.objects.link(so)
el, az = math.radians(21.3), math.radians(-168)            # sun position (WSW), light travels the other way
d = -Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
so.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def area(name, loc, size, inward, energy=0.0, portal=False, color=(1, 1, 1)):
    L = bpy.data.lights.new(name, 'AREA'); L.shape = 'RECTANGLE'; L.size, L.size_y = size; L.energy = energy; L.color = color
    if portal:
        for h in (L, getattr(L, 'cycles', None)):
            if h is not None and hasattr(h, 'is_portal'):
                h.is_portal = True
    o = bpy.data.objects.new(name, L); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = Vector(inward).to_track_quat('-Z', 'Y').to_euler()


area('portal_W2', (4.50, 3.53, 1.90), (2.70, 1.40), (1, 0, 0), portal=True)
area('portal_D1', (4.50, 1.15, 1.45), (1.50, 2.30), (1, 0, 0), portal=True)
area('portal_W4', (13.12, 1.205, 1.875), (1.05, 1.05), (-1, 0, 0), portal=True)
area('portal_D2', (13.12, 2.435, 1.35), (0.75, 2.10), (-1, 0, 0), portal=True)
warm = (1.0, 0.80, 0.60)
for x, y in [(5.6, 3.3), (7.0, 3.3), (8.4, 3.3), (5.6, 4.4), (7.0, 4.4), (8.4, 4.4), (10.0, 3.0), (11.8, 1.2), (11.8, 2.3), (10.8, 4.5)]:
    L = bpy.data.lights.new('dl', 'SPOT'); L.energy = 18; L.spot_size = math.radians(100); L.spot_blend = 0.7
    L.shadow_soft_size = 0.035; L.color = warm
    o = bpy.data.objects.new('dl', L); sc.collection.objects.link(o); o.location = (x, y, 3.72)
area('table_lamp', (7.80, 1.15, 2.105), (1.40, 0.035), (0, 0, -1), energy=30, color=warm)

# ------------------------------------------------------------------ camera
cd = bpy.data.cameras.new('cam'); cd.lens = LENS; cd.sensor_width = 36; cd.shift_y = -0.03; cd.clip_start = 0.05
co = bpy.data.objects.new('cam', cd); sc.collection.objects.link(co); sc.camera = co
co.location = CAM; co.rotation_euler = (math.radians(90), 0, math.radians(BEARING - 90))

# ------------------------------------------------------------------ render
sc.render.engine = 'CYCLES'; cy = sc.cycles
cy.device = 'CPU'; cy.samples = SPP; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.015
cy.use_denoising = True
try:
    cy.denoiser = 'OPENIMAGEDENOISE'
except Exception:
    pass
cy.max_bounces = 12; cy.diffuse_bounces = 6; cy.glossy_bounces = 4; cy.transmission_bounces = 12
cy.transparent_max_bounces = 8; cy.caustics_reflective = False; cy.caustics_refractive = False
cy.sample_clamp_indirect = 8; cy.blur_glossy = 1.0
sc.render.threads_mode = 'FIXED'; sc.render.threads = 4
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_depth = '16'
vs = sc.view_settings; vs.view_transform = 'AgX'
for look in ('AgX - Medium High Contrast', 'Medium High Contrast'):
    try:
        vs.look = look; break
    except Exception:
        pass
vs.exposure = EXPO
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print('RENDERED', OUT)
