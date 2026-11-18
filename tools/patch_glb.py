import json, struct, sys
src, dst = sys.argv[1], sys.argv[2]
b = open(src,'rb').read()
magic, ver, total = struct.unpack('<4sII', b[:12])
n, t = struct.unpack('<I4s', b[12:20]); j = json.loads(b[20:20+n]); rest = b[20+n:]
# names per material usage
use = {}
for node in j['nodes']:
    if 'mesh' in node:
        for p in j['meshes'][node['mesh']]['primitives']:
            use.setdefault(p.get('material'), set()).add(node.get('name','').split('_')[0])
for k,v in use.items(): print(k, j['materials'][k]['pbrMetallicRoughness'].get('baseColorFactor'), sorted(v))
tune = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
for i, m in enumerate(j['materials']):
    p = m.setdefault('pbrMetallicRoughness', {})
    if str(i) in tune:
        p.update(tune[str(i)])
    else:
        p.setdefault('metallicFactor', 0.0); p.setdefault('roughnessFactor', 0.8)
sc = j['scenes'][j.get('scene', 0)]
j['nodes'].append({'name': 'zup_to_yup', 'rotation': [-0.70710678, 0, 0, 0.70710678], 'children': sc['nodes']})
sc['nodes'] = [len(j['nodes']) - 1]
js = json.dumps(j, separators=(',', ':')).encode(); js += b' ' * ((4 - len(js) % 4) % 4)
out = struct.pack('<4sII', magic, ver, 12 + 8 + len(js) + len(rest)) + struct.pack('<I4s', len(js), b'JSON') + js + rest
open(dst, 'wb').write(out); print('wrote', len(out))
