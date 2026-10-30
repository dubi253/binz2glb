#!/usr/bin/env node
// Khronos glTF 校验：node validate.mjs <file.glb>
// 先装依赖：npm install --registry=https://registry.npmmirror.com gltf-validator
import fs from 'node:fs';
import validator from 'gltf-validator';

const file = process.argv[2];
if (!file) {
  console.error('用法: node validate.mjs <file.glb>');
  process.exit(1);
}
const data = new Uint8Array(fs.readFileSync(file));
const r = await validator.validateBytes(data, { maxIssues: 200, uri: file });
const { issues, info } = r;
console.log(`errors ${issues.numErrors} warnings ${issues.numWarnings} ` +
            `infos ${issues.numInfos} hints ${issues.numHints}`);
console.log(`meshes(draw calls) ${info.drawCallCount} triangles ${info.totalTriangleCount} ` +
            `vertices ${info.totalVertexCount} materials ${info.materialCount} images ${info.hasTextures ? 'yes' : 'no'}`);
for (const m of (issues.messages || []).slice(0, 10)) {
  console.log(` [${m.severity}] ${m.code} @ ${m.pointer}: ${m.message}`);
}
process.exit(issues.numErrors ? 2 : 0);
