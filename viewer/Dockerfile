# 离线 3D 查看器镜像：model-viewer（带标注）+ Online3DViewer（通用格式）
# 构建上下文 = 仓库根目录：
#   docker build -f viewer/Dockerfile -t finfet-viewer:1 .
# models/*/source/*.binz 由 .dockerignore 排除，不进镜像。
FROM nginx:alpine

# 页面与前端依赖
COPY viewer/site/ /usr/share/nginx/html/
COPY viewer/lib/  /usr/share/nginx/html/lib/

# 模型与资源（保持 models/<name>/ 结构）
COPY models/finfet/finfet.glb    /usr/share/nginx/html/models/finfet/finfet.glb
COPY models/finfet/annotations/  /usr/share/nginx/html/models/finfet/annotations/


EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
