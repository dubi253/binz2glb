import json, struct, sys, numpy as np

src, dst = sys.argv[1], sys.argv[2]
d = bytearray(open(src,'rb').read())
jlen,_ = struct.unpack('<II', d[12:20])
j = json.loads(bytes(d[20:20+jlen]).decode())
boff = 20 + jlen
blen,_ = struct.unpack('<II', d[boff:boff+8])
bstart = boff + 8

DTS = {5126:np.float32, 5125:np.uint32, 5123:np.uint16, 5121:np.uint8}
NC = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}

def view(i):
    a = j['accessors'][i]; bv = j['bufferViews'][a['bufferView']]
    dt = DTS[a['componentType']]; nc = NC[a['type']]
    start = bstart + bv.get('byteOffset',0) + a.get('byteOffset',0)
    isz = np.dtype(dt).itemsize
    stride = bv.get('byteStride') or nc*isz
    assert stride == nc*isz, "interleaved buffers not supported"
    cnt = a['count']
    return np.frombuffer(d, dtype=dt, count=cnt*nc, offset=start).reshape(cnt, nc)

fixed = 0
for m in j['meshes']:
    for pr in m['primitives']:
        N = view(pr['attributes']['NORMAL'])
        L = np.linalg.norm(N.astype(np.float64), axis=1)
        bad = np.nonzero(L == 0)[0]
        if not len(bad): continue
        P = view(pr['attributes']['POSITION']).astype(np.float64)
        I = view(pr['indices']).astype(np.int64).reshape(-1,3)
        v0,v1,v2 = P[I[:,0]], P[I[:,1]], P[I[:,2]]
        fn = np.cross(v1-v0, v2-v0)              # area-weighted
        acc = np.zeros_like(P)
        for k in range(3):
            np.add.at(acc, I[:,k], fn)
        for vi in bad:
            n = acc[vi]
            ln = np.linalg.norm(n)
            N[vi] = (n/ln).astype(np.float32) if ln > 1e-12 else np.array([0,0,1], np.float32)
            fixed += 1
open(dst,'wb').write(bytes(d))
print("fixed zero normals:", fixed)
