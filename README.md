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

# 看模型：直接用 CI 构建好的镜像（本地不构建），模型目录挂载进去
docker compose pull && docker compose up -d
#   http://127.0.0.1:8123/        带标注的主视图
# 前提：models/<slug>/finfet.glb 在本地，见"从 binz 重新生成"
```

## 内网部署（镜像已经在内网机器上）

镜像 = `nginx:alpine` + 静态文件，运行时不需要网络、不需要 Node/Python、也不需要 `.binz`。
所需镜像的完整清单（两条部署路径、上游/自建、构建期/运行时）见 [`IMAGES.txt`](IMAGES.txt)。

### 0. 只在构建机上：docker 走 HTTPS 代理

`docker pull` 是 daemon 的行为，shell 里的 `HTTP_PROXY` 不生效，要配到 daemon：

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf >/dev/null <<'EOF'
[Service]
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
Environment="NO_PROXY=localhost,127.0.0.1,::1,.local"
EOF
sudo systemctl daemon-reload && sudo systemctl restart docker
docker info | grep -i proxy          # 确认生效
docker pull nginx:alpine
```

`docker build` 里的下载（npm/apt）走客户端代理配置 `~/.docker/config.json`：

```json
{ "proxies": { "default": {
    "httpProxy": "http://127.0.0.1:7890",
    "httpsProxy": "http://127.0.0.1:7890",
    "noProxy": "localhost,127.0.0.1"
} } }
```

本项目的镜像构建只做 `COPY`，不联网（只要 `nginx:alpine` 已在本地），所以构建阶段其实用不到代理；
需要代理的是拉基础镜像，以及构建第三方栈（如 Sculpt 的 Node 镜像）。

### 1. 搬运镜像

```bash
# 构建机 / 有网的机器：拉 CI 产物
docker pull ghcr.io/dubi253/binz2glb:latest
docker save ghcr.io/dubi253/binz2glb:latest | gzip -9 > viewer.tar.gz   # 约 40 MB

# 内网机
gunzip -c viewer.tar.gz | docker load
docker run -d --name finfet-viewer -p 8123:80 \
  -v /srv/models:/usr/share/nginx/html/models:ro \
  ghcr.io/dubi253/binz2glb:latest
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8123/      # 200
```

镜像由 GitHub Actions 构建（`.github/workflows/image.yml`），本地不需要 `docker build`。

### 2. 导入模型文件（模型不进 git）

模型目录约定（`models/` 已被 `.gitignore` 排除，需自己拷）：

```
models/<slug>/
├── finfet.glb                 # 转换产物，唯一运行必需的文件
├── annotations/annotations.json + images/   # 有标注时
└── source/                    # 加密 binz 源文件，运行时用不到，不必拷
```

三种导入方式，按场景选：

**A. 内置进镜像（不想挂载时）** —— 模型不在 git 里，所以内置只能二选一：

- 手动触发 Actions（`workflow_dispatch`）时填 `model_url`（glb 的可下载地址），CI 会
  `--build-arg MODEL_URL=` 把它下载进镜像，产出 `sha-<短哈希>` 那个 tag；
- 或在有网的机器上本地 `docker build -f viewer/Dockerfile --build-arg MODEL_URL=<url> .`
  （不推荐，等于绕回本地构建）。

`source/*.binz` 被 `.dockerignore` 排除，不会进镜像（省 38 MB）。

**B. 运行时挂载（推荐，换模型不用重建镜像）** —— 在 `docker-compose.yml` 给服务加一行：

```yaml
    volumes:
      - /srv/models:/usr/share/nginx/html/models:ro
```

宿主机目录保持 `<host>/<slug>/finfet.glb` 结构即可；往里放新模型后刷新页面就生效
（页面路径仍是 `models/finfet/...`，换 slug 需要同步改页面，见第 3 节）。

**C. 临时验证** —— 不重建、不挂载，直接塞进运行中的容器：

```bash
docker cp models/finfet/finfet.glb finfet-viewer:/usr/share/nginx/html/models/finfet/finfet.glb
docker cp models/finfet/annotations finfet-viewer:/usr/share/nginx/html/models/finfet/
```

`docker cp` 的内容随容器删除而消失，只适合调试。

### 3. CI 构建的镜像（GitHub Actions）

`.github/workflows/image.yml`：push 到 `master`、打 `v*` tag、或手动 `workflow_dispatch` 时，
在 GitHub 的 runner 上构建 `viewer/Dockerfile` 并推到本仓库的 GHCR 镜像：

```
ghcr.io/<owner>/<repo>:latest       # master 分支
ghcr.io/<owner>/<repo>:master
ghcr.io/<owner>/<repo>:sha-<短哈希>
ghcr.io/<owner>/<repo>:<版本号>      # 打 v1.2.3 tag 时
```

workflow 里做了三件事：Buildx 构建（带 gha 层缓存）→ 推到 GHCR（用 `GITHUB_TOKEN`，
权限 `packages: write`）→ 起容器冒烟测试 `/`、`/app.js`、`/lib/model-viewer.min.js` 是否 200。

拉取：

```bash
docker pull ghcr.io/<owner>/<repo>:latest
```

注意两点：

- **GHCR 包默认私有**。要让内网机匿名 `docker pull`，去 GitHub → 仓库右侧 Packages →
  该包 → Package settings → Change visibility → Public；保持私有则内网机先
  `echo $TOKEN | docker login ghcr.io -u <user> --password-stdin`。
- **CI 镜像不含模型**（`models/` 不入库）。两种补齐方式：运行时 `-v /srv/models:...` 挂载，
  或手动触发 workflow 时填 `model_url`，构建阶段用 `--build-arg MODEL_URL=` 把 glb 下载进镜像。

### 4. 多模型（当前限制）

现在是单模型静态页：`viewer/site/index.html` 的 `src=` 和 `viewer/site/app.js` 里的
annotations 路径都写死 `models/finfet/`。要多模型库式浏览有两个方向：

- 每模型一个页面 + 一个索引页（纯静态，`models.json` 驱动）；
- 换成自带模型库的查看器（Sculpt：`publish_to_sculpt.py` 可把模型和带相机的标注直接发布进去）。


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
