"""导出网页查看器里的标注（annotation / hotspot）为本地资源。

数据来源就是浏览器保存下来的模型页面快照，两条都在里面：
  - `/i/models/<uid>/hotspots?optimized=1` 的缓存：名称、图片、eye/target/position
  - 模型 JSON 里的 `hotspot.hotspots`：每个标注锚在哪个三角形上
    （geometryUid + indices + barycentricWeights + localPosition）

坐标：这些坐标是原平台场景根坐标系（Z-up）。转 GLB 时的实际映射是
`(x, y, z) -> (x, z, -y)`（见后处理出的 GLB bbox 验证），本脚本一并换算。

用法:
    python export_annotations.py <page.htm> <outdir> [--no-images]
产物:
    <outdir>/annotations.json
    <outdir>/images/<uid>.jpeg
"""
import json
import os
import re
import sys
import urllib.request

ZUP_TO_GLB = lambda p: [p[0], p[2], -p[1]]


def brace_json(text, start):
    """从 start 处的 '{' 起做括号配平，返回 (obj, end)。"""
    depth = 0
    for k in range(start, len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:k + 1]), k + 1
    raise ValueError("括号不配平")


def extract(page_path):
    html = open(page_path, encoding="utf-8", errors="replace").read().replace("&#34;", '"')

    # 1) hotspots API 缓存
    key = html.find("/hotspots?optimized=1")
    if key < 0:
        raise SystemExit("页面里没有 hotspots API 缓存")
    api, _ = brace_json(html, html.find("{", html.find(":", key)))

    # 2) 场景里的锚点（geometryUid / indices / barycentricWeights / localPosition）
    anchors = {}
    i = html.find('"hotspot": {"visible"')
    if i >= 0:
        blk, _ = brace_json(html, html.find("{", i))
        for h in blk.get("hotspots", []):
            anchors[h["uid"]] = {
                "geometryUid": h.get("geometryUid"),
                "indices": h.get("indices"),
                "barycentricWeights": h.get("barycentricWeights"),
                "localPosition": h.get("localPosition"),
            }
    return api.get("results", []), anchors


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())
    return os.path.getsize(dest)


def main():
    argv = sys.argv[1:]
    pos = [a for a in argv if not a.startswith("--")]
    page, outdir = pos[0], pos[1]
    want_images = "--no-images" not in argv

    results, anchors = extract(page)
    os.makedirs(os.path.join(outdir, "images"), exist_ok=True)

    anns = []
    for order, r in enumerate(results):
        uid = r["uid"]
        img_file = None
        for img in r.get("images") or []:
            name = f"{img['uid']}.jpeg"
            dest = os.path.join(outdir, "images", name)
            if want_images and not os.path.exists(dest):
                try:
                    size = download(img["url"], dest)
                    print(f"  图片 {name} {size} B")
                except Exception as e:  # 网络失败不应让整批失败
                    print(f"  图片 {name} 下载失败: {e}")
            if os.path.exists(dest):
                img_file = f"images/{name}"
            break

        ann = {
            "order": order,
            "uid": uid,
            "name": r.get("name", ""),
            "content": (r.get("content") or {}).get("raw", ""),
            "image": img_file,
            # 模型坐标系（GLB / Y-up）里的锚点、相机目标与相机位
            "position": ZUP_TO_GLB(r["position"]),
            "target": ZUP_TO_GLB(r["target"]),
            "eye": ZUP_TO_GLB(r["eye"]),
            "source": {
                "position": r["position"],
                "target": r["target"],
                "eye": r["eye"],
                "geometryUid": (anchors.get(uid) or {}).get("geometryUid"),
                "indices": (anchors.get(uid) or {}).get("indices"),
                "barycentricWeights": (anchors.get(uid) or {}).get("barycentricWeights"),
            },
        }
        anns.append(ann)

    # 不写快照文件名/来源站点名：仓库里不允许出现平台标识
    doc = {"coordinate_frame": "gltf-y-up", "annotations": anns}
    dest = os.path.join(outdir, "annotations.json")
    json.dump(doc, open(dest, "w"), ensure_ascii=False, indent=1)
    print(f"写出 {dest}：{len(anns)} 条标注")

    # 自检：所有锚点应落在模型 bbox 内
    for a in anns:
        print("  -", a["name"][:44], "->", [round(v, 1) for v in a["position"]])


if __name__ == "__main__":
    main()
