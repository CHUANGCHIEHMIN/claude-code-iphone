"""Photoreal Cycles render of the B7 1F entry view.
usage: python3 b7_cycles.py GLB OUT.png W H SAMPLES LENS BEARING EXPOSURE [camx camy camz]"""
import sys, math
import bpy, bmesh
from mathutils import Vector

GLB, OUT = sys.argv[1], sys.argv[2]
W, H, SPP = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
LENS, BEARING, EXPO = float(sys.argv[6]), float(sys.argv[7]), float(sys.argv[8])
CAM = tuple(map(float, sys.argv[9:12])) if len(sys.argv) > 11 else (4.72, 1.70, 1.88)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
sc = bpy.context.scene
for o in list(bpy.data.objects):
    if o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o, do_unlink=True)


# ------------------------------------------------------------------ material helpers
def bsdf_of(mat):
    for n in mat.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return None


def setin(n, name, val):
    if name in n.inputs:
        n.inputs[name].default_value = val


def add_bump(mat, scale, strength, distance=0.002, detail=6.0, from_image=False):
    nt = mat.node_tree; b = bsdf_of(mat)
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = distance
    if from_image and b.inputs['Base Color'].is_linked:
        src = b.inputs['Base Color'].links[0].from_socket
        nt.links.new(src, bump.inputs['Height'])
    else:
        tex = nt.nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value = scale
        tex.inputs['Detail'].default_value = detail
        nt.links.new(tex.outputs['Fac'], bump.inputs['Height'])
    if b.inputs['Normal'].is_linked:   # chain onto existing normal map
        nt.links.new(b.inputs['Normal'].links[0].from_socket, bump.inputs['Normal'])
    nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return bump


def add_bevel(mat, radius):
    nt = mat.node_tree; b = bsdf_of(mat)
    bev = nt.nodes.new('ShaderNodeBevel'); bev.inputs['Radius'].default_value = radius; bev.samples = 6
    if b.inputs['Normal'].is_linked:
        nt.links.new(b.inputs['Normal'].links[0].from_socket, bev.inputs['Normal'])
    nt.links.new(bev.outputs['Normal'], b.inputs['Normal'])


def glass_mat(name, color=(1, 1, 1, 1), rough=0.0, ior=1.45, shadow_tint=(0.92, 0.92, 0.92, 1)):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    g = nt.nodes.new('ShaderNodeBsdfPrincipled')
    setin(g, 'Base Color', color); setin(g, 'Roughness', rough); setin(g, 'IOR', ior)
    setin(g, 'Transmission Weight', 1.0); setin(g, 'Transmission', 1.0)
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); tr.inputs['Color'].default_value = shadow_tint
    lp = nt.nodes.new('ShaderNodeLightPath'); mx = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Shadow Ray'], mx.inputs['Fac'])
    nt.links.new(g.outputs[0], mx.inputs[1]); nt.links.new(tr.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs['Surface'])
    return m


def emit_mat(mat, color, strength):
    b = bsdf_of(mat)
    setin(b, 'Base Color', (1, 1, 1, 1)); setin(b, 'Emission Color', color); setin(b, 'Emission Strength', strength)


