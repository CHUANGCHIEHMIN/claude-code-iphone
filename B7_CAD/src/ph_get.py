import json, os, sys, subprocess
root = sys.argv[1]
models = {"sofa_02": "2k", "modern_arm_chair_01": "2k", "ArmChair_01": "1k", "dining_chair_02": "2k", "bar_chair_round_01": "2k",
          "throw_pillows_01": "2k", "modern_coffee_table_01": "2k", "side_table_01": "1k", "potted_plant_01": "2k",
          "potted_plant_02": "2k", "potted_plant_04": "1k", "ceramic_vase_01": "1k", "ceramic_vase_03": "1k",
          "book_encyclopedia_set_01": "1k", "wooden_bowl_01": "1k", "hanging_picture_frame_01": "1k", "modern_ceiling_lamp_01": "1k"}
textures = ["laminate_floor_02", "oak_wood_planks", "oak_veneer_01", "leather_white", "rough_linen", "poly_wool_herringbone", "white_plaster_02"]
hdris = ["pretville_street", "garden_nook"]

def get(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    subprocess.run(["curl", "-sS", "-m", "300", "-o", path, url], check=True)

def files(name):
    p = os.path.join(root, "api", name + ".json")
    get(f"https://api.polyhaven.com/files/{name}", p)
    return json.load(open(p))

for n, res in models.items():
    g = files(n)["gltf"][res]["gltf"]
    d = os.path.join(root, "models", n)
    get(g["url"], os.path.join(d, os.path.basename(g["url"])))
    for rel, inc in g.get("include", {}).items():
        get(inc["url"], os.path.join(d, rel))
    print("model", n)
for n in textures:
    f = files(n)
    for key in ("Diffuse", "nor_gl", "Rough"):
        u = f[key]["2k"]["jpg"]["url"]
        get(u, os.path.join(root, "tex", n, os.path.basename(u)))
    print("tex", n)
for n in hdris:
    u = files(n)["hdri"]["2k"]["hdr"]["url"]
    get(u, os.path.join(root, "hdri", os.path.basename(u)))
    print("hdri", n)
