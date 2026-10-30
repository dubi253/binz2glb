// 从 annotations.json 生成 model-viewer 的 hotspot，并把点击变成"飞到标注视点 + 显示说明"
const mv = document.getElementById('mv');
const card = document.getElementById('card');
const cardImg = document.getElementById('card-img');
const cardTitle = document.getElementById('card-title');
const cardText = document.getElementById('card-text');
const cardIndex = document.getElementById('card-index');

const DEG = 180 / Math.PI;

/**原平台的 eye/target（已是 GLB 坐标系）→ model-viewer 的球坐标。 */
function orbitFrom(eye, target) {
  const d = [eye[0] - target[0], eye[1] - target[1], eye[2] - target[2]];
  const r = Math.hypot(d[0], d[1], d[2]);
  const theta = Math.atan2(d[0], d[2]) * DEG;
  const phi = Math.acos(Math.max(-1, Math.min(1, d[1] / r))) * DEG;
  //原平台的默认 fov 比 model-viewer 自动算出的 30° 更广，不放大半径会显得贴脸
  return { theta, phi, radius: r * 1.45 };
}

const fmt = (o) => `${o.theta.toFixed(1)}deg ${o.phi.toFixed(1)}deg ${o.radius.toFixed(2)}m`;
const fmtTarget = (t) => `${t[0].toFixed(2)}m ${t[1].toFixed(2)}m ${t[2].toFixed(2)}m`;

let annotations = [];
let active = -1;

function imgUrl(rel) {
  // annotations.json 里的 image 是相对 annotations/ 目录的
  return rel ? `models/finfet/annotations/${rel}` : null;
}

function showCard(ann, i) {
  card.hidden = false;
  cardTitle.textContent = ann.name;
  cardText.textContent = ann.content || '（该标注在原平台上没有文字说明）';
  cardIndex.textContent = `标注 ${i + 1} / ${annotations.length}`;
  const url = imgUrl(ann.image);
  if (url) {
    cardImg.src = url;
    cardImg.style.display = 'block';
  } else {
    cardImg.removeAttribute('src');
    cardImg.style.display = 'none';
  }
}

function gotoAnnotation(ann) {
  const o = orbitFrom(ann.eye, ann.target);
  mv.cameraTarget = fmtTarget(ann.target);
  mv.cameraOrbit = fmt(o);
}

function buildHotspots() {
  mv.querySelectorAll('.hotspot').forEach((el) => el.remove());
  annotations.forEach((ann, i) => {
    const btn = document.createElement('button');
    btn.className = 'hotspot';
    btn.slot = `hotspot-${i + 1}`;
    btn.dataset.position = ann.position.map((v) => v.toFixed(4)).join(' ');
    btn.dataset.normal = '0 1 0';
    btn.dataset.visibilityAttribute = 'visible';
    btn.title = ann.name;
    btn.setAttribute('aria-label', ann.name);
    const url = imgUrl(ann.image);
    if (url) btn.style.backgroundImage = `url("${url}")`;
    btn.addEventListener('click', () => {
      active = i;
      gotoAnnotation(ann);
      showCard(ann, i);
    });
    mv.appendChild(btn);
  });
}

async function init() {
  try {
    const res = await fetch('models/finfet/annotations/annotations.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const doc = await res.json();
    annotations = doc.annotations || [];
  } catch (e) {
    console.warn('标注加载失败：', e);
    document.getElementById('legend').textContent = '未找到 annotations/annotations.json';
    return;
  }
  buildHotspots();
  if (annotations.length) document.getElementById('legend').textContent =
    `点击模型上的圆点查看各层材料说明（共 ${annotations.length} 处）`;
}

document.getElementById('reset').addEventListener('click', () => {
  active = -1;
  card.hidden = true;
  mv.removeAttribute('camera-target');
  mv.removeAttribute('camera-orbit');
  mv.cameraTarget = 'auto auto auto';
  mv.cameraOrbit = 'auto auto auto';
});

document.getElementById('toggle-ann').addEventListener('click', (e) => {
  const on = e.currentTarget.classList.toggle('on');
  e.currentTarget.textContent = `标注：${on ? '开' : '关'}`;
  mv.querySelectorAll('.hotspot').forEach((el) => {
    el.style.display = on ? '' : 'none';
  });
});

document.getElementById('card-close').addEventListener('click', () => {
  card.hidden = true;
});
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') card.hidden = true;
});

init();
