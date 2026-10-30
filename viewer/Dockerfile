# 离线 3D 查看器镜像（model-viewer 带标注页）
# 构建上下文 = 仓库根目录：
#   docker build -f viewer/Dockerfile -t finfet-viewer:1 .
#
# 模型文件默认**不打包**（models/ 被 .gitignore 排除），有两种用法：
#   1) 运行时挂载：-v /srv/models:/usr/share/nginx/html/models:ro
#   2) 构建时下载：--build-arg MODEL_URL=<glb 的 http(s) 地址>
# models/*/source/*.binz 由 .dockerignore 排除，永不会进镜像。
FROM nginx:alpine

ARG MODEL_URL=""

# 页面与前端依赖
COPY viewer/site/ /usr/share/nginx/html/
COPY viewer/lib/  /usr/share/nginx/html/lib/

# 模型目录结构（仓库里至少有一个 models/.gitkeep，保证 COPY 不失败）
COPY models/ /usr/share/nginx/html/models/
RUN mkdir -p /usr/share/nginx/html/models/finfet/annotations \
    && if [ -n "$MODEL_URL" ]; then \
         wget -q -O /usr/share/nginx/html/models/finfet/finfet.glb "$MODEL_URL" \
         && echo "model: $(wc -c < /usr/share/nginx/html/models/finfet/finfet.glb) bytes"; \
       else \
         echo "model: 未内置，运行时挂载 models/ 或重建时传 --build-arg MODEL_URL"; \
       fi

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
