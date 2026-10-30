# 3D 模型管线 — 网页查看器模型 → 标准 glTF → 离线查看

把只存在于网页查看器里的 3D 模型（加密 `.binz` 是典型）还原成标准 glTF 2.0：
解密 → 转换 → 补齐材质色与标注资源 → 校验 → 容器化离线查看器。

不覆盖：官方开放下载的模型（直接下原始 glb/fbx）、只想要截图、付费/私有模型的绕过。

```
.
├── decrypt.mjs              # 解密 .binz（自动取 static key + diterB）
├── osgjs2glb.mjs            # OSGJS 场景 + 几何 → GLB
├── postprocess_normals.py   # 零法线修补
├── postprocess_material.py  # 材质色兜底（正常由转换器带出）
├── export_annotations.py    # 导出 annotation/hotspot（名称/图片/视点/锚点）
├── validate.mjs             # Khronos glTF-Validator
├── lib/                     # osgjs2gltf 转换库（含材质色补丁）
├── models/<slug>/           # 每个模型的产物与元数据，见 models/finfet/
├── viewer/                  # Docker 离线查看器（model-viewer + Online3DViewer）
├── skills/                  # 项目技能：完整流程 + 格式细节 + 排错
├── AGENTS.md                # 本仓库的 agent 硬性规范
└── docker-compose.yml
```

## 快速开始

```bash
# 依赖：Node ≥ 18；Python 3.14 虚拟环境（uv，清华源）
uv venv --python 3.14 .venv
UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
  uv pip install --python .venv/bin/python numpy
npm install --registry=https://registry.npmmirror.com gltf-validator

# 看模型（需要 models/<slug>/finfet.glb，见"从 binz 重新生成"）
docker compose up -d --build
#   http://127.0.0.1:8123/        带标注的主视图
```

## 从 binz 重新生成

前提：把模型页面"另存为 网页，完成"，得到 `xxx.htm` 与 `xxx_files/`（含 viewer 的 `.js`
bundle，static key 藏在里面），放到 `data/page/`（已被 `.gitignore` 排除）；再下载页面上
`files[0]` 的两个 `.binz` 到 `models/<slug>/source/`。

```bash
# 1 解密（key 与 diterB 都从页面快照里自动取）
node decrypt.mjs "data/page/<页面>.htm" models/<slug>/source/file.binz \
                 models/<slug>/source/model_file.binz out

# 2 转 GLB
node osgjs2glb.mjs out out/raw.glb

# 3 后处理：零法线 + 材质色兜底
python postprocess_normals.py  out/raw.glb  out/norm.glb
python postprocess_material.py out/norm.glb out/final.glb

# 4 标注（没有标注的模型跳过）
python export_annotations.py "data/page/<页面>.htm" models/<slug>/annotations

# 5 校验：必须 errors=0 warnings=0
node validate.mjs out/final.glb

# 6 归档
mv out/final.glb models/<slug>/finfet.glb
```

本仓库自带一次完整跑通的样例：`models/finfet/`（17 种材料的芯片工艺模型，1,252,798 三角面、
5 条标注，校验 0 error）。数字基准见 `models/finfet/meta.json`。

## 关键事实

- **无贴图模型的外观全在 `osg.Material.Diffuse` 里。** 上游转换器只用贴图做材质去重键，
  会把 N 种材料压成一个白材质——表现就是"GLB 里只有模型本体"。本仓库的
  `lib/osgjs2gltf.js` 已修（材质键含 baseColorFactor），验收看材质数。
- **标注在页面快照里有两份数据**：`/i/models/<uid>/hotspots?optimized=1` 的缓存（名称、图片、
  eye/target）与模型 JSON 的 `hotspot.hotspots[]`（geometryUid、indices、重心坐标）。
- **坐标系要换**：原平台是 Z-up，写进 GLB 用 `(x, y, z) -> (x, z, -y)`。
- **`.binz` 没有文件头**：熵 8.0、`file` 只报 `data`，是密文的正常长相；完整性只能靠页面
  `files[0].modelSize` 对数。
- **static key 会轮换、`decrypt.wasm` 会换版本**：key 现场从 bundle 提取
  （`C04p:t=>{"use strict";t.exports="<40 位 hex>"}`），wasm 是 bundle 里以 `AGFzbQ` 开头的长
  base64；本仓库附的 wasm 是本次提取的版本。

## 模型与版权的约定

`models/*/*.glb`、`models/*/source/*.binz` 默认**不入库**（体积 + 第三方版权）。
提交到 GitHub 前请确认你有权分发对应模型；本样例源站为 `downloadType: no` / `license: null`，
产物仅限本地/内网自用。需要入库时用 Git LFS 或 `git add -f`，见 `models/finfet/README.md`。

## 文档

- `AGENTS.md` — 在本仓库工作的 agent 硬性规范（输入只读、必须对数、禁止写死密钥等）
- `skills/binz-to-glb/SKILL.md` — 完整流程技能；`references/` 有格式细节与排错表
- `viewer/README.md` — 查看器部署与选型对比（为什么是 model-viewer + Online3DViewer）

## 许可

本仓库代码 MIT。随仓库分发的第三方组件各自保留许可：`lib/osgjs2gltf.js` 等来自
上游开源 ripper 项目（MIT，版权声明随文件保留）；
`viewer/lib/model-viewer.min.js` 为 Google model-viewer（Apache-2.0 / BSD-3-Clause）；
`decrypt.wasm` 由网页查看器自带，仅作互操作之用。
