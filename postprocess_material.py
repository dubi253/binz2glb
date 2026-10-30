"""回填 osg.Material 颜色到 glTF 材质（兜底脚本）。

历史上的坑：上游 osgjs2gltf 只用贴图做材质去重键，`osg.Material.Diffuse` 被整块丢掉，
一个 17 种材料层的芯片模型会变成一整片白。本项目已在 `lib/osgjs2gltf.js` 里修好
（材质键含 baseColorFactor），所以本脚本现在只是**兜底**：

  - 只有当 GLB 里所有材质都是纯白（说明颜色确实没带过来）时，才用 osgjs 里的颜色回填；
  - 按材质名（含去掉 `_数字` 后缀的名字）逐个匹配；
  - 其它情况什么都不做，避免覆盖正确的颜色。

用法:
    python postprocess_material.py <in.glb> <out.glb> [--osgjs <file.osgjs>]
不给 --osgjs 时，用 in.glb 同目录的 file.osgjs。
"""
import json
import os
import struct
import sys


def load_glb(path):
    d = open(path, "rb").read()
    assert d[:4] == b"glTF", "不是 GLB"
    jlen, _ = struct.unpack("<II", d[12:20])
    j = json.loads(d[20:20 + jlen].decode())
    boff = 20 + jlen
    blen, _ = struct.unpack("<II", d[boff:boff + 8])
    return j, d[boff + 8:boff + 8 + blen]


def save_glb(path, j, binc):
    jb = json.dumps(j, separators=(",", ":")).encode()
    jb += b" " * (-len(jb) % 4)
    binc = binc + b"\x00" * (-len(binc) % 4)
    total = 12 + 8 + len(jb) + 8 + len(binc)
    out = bytearray(b"glTF" + struct.pack("<II", 2, total))
    out += struct.pack("<II", len(jb), 0x4E4F534A) + jb
    out += struct.pack("<II", len(binc), 0x004E4942) + binc
    open(path, "wb").write(bytes(out))


def osg_colors(path):
    """{材质名: [r,g,b,a]} —— 从 osgjs 场景图里收集 osg.Material.Diffuse。"""
    found = {}
    stack = [json.load(open(path))]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            mat = node.get("osg.Material")
            if isinstance(mat, dict) and isinstance(mat.get("Diffuse"), list):
                found.setdefault(str(mat.get("Name") or ""), [float(x) for x in mat["Diffuse"][:4]])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return found


def main():
    argv = sys.argv[1:]
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2:
        sys.exit(__doc__)
    src, dst = pos[0], pos[1]
    osgjs = argv[argv.index("--osgjs") + 1] if "--osgjs" in argv else \
        os.path.join(os.path.dirname(os.path.abspath(src)), "file.osgjs")

    j, binc = load_glb(src)
    mats = j.get("materials", [])
    if not mats:
        sys.exit("GLB 里没有材质，先检查转换步骤")

    def factor(m):
        return (m.get("pbrMetallicRoughness", {}).get("baseColorFactor") or [1, 1, 1, 1])[:3]

    white = all(all(abs(c - 1.0) < 1e-6 for c in factor(m)) for m in mats)
    colors = osg_colors(osgjs) if os.path.isfile(osgjs) else {}
    if not colors:
        print("没有可用的 osgjs 颜色，原样输出")
    elif not white:
        print(f"材质已有颜色（{len(mats)} 个材质），跳过回填")
    else:
        hits = 0
        for m in mats:
            name = str(m.get("name") or "")
            col = colors.get(name) or colors.get(name.rsplit("_", 1)[0])
            if col:
                m.setdefault("pbrMetallicRoughness", {})["baseColorFactor"] = col
                hits += 1
        print(f"回填 {hits}/{len(mats)} 个材质颜色")

    save_glb(dst, j, binc)
    print(f"写出 {dst} ({os.path.getsize(dst)} B)")


if __name__ == "__main__":
    main()
