#!/usr/bin/env node
// 加密 .binz -> 解密后的 OSGJS 场景 + 几何缓冲
// 用法: node decrypt.mjs <已保存的页面> <xxx.binz> [<model_file.binz>] <输出目录>
//
// 原理:原平台自 2021-06 起把模型文件加密成 .binz，解密逻辑在 viewer 的
// decrypt.wasm 里，密钥 = 全局静态 key（页面 JS 中 C04p 模块导出）
//        + 每个模型自己的 diterB（页面模型 JSON 里 files[0].p[0].b）。
import fs from 'node:fs';
import path from 'node:path';
import { decryptBinzBytes } from './decrypt-core.mjs';

const args = process.argv.slice(2);
if (args.length < 3) {
  console.error('用法: node decrypt.mjs <page.htm> <file.binz> [<model_file.binz>] <outdir>');
  process.exit(1);
}
const outDir = args[args.length - 1];
const page = args[0];
const binzFiles = args.slice(1, -1);

const html = fs.readFileSync(page, 'utf8').replace(/&#34;/g, '"');

// 1) 每个模型的 diterB
const m = html.match(/"p"\s*:\s*\[\s*\{\s*"v"\s*:\s*\d+\s*,\s*"b"\s*:\s*"((?:[^"\\]|\\.)*)"/);
if (!m) throw new Error('页面里找不到 files[0].p[0].b (diterB)');
const diterB = m[1];

// 2) 全局静态 key：从页面同目录下载下来的 viewer bundle 里找
const pageDir = path.dirname(page);
function walk(dir, depth = 0) {
  const out = [];
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory() && depth < 2) out.push(...walk(p, depth + 1));
    else if (/\.(js|download)$/i.test(ent.name)) out.push(p);
  }
  return out;
}
const jsFiles = walk(pageDir);
let staticKey = null;
const keyPatterns = [
  /C04p\s*:\s*\w+\s*=>\s*\{\s*"use strict";\s*\w+\.exports\s*=\s*"([0-9a-f]{40})/,
  /exports\s*\.\s*k\s*:\s*\(\)\s*=>\s*\w+\}\s*;\s*const\s+\w+\s*=\s*"([0-9a-f]{40})/,
  /\{k:\s*\(\)\s*=>\s*\w+\}[^;]*;\s*const\s+\w+\s*=\s*"([0-9a-f]{40})/,
];
for (const f of jsFiles) {
  const s = fs.readFileSync(f, 'utf8');
  for (const re of keyPatterns) {
    const km = s.match(re);
    if (km) { staticKey = km[1].toLowerCase(); break; }
  }
  if (staticKey) break;
}
if (!staticKey) throw new Error('viewer bundle 里找不到 40 位静态 key');
console.log('静态 key:', staticKey);
console.log('diterB 长度:', diterB.length);

const wasm = new Uint8Array(fs.readFileSync(new URL('./decrypt.wasm', import.meta.url)));
fs.mkdirSync(outDir, { recursive: true });

for (const f of binzFiles) {
  const name = path.basename(f);
  const enc = new Uint8Array(fs.readFileSync(f));
  const out = await decryptBinzBytes(wasm, enc, diterB, staticKey);
  const outName = name === 'file.binz' ? 'file.osgjs'
    : name === 'model_file.binz' ? 'model_file.bin'
    : name.replace(/\.binz$/, '.bin');
  fs.writeFileSync(path.join(outDir, outName), out);
  console.log(`${name} (${enc.length} B) -> ${outName} (${out.length} B)`);
}
