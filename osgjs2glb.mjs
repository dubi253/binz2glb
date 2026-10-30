#!/usr/bin/env node
// 解密后的 file.osgjs + model_file.bin -> GLB
// 用法: node osgjs2glb.mjs <解密目录> <out.glb>
import fs from 'node:fs';
import path from 'node:path';
import { convertOsgjsToGlbFromFiles } from './lib/osgjs2gltf.js';

const [dir, outPath] = process.argv.slice(2);
if (!dir || !outPath) {
  console.error('用法: node osgjs2glb.mjs <解密目录> <out.glb>');
  process.exit(1);
}
const files = {};
for (const name of fs.readdirSync(dir)) {
  if (name === 'file.osgjs' || name.startsWith('model_file') || /^animations\//.test(name)) {
    files[name] = new Uint8Array(fs.readFileSync(path.join(dir, name)));
  }
}
if (!files['file.osgjs'] || !files['model_file.bin']) {
  throw new Error('目录里需要 file.osgjs 和 model_file.bin');
}
const res = await convertOsgjsToGlbFromFiles(files, null, []);
fs.writeFileSync(outPath, Buffer.from(res.glb));
let tris = 0, verts = 0;
for (const m of res.json.meshes) {
  for (const pr of m.primitives) {
    if (pr.indices != null) tris += res.json.accessors[pr.indices].count / 3;
    verts += res.json.accessors[pr.attributes.POSITION].count;
  }
}
console.log(`写出 ${outPath}: ${res.glb.byteLength} B, meshes=${res.geometryCount}, 三角面=${tris}, 顶点(含拆分)=${verts}`);
