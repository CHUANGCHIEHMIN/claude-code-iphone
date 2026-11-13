import json, struct, sys
src, dst = sys.argv[1], sys.argv[2]
b = open(src, 'rb').read()
jl = struct.unpack('<I', b[12:16])[0]
j = json.loads(b[20:20 + jl])
rest = b[20 + jl:]
for m in j.get('materials', []):
    ext = m.get('extensions', {})
    ext.pop('KHR_materials_volume', None)
    if not ext: m.pop('extensions', None)
j['extensionsUsed'] = [e for e in j.get('extensionsUsed', []) if e != 'KHR_materials_volume']
js = json.dumps(j, separators=(',', ':')).encode()
js += b' ' * ((4 - len(js) % 4) % 4)
total = 12 + 8 + len(js) + len(rest)
open(dst, 'wb').write(struct.pack('<III', 0x46546C67, 2, total) + struct.pack('<I4s', len(js), b'JSON') + js + rest)
print('ok', len(j['materials']), 'materials')