mats = {m.name: m for m in bpy.data.materials if m.use_nodes and bsdf_of(m)}
for nm, m in mats.items():
    b = bsdf_of(m)
    setin(b, 'Alpha', 1.0)
    if nm == 'plaster':
        setin(b, 'Base Color', (0.91, 0.89, 0.85, 1)); setin(b, 'Roughness', 0.9); add_bump(m, 60, 0.04)
    elif nm == 'ceiling':
        setin(b, 'Base Color', (0.92, 0.91, 0.88, 1)); setin(b, 'Roughness', 0.95)
    elif nm == 'floor':
        setin(b, 'Roughness', 0.32); setin(b, 'Coat Weight', 0.15); setin(b, 'Coat Roughness', 0.25)
        add_bump(m, 0, 0.12, 0.003, from_image=True)
    elif nm == 'oakLight':
        setin(b, 'Roughness', 0.48); add_bump(m, 0, 0.05, 0.002, from_image=True); add_bevel(m, 0.004)
    elif nm == 'log':
        setin(b, 'Roughness', 0.38); setin(b, 'Coat Weight', 0.2); setin(b, 'Coat Roughness', 0.3)
        add_bump(m, 0, 0.12, 0.003, from_image=True); add_bevel(m, 0.004)
    elif nm == 'leather':
        setin(b, 'Base Color', (0.80, 0.73, 0.63, 1)); setin(b, 'Roughness', 0.42)
        setin(b, 'Coat Weight', 0.12); setin(b, 'Coat Roughness', 0.35); add_bump(m, 420, 0.07, 0.001, detail=10)
    elif nm in ('boucle', 'linen', 'rug'):
        setin(b, 'Roughness', 1.0); setin(b, 'Sheen Weight', 0.6 if nm != 'linen' else 0.35)
        setin(b, 'Sheen Roughness', 0.5)
        add_bump(m, {'boucle': 900, 'linen': 1200, 'rug': 700}[nm], {'boucle': 0.45, 'linen': 0.15, 'rug': 0.5}[nm], 0.002, detail=4)
    elif nm == 'cabinet':
        setin(b, 'Base Color', (0.84, 0.83, 0.80, 1)); setin(b, 'Roughness', 0.42); add_bevel(m, 0.003)
    elif nm == 'stone':
        setin(b, 'Base Color', (0.88, 0.87, 0.85, 1)); setin(b, 'Roughness', 0.16); add_bevel(m, 0.003)
    elif nm == 'blackGlass':
        setin(b, 'Base Color', (0.012, 0.012, 0.012, 1)); setin(b, 'Roughness', 0.12); setin(b, 'Metallic', 0)
    elif nm in ('steel', 'sinkDark'):
        setin(b, 'Metallic', 1.0); setin(b, 'Roughness', 0.25)
    elif nm == 'champagne':
        setin(b, 'Base Color', (0.78, 0.71, 0.60, 1)); setin(b, 'Metallic', 0.85); setin(b, 'Roughness', 0.32)
    elif nm == 'ceramic':
        setin(b, 'Base Color', (0.92, 0.92, 0.91, 1)); setin(b, 'Roughness', 0.08)
    elif nm == 'pot':
        setin(b, 'Base Color', (0.82, 0.79, 0.74, 1)); setin(b, 'Roughness', 0.65); add_bump(m, 120, 0.15)
    elif nm == 'leaf':
        setin(b, 'Base Color', (0.20, 0.30, 0.14, 1)); setin(b, 'Roughness', 0.55); setin(b, 'Subsurface Weight', 0.2)
    elif nm == 'wire':
        setin(b, 'Base Color', (0.05, 0.05, 0.05, 1)); setin(b, 'Roughness', 0.4); setin(b, 'Metallic', 0.6)
    elif nm == 'lampGlow':
        emit_mat(m, (1.0, 0.84, 0.62, 1), 14)
    elif nm == 'downlight':
        emit_mat(m, (1.0, 0.88, 0.72, 1), 60)

# window glass: physically clear, transparent to shadow rays
gl = glass_mat('win_glass', (1, 1, 1, 1), 0.0, 1.45, (0.95, 0.95, 0.95, 1))
for o in bpy.data.objects:
    if o.type == 'MESH':
        for s in o.material_slots:
            if s.material and s.material.name == 'glassClear':
                s.material = gl

# ------------------------------------------------------------------ real reeded glass (geometry)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and any(s.material and s.material.name == 'fluted' for s in o.material_slots):
        bpy.data.objects.remove(o, do_unlink=True)
y0, y1, z0, z1 = 0.115, 1.47, 0.42, 3.69
x_back, x_core, bulge, pitch, seg = 5.904, 5.896, 0.006, 0.022, 8
n_ribs = max(1, round((y1 - y0) / pitch)); pitch = (y1 - y0) / n_ribs
prof = []
for i in range(n_ribs):
    for k in range(seg):
        t = k / seg
        prof.append((x_core - bulge * math.sin(math.pi * t), y0 + (i + t) * pitch))
prof.append((x_core, y1)); prof.append((x_back, y1)); prof.append((x_back, y0))
bm = bmesh.new()
bot = [bm.verts.new((x, y, z0)) for x, y in prof]
top = [bm.verts.new((x, y, z1)) for x, y in prof]
n = len(prof)
for i in range(n):
    j = (i + 1) % n
    f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
    f.smooth = i < n - 3
bm.faces.new(list(reversed(bot))); bm.faces.new(top)
bm.normal_update()
me = bpy.data.meshes.new('reeded_glass'); bm.to_mesh(me); bm.free()
ob = bpy.data.objects.new('reeded_glass', me); sc.collection.objects.link(ob)
me.materials.append(glass_mat('reeded', (0.97, 0.99, 0.98, 1), 0.03, 1.5, (0.80, 0.82, 0.80, 1)))
for e in me.edges:   # rib valleys stay crisp
    pass

# ------------------------------------------------------------------ small props (books, tray, bowl)
def prop_box(name, loc, size, color, rough=0.6, rot=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.active_object
    o.name = name; o.scale = size; o.rotation_euler[2] = rot
    m = bpy.data.materials.new(name); m.use_nodes = True; b = bsdf_of(m)
    setin(b, 'Base Color', color); setin(b, 'Roughness', rough); o.data.materials.append(m)
    bev = o.modifiers.new('bev', 'BEVEL'); bev.width = 0.002; bev.segments = 2
    return o
prop_box('book1', (6.95, 4.12, 0.695), (0.26, 0.19, 0.03), (0.78, 0.74, 0.66, 1), rot=0.12)
prop_box('book2', (6.96, 4.12, 0.725), (0.23, 0.17, 0.028), (0.55, 0.60, 0.58, 1), rot=0.02)
prop_box('book3', (6.95, 4.11, 0.752), (0.21, 0.15, 0.026), (0.90, 0.88, 0.84, 1), rot=0.2)
prop_box('board', (10.45, 2.05, 1.205), (0.42, 0.24, 0.02), (0.62, 0.45, 0.28, 1), rough=0.5, rot=-0.15)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=(10.85, 1.80, 1.26), segments=48, ring_count=24)
bowl = bpy.context.active_object; bowl.scale = (1, 1, 0.45)
bm_ = bpy.data.materials.new('bowl'); bm_.use_nodes = True; setin(bsdf_of(bm_), 'Base Color', (0.93, 0.92, 0.90, 1))
setin(bsdf_of(bm_), 'Roughness', 0.15); bowl.data.materials.append(bm_)
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name.startswith(('book', 'board')) or o.name.startswith('Sphere'):
        o.data.shade_smooth() if o.name.startswith('Sphere') else None

