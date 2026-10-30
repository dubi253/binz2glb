# `.binz` 格式内部（实测 + 对照 viewer 代码）

本文件只写经过实测验证的事实，供换模型、换 查看器版本、排查解密失败时使用。

## 1. 容器分两层

| 层 | 内容 | 实测值（SEMulator3D FinFET） |
|---|---|---|
| 外层加密 | 全局 40 位 hex static key × 每模型 diterB 混合出密钥流 | key `d34c9cf6…8c75`；diterB 552 个 base64 字符 = 412 B |
| 内层压缩 | wasm 解密的同时解压，**明文比密文大** | 38,467,477 B → 68,922,700 B（1.79×） |

因此：

- `.binz` **没有魔数、没有文件头**，熵 8.0 bit/byte、256 种字节齐全，`file` 只会说 `data`。
  这是密文的正常长相，不能据此判定"文件损坏/是随机垃圾"。
- 完整性唯一可靠的判据是页面 JSON 的 `files[0].modelSize` 与实际字节数相等。
- 部分模型的解密输出以 `1F 8B` 开头（gzip），要再 gunzip（`decrypt-core.mjs` 已处理）。
  本样例 **不是** gzip。

## 2. 两个文件各是什么

- `file.binz`（约 17 KB）→ `file.osgjs`：**场景图 JSON**。顶层是
  `{"Generator": "OpenSceneGraph 3.5.6", "Version": 9, "osg.Node": {...}}`，
  内含节点树、`osg.Geometry`、`osg.StateSet`/`osg.Material`（材质的 `Diffuse`
  就藏在这里，转换器不会自动带到 glTF）。
- `model_file.binz`（数十 MB）→ `model_file.bin`：**几何二进制**，按 geometry 名索引。
  顶点属性用 varint + zigzag + delta 编码，再按 quantize 参数反量化；法线/切线可能走
  spherical 解码（见 `lib/osg-codec.js` 的 `decodeVarint` / `deltaDecodeInPlace` /
  `dequantize` / `decodeSpherical`）。
- `model_file_wireframe.binz`（可选）→ 线框专用几何，转换时可以不给。

**两个文件必须成对**：只有 `model_file.binz` 时拿不到场景图，转换器第一步就报
`file.osgjs missing`。

## 3. decrypt.wasm 接口

导出符号被刻意混淆成 rickroll 的 base64 片段，签名与用途：

| 导出名（前缀） | 签名 | 用途 |
|---|---|---|
| `heSBnb29kYnll…` | `(len) -> ptr` | 分配输入缓冲 |
| `mV2ZXIgZ29ubmE…` | `() -> void` | reset |
| `Umlja1JvbGxlZDRV` | `(seed, 40) -> ptr` | 申请 40 B 的 key 写入口，返回偏移 |
| `dmVyIGdvbm5hIH…` | `(len) -> ptr` | 分配 diterB 缓冲 |
| `GRlc2VydCB5b3U…` | `(flag) -> i32` | 主流程：`1`=喂输入块，`0`=继续取输出 |
| `FrZSB5b3UgY3J5…` | `() -> void` | advance 到下一输出块 |
| `bGwgYSBsaWUgYW5k…` | `() -> i32` | 当前输出块长度 |
| `TmV2ZXIgZ29ubmEg…` | `() -> i32` | 当前输出块起始偏移 |

宿主必须提供 `env.memory`、`sbrk`、`time`、`gettimeofday`、`abort`（JS 侧另有
`__lock`/`__unlock`/`setjmp`/`__cxa_atexit` 空实现）。内存初始页数 =
`262144 + ((dataSize + 65535) >> 16 << 16)` 再右移 16，上限 512 MB。

调用顺序：`reset` → 把 10 组 4 位 hex（由 seed 与 key 混合、再与全集 XOR 得到）写成
ASCII 写进 `rickRolled()` 返回的偏移 → `allocDiterB` + 写入 diterB → `process(0)` 初始化 →
按 **10240 B** 切块：`allocInput` 写入 → `process(1)` → 循环 `getStart`/`getInfo`/`advance`/
`process(0)` 直到返回 0。

## 4. 重新提取 wasm / key

- **wasm**：在页面保存下来的 `.js` bundle 里找以 `AGFzbQ` 开头的长 base64 串（在引号内、
  含 `\n` 转义）。去掉转义与空白后 base64 解码。本样例来自一个 368,440 B 的 bundle，
  blob 347,262 字符 → 253,767 B 的合法 wasm（`\0asm\1\0\0\0`）。
- **static key**：在 bundle 里以 `C04p:t=>{"use strict";t.exports="<40 hex>"}` 出现，
  这是当前版本的形态；其余兜底形态见 `decrypt.mjs` 的 `keyPatterns`。
- **diterB**：页面模型 JSON 中 `files[0].p[0].b`（`p` 可能是数组，取 `[0]`）。

## 4.5 材质色与标注藏在哪（"资源文件缺失"的答案）

| 想要的东西 | 数据位置 | 注意 |
|---|---|---|
| 每个材料层的颜色 | osgjs 里每个 `osg.Geometry` 内联的 `StateSet.osg.StateSet.AttributeList[].osg.Material.Diffuse` | 样例 17 个材质（Cu / TaN-Copy / Ta.001 / W / TiN / TiAl / Ti / SiGe / SiC / Si Xtal / Si3N4 PECVD,MLD / HfOx / SiO2 TEOS,PECVD,HTO,HDP）。上游转换器会整块丢掉 |
| 材质贴图 | `/i/models/<uid>/textures?optimized=1` | 本样例 `count: 0`：模型没有任何材质贴图，`images: 0`/`maxUVs: 0` 是正常的 |
| 标注文字与图片 | 页面缓存 `/i/models/<uid>/hotspots?optimized=1` | 每条含 name / content.raw / images[].url / eye / target / position |
| 标注锚点 | 模型 JSON 的 `hotspot.hotspots[]` | geometryUid + indices + barycentricWeights + localPosition；`localPosition` 与 API 的 `position` 相等 |
| 标注坐标换系 | — | 查看器是 Z-up → GLB 用 `(x, y, z) -> (x, z, -y)`；样例两点正好落在 z=87 的面上，可自检 |

## 5. 解密成功的判定（别用头字节判断）

`model_file.bin` **正常就以 `00 01 02 03 04 05 …` 开头**（缓冲区/索引结构），
不要当成"乱码=密钥错"。可靠判据只有两条：

1. `file.osgjs` 是合法 JSON 且 `Generator` 字段是 `OpenSceneGraph`；
2. 转换出的三角面数与页面 `faceCount` 相差 < 1%。

密钥错时的典型表现是解密阶段直接 `WASM abort`（不是输出乱码）。
