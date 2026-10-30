---
name: binz-to-glb
description: 把加密 .binz 还原成标准 GLB 并部署离线查看器。
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [binz, GLTF, 3D, OfflineViewer]
    related_skills: []
---

# 加密 binz → 标准 3D 模型

原平台自 2021-06 起把模型文件加密成 `.binz`（解密后是 OSGJS 场景 JSON + 几何二进制），
任何 3D 软件都打不开。本技能覆盖完整链路：抓页面 → 取两个 binz → 解密 → 转 GLB →
修数据 → 校验 → 内网离线查看。只在本地做互操作，产物不自带分发权。

## 何时使用

- 用户手上有一个 `.binz`（或查看器的模型页面），要"能打开的模型"
- 要把查看器里的模型放进内网/离线环境查看
- 需要判断某个 `.binz` 下载是否完整、是不是真的 3D 模型

不适用：模型作者开放了官方下载（直接下原始 glb/fbx，别绕）；私有/付费模型（拿不到
`model_file.binz`）；只要截图不要几何。

## 前置条件

- Node ≥ 18（解密依赖 `DecompressionStream`；实测 v24.18.0）。解密/转换不需要 npm 依赖。
- Python + numpy（后处理）：用项目根的 uv 虚拟环境，清华源、IPv4：

      cd <项目根>
      uv venv --python 3.14 .venv
      UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
        uv pip install --python .venv/bin/python numpy

- 本目录已带：`decrypt.wasm`（253,767 B）、`decrypt-core.mjs`、`lib/`（osgjs2gltf 转换库）。
- 需要页面的**浏览器另存为快照**：`xxx.htm` + `xxx_files/`（里面有 viewer 的 `.js` bundle，
  static key 就藏在其中）。光有 `.binz` 解不开。

## 快速参考

以下命令都在本目录（`binz2glb/`）里执行：

    # 1 解密：页面快照 + 两个 binz → out/file.osgjs + out/model_file.bin
    node decrypt.mjs "data/page/<页面>.htm" models/<slug>/source/file.binz \
                     models/<slug>/source/model_file.binz out
    # 2 解密产物 → GLB
    node osgjs2glb.mjs ./out ./out/raw.glb
    # 3 后处理（零法线 + 材质色）
    python postprocess_normals.py  out/raw.glb  out/norm.glb
    python postprocess_material.py out/norm.glb out/final.glb
    # 4 标注（annotation/hotspot）：名称/图片/相机视点，坐标换算进 GLB 系
    python export_annotations.py "data/page/<页面>.htm" models/<slug>/annotations
    # 5 校验（Khronos 官方；gltf-validator 从 npmmirror 装）
    npm install --registry=https://registry.npmmirror.com gltf-validator
    node validate.mjs ./out/final.glb      # 片段见 references/troubleshooting.md

## 流程

### 步骤 1 采集：把页面和两个 binz 拿到本地

在页面 JSON 里找 `files[0]`：

- `osgjsUrl` → `.../file.binz`，约 17 KB，**场景图 JSON**，少了它无法转换
- 同一条目里的 `modelSize` → 主几何 `.binz` 的**期望字节数**（用于判断下载完整性）
- 主几何文件名通常是 `model_file.binz`，URL 形如
  `https://<media-host>/models/<uid>/<hash>/files/<hash>/model_file.binz`
- `vertexCount` / `faceCount` 记下来，步骤 3 要对数

完成判据：`stat -c%s model_file.binz` 等于页面 `modelSize`；`file.binz` 存在且 > 1 KB。

### 步骤 2 解密

    node decrypt.mjs "<页面.htm>" "<file.binz>" "<model_file.binz>" ./out

脚本自己完成两件事：从页面同目录（含子目录）的 `.js` bundle 里正则提取 40 位 static key
（`C04p:t=>{"use strict";t.exports="<40 hex>"`），从页面 JSON 取 `files[0].p[0].b` 作为
每模型密钥材料 diterB，然后喂给 `decrypt.wasm`。

完成判据：`out/file.osgjs` 以 `{"Generator": "OpenSceneGraph` 开头（本项目样例 260,426 B）；
`out/model_file.bin` 大小与 `model_file.binz` 同数量级（样例 68,922,700 B，约 1.8×）。

### 步骤 3 转换 OSGJS → GLB

    node osgjs2glb.mjs ./out ./out/raw.glb

完成判据：打印的三角面数与页面 `faceCount` 差异 < 1%（样例 1,252,798 / 1,254,128，差
0.1%，来自退化三角形被丢弃）。差异大 = 解密或 key 错，别继续。

### 步骤 4 后处理（两步都必须做）

1. `postprocess_normals.py`：原平台原始数据里有零长度法线（样例 698 个 / 2,258,844），
   不修则 validator 报 `ACCESSOR_VECTOR3_NON_UNIT`、渲染出黑斑。按相邻面面积加权重算。
2. `postprocess_material.py`：只是**兜底**。材质色现在由 `lib/osgjs2gltf.js` 直接带出
   （材质去重键里含 baseColorFactor，样例 17 个材质各自带 `osg.Material.Diffuse`）；
   脚本仅当 GLB 里所有材质都是纯白时才回填，否则打印"跳过回填"。

完成判据：normals 脚本报出"fixed zero normals: N"（N 与首次分析一致，重跑为 0）；
material 脚本打印新的 pbrMetallicRoughness。

### 步骤 5 导出标注（annotation / hotspot）

    python export_annotations.py "data/page/<页面>.htm" models/<slug>/annotations

