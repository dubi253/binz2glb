#!/usr/bin/env python3
"""把一个模型 + 它的标注发布到自托管 Sculpt（https://github.com/prathamps/Sculpt）。

只做数据搬运：注册/登录 → 建项目 → 上传 GLB（作为 MODEL 的 modelProxy）→
按 annotations.json 逐条建带 3D 锚点的评论。不涉及任何前端代码。

Sculpt 的 ModelAnchor 结构（docs/openapi.yaml）正好对上我们导出的标注：
    point  = annotations[i].position     （模型坐标系）
    normal = [0, 1, 0]
    camera = { position: eye, target: target }

用法:
    python publish_to_sculpt.py \
        --api http://127.0.0.1:3001 \
        --email you@example.com --password 'password' \
        --project "FinFET" \
        --glb  models/finfet/finfet.glb \
        --annotations models/finfet/annotations/annotations.json
"""
import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid
from http.cookiejar import CookieJar


class Client:
    def __init__(self, api, verbose=False):
        self.api = api.rstrip("/")
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.verbose = verbose

    def _request(self, method, path, data=None, headers=None, raw=False):
        url = f"{self.api}{path}"
        req = urllib.request.Request(url, data=data, method=method)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with self.opener.open(req, timeout=300) as r:
                body = r.read()
                if self.verbose:
                    print(f"  {method} {path} -> {r.status} ({len(body)} B)")
                return (body, r.status) if raw else (json.loads(body) if body else None, r.status)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            if e.code in (409,) and "already" in detail.lower():
                return None, e.code
            raise SystemExit(f"{method} {path} -> HTTP {e.code}: {detail}")

    def json(self, method, path, payload=None):
        headers = {"Content-Type": "application/json"}
        data = json.dumps(payload).encode() if payload is not None else None
        return self._request(method, path, data, headers)

    def multipart(self, path, files, fields):
        """files: [(field, filename, content_type, bytes)], fields: dict"""
        boundary = "----" + uuid.uuid4().hex
        out = bytearray()
        for name, value in fields.items():
            out += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        for name, filename, ctype, blob in files:
            out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
                    f"filename=\"{filename}\"\r\nContent-Type: {ctype}\r\n\r\n").encode()
            out += blob + b"\r\n"
        out += f"--{boundary}--\r\n".encode()
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        return self._request("POST", path, bytes(out), headers)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:3001")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--name", default="Pipeline")
    ap.add_argument("--project", default="FinFET")
    ap.add_argument("--glb", required=True)
    ap.add_argument("--annotations", required=True)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    c = Client(a.api, a.verbose)

    _, status = c.json("POST", "/api/auth/register",
                       {"email": a.email, "password": a.password, "name": a.name})
    print("register:", "created" if status == 201 else "already exists")
    _, status = c.json("POST", "/api/auth/login", {"email": a.email, "password": a.password})
    print("login:", status)

    projects, _ = c.json("GET", "/api/projects?page=1&pageSize=100")
    items = projects.get("items", []) if isinstance(projects, dict) else projects
    proj = next((p for p in items if p.get("name") == a.project), None)
    if proj:
        print("project:", proj["id"], "(reused)")
    else:
        proj, _ = c.json("POST", "/api/projects", {"name": a.project})
        print("project:", proj["id"], "(created)")

    media, _ = c.json("GET", f"/api/projects/{proj['id']}/images")
    media = media.get("items", media) if isinstance(media, dict) else media
    target = next((m for m in media if m.get("name") == os.path.basename(a.glb)), None)
    if target:
        print("model:", target["id"], "(already uploaded)")
    else:
        blob = open(a.glb, "rb").read()
        ctype = mimetypes.guess_type(a.glb)[0] or "model/gltf-binary"
        created, _ = c.multipart(
            f"/api/projects/{proj['id']}/images",
            files=[("images", os.path.basename(a.glb), "model/gltf-binary", blob),
                   ("modelProxies", os.path.basename(a.glb), ctype, blob)],
            fields={"filesMeta": json.dumps([{"hasModelProxy": True, "hasThumbnail": False}])},
        )
        target = (created or [None])[0]
        if not target:
            raise SystemExit("上传失败：接口没有返回 media")
        print("model:", target["id"], f"({len(blob)} B uploaded)")

    version = target.get("latestVersion") or {}
    version_id = version.get("id")
    if not version_id:
        versions, _ = c.json("GET", f"/api/images/{target['id']}/versions")
        version_id = (versions if isinstance(versions, list) else versions.get("items", []))[0]["id"]
    print("version:", version_id, "| mediaType:", version.get("mediaType"))

    ann = json.load(open(a.annotations))["annotations"]
    existing, _ = c.json("GET", f"/api/images/versions/{version_id}/comments?page=1&pageSize=100")
    existing = existing.get("items", existing) if isinstance(existing, dict) else existing
    have = {x.get("content") for x in existing}
    posted = 0
    for x in ann:
        if x["name"] in have:
            continue
        c.json("POST", f"/api/images/versions/{version_id}/comments", {
            "content": x["name"],
            "modelAnchor": {
                "point": x["position"],
                "normal": [0, 1, 0],
                "camera": {"position": x["eye"], "target": x["target"]},
            },
        })
        posted += 1
    print(f"annotations: {posted} posted / {len(ann)} total (existing {len(have)})")
    print(f"open: {a.api.replace(':3001', ':3000')}/projects/{proj['id']}")


if __name__ == "__main__":
    main()
