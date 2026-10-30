# 排错表

按"症状 → 原因 → 处理"查。所有症状都来自本项目的真实失败/成功记录。

## 解密阶段

| 症状 | 原因 | 处理 |
|---|---|---|
| `ERR WASM abort` | static key 错（用了别的 bundle 的 key / 手抄错）、diterB 取错、wasm 版本与 bundle 不配套 | 确认 key 是从**本次页面**的 bundle 里提取（`C04p` 形态）；diterB 必须是同一页面 `files[0].p[0].b` |
| `页面里找不到 files[0].p[0].b (diterB)` | 保存的是普通网页而不是模型的 viewer 快照，或页面被压缩成 mhtml 后正则失配 | 重新"另存为 网页，完成"；确认 `.htm` 里有 `"files": [{"uid": ...` |
| `viewer bundle 里找不到 40 位静态 key` | 只存了 `.htm`，`xxx_files/` 目录丢了，或 bundle 未下载完 | 检查 `xxx_files/` 里有 20+ 个 `-v2.js.download`；重新保存页面 |
| `WASM exports missing (decrypt.wasm outdated?)` | wasm 换版本，导出符号名变了 | 按 `references/binz-format.md` §4 重新从 bundle 提取 wasm |
| `decompressed gzip not supported` / `DecompressionStream is not defined` | Node < 18 | 升级 Node（实测 v24.18.0） |
| 解密输出 `model_file.bin` 以 `00 01 02 03…` 开头 | **正常**，这不是乱码 | 用 `file.osgjs` 是否合法 JSON + 三角面数对数来判断成功 |

## 转换阶段

| 症状 | 原因 | 处理 |
|---|---|---|
| `file.osgjs missing` / `model_file.bin missing` | 只下了一个 `.binz` | 补齐 `file.binz`（约 17 KB） |
| `No triangle geometries found in osgjs` | osgjs 与 bin 不配套（不同模型的组合），或解密失败 | 用同一 `files[0]` 下的两个 binz |
| 三角面数远小于页面 `faceCount` | 下载被截断 / 密钥错导致部分块解错 | 比对 `modelSize`；重下 |
| 三角面数略小（< 1%） | 退化三角形被丢弃，正常 | 无需处理，报告里注明差值 |
| GLB 里 `images: 0`、`maxUVs: 0` | 该模型本来就没贴图/没 UV | 正常；贴图要走 `/i/models/<uid>/textures` |
| 模型一片灰白、材质数只有 1 | 转换器的材质去重键只看贴图，17 种 `osg.Material.Diffuse` 被压成一个 | 用本项目打过补丁的 `lib/osgjs2gltf.js`（键含 baseColorFactor）；`postprocess_material.py` 只在全白时兜底 |
| 标注点飘在模型外 | 坐标没换系（查看器是 Z-up → GLB Y-up） | `(x, y, z) -> (x, z, -y)`，并用 bbox 自检 |
| 标注缩略图 404 | `annotations.json.image` 是相对 `annotations/` 的路径 | 页面里拼 `annotations/` 前缀 |
| 点标注后镜头贴脸 | model-viewer 自动 fov 30°，原平台更广 | 半径乘 ~1.45；别锁 `min-field-of-view` |

## 校验阶段

| 症状 | 原因 | 处理 |
|---|---|---|
| `ACCESSOR_VECTOR3_NON_UNIT`（大量） | 源数据有零长度法线（样例 698 个） | 跑 `postprocess_normals.py`，重跑应为 0 |
| 校验报 buffer 长度不符 | 手工改过 JSON chunk 但没重新 padding | 用 `postprocess_material.py` 那条脚本改（它重排 GLB 容器） |
| 校验通过但渲染黑斑 | 只跑了材质、没跑法线 | 两步都跑，顺序：法线 → 材质 |

校验片段（`gltf-validator` 从 npmmirror 装）：

```js
// validate.mjs —— node validate.mjs out/final.glb
import fs from 'node:fs';
import validator from 'gltf-validator';
const data = new Uint8Array(fs.readFileSync(process.argv[2]));
const r = await validator.validateBytes(data, { maxIssues: 200, uri: process.argv[2] });
console.log('errors', r.issues.numErrors, 'warnings', r.issues.numWarnings,
            'tris', r.info.totalTriangleCount, 'meshes', r.info.drawCallCount);
```

期望：`errors 0 warnings 0`，`tris` 与转换步骤打印的一致。

## 查看 / 部署阶段

| 症状 | 原因 | 处理 |
|---|---|---|
| `curl http://127.0.0.1:8000` 返回 502 | shell 里的 `HTTP(S)_PROXY` 把本地请求也代理了 | `curl --noproxy '*'` |
| 双击 `index.html` 打不开模型 | `file://` 下 fetch 被浏览器拦截 | `python -m http.server 8000 --bind 0.0.0.0` 走 HTTP |
| 页面空白、`document.querySelector('canvas')` 为 null | 只写了 `<div class="online_3d_viewer">` 却没有触发初始化 | 显式调用 `OV.Init3DViewerFromUrlList` / `OV.Init3DViewerFromFileList`（见 SKILL.md 步骤 7） |
| 环境贴图把背景铺满、看不见模型 | `EnvironmentSettings(urls, true)` 的第二参开启背景 | 传 `false`，只用它做光照 |
| 中文按钮显示成方块 | 系统缺中文字体（headless 环境常见） | 装中文字体；或按钮改英文 |