数据在页面快照里有两份，脚本会合并：`/i/models/<uid>/hotspots?optimized=1` 的缓存
（name / content / images / eye / target / position）与模型 JSON 的 `hotspot.hotspots`
（geometryUid / indices / barycentricWeights）。坐标必须换系：
原平台是 Z-up，写进 GLB 的映射为 `(x, y, z) -> (x, z, -y)`。

完成判据：`annotations/annotations.json` 条数等于页面上标注数量；图片落地到
`annotations/images/`；所有 `position` 落在 GLB bbox 内（样例 5 条，两个点正好在 z=87 面上）。

### 步骤 6 校验

Khronos glTF-Validator 必须 `errors=0 warnings=0`，且材质数、三角面数与源一致
（样例 17 材质 / 1,252,798 面）。片段见 `references/troubleshooting.md`。

### 步骤 7 部署离线查看器（Docker）

**不要自己写渲染器**。带标注的呈现用 `google/model-viewer`（8.3k★，原生 hotspot，
声明式：`<button slot="hotspot-1" data-position="x y z">`），通用格式用
`kovacsv/Online3DViewer`（3.7k★，MIT，glb/obj/stl/3mf/step 一堆格式）。两者都是静态包，
一个 `nginx:alpine` 容器就能装下：

    FROM nginx:alpine
    COPY site/ /usr/share/nginx/html/
    COPY model.glb /usr/share/nginx/html/model.glb
    COPY annotations/ /usr/share/nginx/html/annotations/

    docker compose up -d --build      # 容器内 nginx:80，宿主机映射随便挑
    curl --noproxy '*' http://127.0.0.1:8123/            # 200 = 起来了
    docker exec finfet-viewer wget -qO- http://127.0.0.1/annotations/annotations.json | head -c 200

自定义渲染（three.js/threepipe 之类）只有在"必须改渲染管线"时才值得，标注页用 model-viewer
十分钟能搞定，自己写要几小时且没人维护。

完成判据：浏览器打开容器地址，模型彩色显示、5 个标注点可见、点一个标注相机会飞过去并弹出
说明卡片（截图确认）。

## 陷阱

- **只有 `model_file.binz` 转不了**：缺 `file.binz`（17 KB 场景 JSON）就没有场景图。
- **`.binz` 没有文件头**：`file` 报 `data`、熵 8.0 bit/byte、256 种字节全出现，这是密文的正常
  长相，不要判定为"损坏/随机垃圾"。完整性只能靠 `modelSize` 对数。
- **static key 会轮换**：新 bundle 变了就重新保存页面，不要手工改代码里的 key；
  `decrypt-core.mjs` 的默认值只是兜底。
- **`decrypt.wasm` 也会换**：形状是 bundle 里一段 base64（以 `AGFzbQ` 开头），换版本要重新提取，
  导出符号是刻意混淆的（rickroll 名字），`decrypt-core.mjs` 里已写死这套符号名。
- **贴图不在 binz 里**：走 `/i/models/<uid>/textures` API 另取；无贴图模型的 GLB 里
  `images/textures` 为 0、`maxUVs: 0` 是正常的，不是转换失败。
- **最坑的一条：材质色会被压成一个白材质。** 上游转换器只用贴图做材质去重键，
  无贴图模型的 `osg.Material.Diffuse` 全被丢掉——表现就是"GLB 里只有模型本体，其他资源
  都没有"。修法见步骤 4/`lib/osgjs2gltf.js`，验收看材质数（样例 17）。
- **标注坐标不是 GLB 坐标**：原平台是 Z-up，必须 `(x, y, z) -> (x, z, -y)`；不换系
  标注会飘到模型外。判据：所有锚点落在 GLB bbox 内。
- **标注图片 404**：`annotations.json` 里的 `image` 是相对 `annotations/` 目录的路径，
  页面里引用要拼前缀，否则会去站点根找。
- **标注视点贴脸/太远**：model-viewer 自动算的 fov 是 30°，原平台更广；把半径乘 1.4~1.5
  再喂 `camera-orbit`，别去锁 `min-field-of-view`（会逼出更窄的 fov）。
- **Online3DViewer 不支持标注**（源码里 annotation/hotspot 命中数为 0）：要标注就必须上
  model-viewer 或在自研渲染里实现，别指望通用格式查看器。
- **本地服务用 curl 会被代理劫持**：shell 里有 `HTTP(S)_PROXY` 时，`curl http://127.0.0.1:8000`
  返回 502，加 `--noproxy '*'`。
- **O3DV 的 `class="online_3d_viewer"` 不会自动初始化**：必须显式调
  `OV.Init3DViewerFromUrlList` / `OV.Init3DViewerFromFileList`。
- **材质色默认丢失**：不跑 `postprocess_material.py`，模型会是灰白一片。
- **版权**：`downloadType: no` / `license: null` 的模型，产物仅本地/内网自用，不分发；
  这一点要主动告诉用户，别只字不提。

## 校验

样例（SEMulator3D FinFET，44 mesh / 单材质）实测基准，换模型时结构相同、数字不同：

| 项 | 值 |
|---|---|
| `model_file.binz` | 38,467,477 B（= 页面 modelSize） |
| `file.binz` | 17,240 B |
| 解密后 `file.osgjs` | 260,426 B，`OpenSceneGraph 3.5.6` |
| 解密后 `model_file.bin` | 68,922,700 B |
| GLB | 69,287,172 B，44 mesh，1,252,798 三角面，**17 材质** |
| 标注 | 5 条 + 5 张 128×128 图片，锚点全在 bbox 内 |
| glTF-Validator | 0 errors / 0 warnings / 0 hints |
| 复现性 | 重跑全流程 sha256 一致 |

格式内部细节与排错表见 `references/binz-format.md`、`references/troubleshooting.md`。
