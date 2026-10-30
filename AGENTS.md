# AGENTS.md — binz2glb 项目约定

本文件是给在本仓库（`binz2glb`，即项目 git 根目录）内工作的 agent 的硬性规范。
先读完本文件，再加载 `skills/binz-to-glb/SKILL.md` 执行具体流程。

## 1. 项目是什么

把网页查看器里的加密模型容器 `.binz` 还原成标准 glTF 2.0（GLB）的可复现管线，附带
带标注的离线查看器。三个输入 → 一套产物：

    data/page/<页面>.htm + _files/   (viewer bundle, 取静态 key)
    models/<slug>/source/file.binz        (十几 KB, 场景图 JSON)
    models/<slug>/source/model_file.binz  (数十 MB, 几何二进制)
            ↓ 解密 → 转换 → 后处理 → 标注导出 → 校验
    models/<slug>/finfet.glb + annotations/

## 2. 目录职责

| 路径 | 作用 | 可改? |
|---|---|---|
| `decrypt.mjs` | 取 static key + diterB，调 decrypt.wasm 解密 | 可改，须保持 CLI 不变 |
| `decrypt-core.mjs` | WASM 解密封装（第三方） | 不建议改 |
| `decrypt.wasm` |原平台 viewer 自带的解密模块 | 只读；换版本时整体替换 |
| `osgjs2glb.mjs` | OSGJS 场景 + 几何 → GLB | 可改 |
| `lib/` | osgjs2gltf 转换库（第三方） | 只读 |
| `postprocess_normals.py` | 修补零法线 | 可改 |
| `postprocess_material.py` | 材质色兜底（正常情况由转换器带出） | 可改 |
| `export_annotations.py` | 导出标注（名称/图片/视点/锚点）到 `models/<slug>/annotations/` | 可改 |
| `models/<slug>/` | 每个模型的产物：`meta.json` / `finfet.glb` / `annotations/` / `source/` | 产物可改，`source/` 只读 |
| `viewer/` | Docker 离线查看器（model-viewer + Online3DViewer 静态桥接页） | 可改 |
| `skills/` | 可复用流程技能 | 只增不改坏 |
| `models/*/source/*.binz`、`data/page/` | 用户输入 | **只读，永不修改/移动** |

## 3. 环境约定

- Python：一律用项目根的 uv 虚拟环境，不在系统 Python 里装包。

      uv venv --python 3.14 .venv        # 已存在则跳过
      UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
        uv pip install --python .venv/bin/python numpy

- Node：≥ 18（用到 `DecompressionStream`）；本机实测 v24.18.0。不需要 npm 依赖来解密/转换。
- npm：只用中国大陆镜像 `--registry=https://registry.npmmirror.com`（如装 `gltf-validator`）。
- 网络：本机 shell 导出了 `HTTP(S)_PROXY=localhost:7890`。访问本机服务必须
  `curl --noproxy '*'`，否则本地 8123 会返回 502。

## 4. HARDLINE 规则

1. **输入只读**：`*.binz`、`web-save/` 里的页面快照都不许改写。所有产物写到 `out/`。
2. **必须校验**：任何 GLB 交付前跑 Khronos glTF-Validator，要求 `errors=0 warnings=0`；
   数字照抄，不许写"应该没问题"。
3. **必须对数**：转换后三角面/顶点数要与页面元数据 `faceCount` / `vertexCount` 对照，
   差异 > 1% 视为失败并停下排查（正常差异来自退化面被丢弃）。材质数必须等于源里
   `osg.Material` 的种类数（样例 17）——只剩 1 个白材质就说明材质色被压平了。
3b. **标注不能丢**：只要源模型有 annotation/hotspot，就必须导出 `annotations/annotations.json`
   + 图片，并在查看器里能点开；锚点必须落在模型 bbox 内。
4. **不许把密钥写死进代码**：static key 会随 viewer 版本轮换，只能从页面 bundle 里现场提取；
   只有 `decrypt-core.mjs` 里的默认值可作兜底。
5. **不加后台服务**：不写 systemd unit、不装常驻进程、不改 `/etc`。需要长期服务先问用户。
   查看器用 `docker compose up -d --build`（见 `viewer/README.md`），不要另起 python
   http.server 之类的东西当长期方案。
5b. **不自己写渲染器**：标注页用 `google/model-viewer`，通用格式页用 `kovacsv/Online3DViewer`，
   只在两者都不满足时才考虑 three.js/threepipe，并先说明理由。
6. **不改仓库外的东西**：`models/*/source/*.binz`、`data/page/` 是输入，只读；`viewer/lib/`、
   `decrypt.wasm` 是第三方件，只替换不改写。
7. **脚本里不写绝对路径**：用相对路径 + CLI 参数；路径示例写成占位符（如 `<项目根>`）。
8. **别提交大产物**：若本目录纳入 git，`out/`、`*.glb`、`node_modules/` 应进 `.gitignore`。
9. **版权**：原平台上 `downloadType: no` / `license: null` 的模型，产物仅限本地/内网自用，
   不再分发；转述这一点给用户，别省略。

## 5. 一次改动的验收清单

- [ ] `node decrypt.mjs ...` 输出 `静态 key: <40 hex>`、两个产物大小合理
- [ ] `node osgjs2glb.mjs ...` 打印的三角面数与页面 `faceCount` 差异 < 1%
- [ ] `postprocess_normals.py` 报出的零法线数量与修改前一致（幂等：二次运行为 0）
- [ ] glTF-Validator `errors=0 warnings=0`
- [ ] 用浏览器实际打开渲染一次（不是"应该能打开"）
- [ ] 报告只写命令与实际数字，不写过程叙事

## 6. 汇报格式

    改了什么：<文件列表 + 一句话>
    实跑输出：<关键命令行 + 数字>
    校验：validator 0/0；面数 X/Y（差 Z%）
    未做/风险：<honest 列表>

## 7. 技能索引

| 技能 | 何时加载 |
|---|---|
| `skills/binz-to-glb/SKILL.md` | 任何"把原平台模型转成 glb/obj"的请求 |
| `skills/binz-to-glb/references/binz-format.md` | 需要理解格式内部、换 key/wasm、调试解密 |
| `skills/binz-to-glb/references/troubleshooting.md` | 解密/转换/校验报错时 |
