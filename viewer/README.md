# 离线 3D 查看器（Docker）

一个 `nginx:alpine` 容器，里面装两套现成开源查看器，没有任何自研渲染代码：

| 路径 | 用什么 | 作用 |
|---|---|---|
| `/` | [google/model-viewer](https://github.com/google/model-viewer) 4.4.0（8.3k★，Apache-2.0/BSD-3） | 带标注的主视图：5 个 hotspot + 点击飞行 + 说明卡片 |
| `/o3dv/` | [kovacsv/Online3DViewer](https://github.com/kovacsv/Online3DViewer) 0.18.0（3.7k★，MIT） | 通用格式查看（glb/gltf/obj/stl/ply/3mf/step…），可拖入本地文件 |

`viewer/site/` 只是把 `models/<slug>/annotations/annotations.json` 桥接成 model-viewer 的 hotspot
（约 100 行 JS），模型、标注、渲染能力都来自上面两个项目。

## 起停

```bash
cd <仓库根>
docker compose up -d --build      # 首次构建约 10 秒（上下文 ~78 MB）
curl --noproxy '*' -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8123/
docker compose logs -f            # nginx 日志
docker compose down               # 停掉并删除容器（镜像保留）
```

内网其他机器访问：把 `docker-compose.yml` 里的 `"8123:80"` 换成 `"0.0.0.0:8123:80"`
（默认已经绑全地址），然后 `http://<机器IP>:8123/`。

需要开机自启再打开 compose 里的 `restart: unless-stopped`；默认不加，符合"不擅自加常驻"。

## 为什么是这两个，而不是别的

选型只看了"离线 + 可容器化 + 真有人维护"的：

| 项目 | ★ | 许可 | 标注支持 | Docker | 结论 |
|---|---|---|---|---|---|
| google/model-viewer | 8,302 | Apache-2.0 | **原生 hotspot** | 无官方镜像，nginx 一行即可 | **选它做标注页** |
| kovacsv/Online3DViewer | 3,750 | MIT | 无（源码里 annotation 命中 0） | 同上 | **选它做通用格式页** |
| donmccurdy/three-gltf-viewer | 2,480 | MIT | 无 | 无 | 只是拖放预览器 |
| KhronosGroup/glTF-Sample-Viewer | 1,482 | Apache-2.0 | 无 | 无 | 参考实现，界面不适合展示 |
| repalash/threepipe | 943 | Apache-2.0 | 需自己实现 | 无 | 是引擎/工具包，不是成品查看器 |
| xeokit/xeokit-sdk | 948 | AGPL-3.0 | 有（BIM 方向） | 无 | AGPL，且面向 IFC/BIM |
| prathamps/Sculpt | 3 | MIT | — | 无 | 作者个人玩具，不适合依赖 |

自动化校验（可重跑）：`curl -s https://api.github.com/repos/<owner>/<repo> | jq '.stargazers_count'`。

## 换模型/换标注

1. 用仓库根管线生成 `models/<slug>/finfet.glb` 与 `models/<slug>/annotations/annotations.json`
2. 改 `viewer/site/index.html` 的 `src=`、`viewer/site/app.js` 里的 annotations 路径，
   以及 `viewer/Dockerfile` 的 `COPY models/<slug>/…` 三处
3. `docker compose up -d --build`

标注 JSON 结构（`export_annotations.py` 产出）：

```json
{ "annotations": [ { "uid": "...", "name": "...", "content": "",
    "image": "images/<uid>.jpeg",
    "position": [x, y, z], "target": [x, y, z], "eye": [x, y, z] } ] }
```

`position` 是模型坐标系（Y-up）里的锚点；`eye`/`target` 会换算成 model-viewer 的
`camera-orbit` / `camera-target`。半径乘了 1.45，因为 model-viewer 自动 fov 是 30°，
比原平台默认更窄。