# ------------------------------------------------------------------ world + sun
world = bpy.data.worlds.new('sky'); sc.world = world; world.use_nodes = True
wn = world.node_tree; bg = wn.nodes['Background']
grad = wn.nodes.new('ShaderNodeTexSky') if False else None
bg.inputs['Color'].default_value = (0.70, 0.79, 0.92, 1); bg.inputs['Strength'].default_value = 1.6

sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 4.2; sun.angle = math.radians(0.6)
sun.color = (1.0, 0.90, 0.78)
so = bpy.data.objects.new('sun', sun); sc.collection.objects.link(so)
el, az = math.radians(26), math.radians(12)            # light travels toward ENE, from the WSW
d = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), -math.sin(el)))
so.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def area(name, loc, size, normal, energy=0.0, portal=False, color=(1, 1, 1)):
    L = bpy.data.lights.new(name, 'AREA'); L.shape = 'RECTANGLE'; L.size, L.size_y = size
    L.energy = energy; L.color = color
    if portal:
        for holder in (L, getattr(L, 'cycles', None)):
            if holder is not None and hasattr(holder, 'is_portal'):
                holder.is_portal = True
    o = bpy.data.objects.new(name, L); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (-Vector(normal)).to_track_quat('-Z', 'Y').to_euler()
    return o


# portals: light emitted along local -Z, so pass the inward direction as -normal
area('portal_W2', (4.50, 3.53, 1.90), (2.70, 1.40), (-1, 0, 0), portal=True)
area('portal_D1', (4.50, 1.15, 1.45), (1.50, 2.30), (-1, 0, 0), portal=True)
area('portal_W4', (13.12, 1.205, 1.875), (1.05, 1.05), (1, 0, 0), portal=True)
area('portal_D2', (13.12, 2.435, 1.35), (0.75, 2.10), (1, 0, 0), portal=True)

warm = (1.0, 0.80, 0.60)
for x, y in [(5.6, 3.3), (7.0, 3.3), (8.4, 3.3), (5.6, 4.4), (7.0, 4.4), (8.4, 4.4), (10.0, 3.0), (11.8, 1.2), (11.8, 2.3), (10.8, 4.5)]:
    L = bpy.data.lights.new('dl', 'SPOT'); L.energy = 22; L.spot_size = math.radians(100); L.spot_blend = 0.7
    L.shadow_soft_size = 0.035; L.color = warm
    o = bpy.data.objects.new('dl', L); sc.collection.objects.link(o); o.location = (x, y, 3.72)
area('table_lamp', (7.80, 1.15, 2.105), (1.40, 0.035), (0, 0, 1), energy=35, color=warm)

# ------------------------------------------------------------------ camera (level, two-point perspective)
cd = bpy.data.cameras.new('cam'); cd.lens = LENS; cd.sensor_width = 36; cd.shift_y = -0.03
cd.clip_start = 0.05
co = bpy.data.objects.new('cam', cd); sc.collection.objects.link(co); sc.camera = co
co.location = CAM; co.rotation_euler = (math.radians(90), 0, math.radians(BEARING - 90))

# ------------------------------------------------------------------ render settings
sc.render.engine = 'CYCLES'; cy = sc.cycles
cy.device = 'CPU'; cy.samples = SPP; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.02
cy.use_denoising = True
try: cy.denoiser = 'OPENIMAGEDENOISE'
except Exception: pass
cy.max_bounces = 10; cy.diffuse_bounces = 5; cy.glossy_bounces = 4; cy.transmission_bounces = 12
cy.transparent_max_bounces = 8; cy.caustics_reflective = False; cy.caustics_refractive = False
cy.sample_clamp_indirect = 8; cy.blur_glossy = 1.0
sc.render.threads_mode = 'FIXED'; sc.render.threads = 4
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.image_settings.file_format = 'PNG'
vs = sc.view_settings
vs.view_transform = 'AgX'
for look in ('AgX - Medium High Contrast', 'Medium High Contrast', 'AgX - Base Contrast'):
    try:
        vs.look = look; break
    except Exception:
        pass
vs.exposure = EXPO
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print('RENDERED', OUT)
