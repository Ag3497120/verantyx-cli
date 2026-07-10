import * as THREE from "/static/vendor/three.module.min.js";
import { I18N, pickLang, fmt } from "/static/i18n.js";

// ── 言語 ────────────────────────────────────────────────────────────────────
let LANG = pickLang();
const T = () => I18N[LANG];
function applyLang() {
  document.documentElement.lang = LANG;
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const s = T()[el.dataset.i18n];
    if (s) el.textContent = s;
  });
  document.getElementById("q").placeholder = T().placeholder;
  document.getElementById("lang").value = LANG;
  buildPresets();
}

// ── 3D シーン ────────────────────────────────────────────────────────────────
const canvas = document.getElementById("scene");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
camera.position.set(0, 1.6, 7.5);
camera.lookAt(0, 0, 0);
scene.add(new THREE.AmbientLight(0x8899ff, 0.7));
const key = new THREE.PointLight(0xffffff, 1.2, 50);
key.position.set(4, 6, 6);
scene.add(key);

const world = new THREE.Group();
scene.add(world);

// 立体十字 (3D cross) — プロジェクトの象徴構造をワイヤフレームで
const crossMat = new THREE.LineBasicMaterial({ color: 0x2a3560, transparent: true, opacity: 0.55 });
function crossPlane(rx, ry) {
  const g = new THREE.PlaneGeometry(6.4, 6.4, 8, 8);
  const wire = new THREE.LineSegments(new THREE.WireframeGeometry(g), crossMat);
  wire.rotation.set(rx, ry, 0);
  return wire;
}
world.add(crossPlane(0, 0), crossPlane(0, Math.PI / 2), crossPlane(Math.PI / 2, 0));

// 星屑
{
  const n = 700, pos = new Float32Array(n * 3);
  for (let i = 0; i < n * 3; i++) pos[i] = (Math.random() - 0.5) * 42;
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({
    color: 0x5566aa, size: 0.035, transparent: true, opacity: 0.7 })));
}

const COLORS = { Commander: 0xffd166, "Scout-A": 0x4cc9f0, "Scout-B": 0x4cc9f0,
                 "Worker-1": 0x90e0a0, "Worker-2": 0x90e0a0 };
const CLASSMAP = { Commander: "cmd", "Scout-A": "scout", "Scout-B": "scout",
                   "Worker-1": "worker", "Worker-2": "worker" };

function label(text, color) {
  const c = document.createElement("canvas");
  c.width = 256; c.height = 64;
  const ctx = c.getContext("2d");
  ctx.font = "600 30px system-ui";
  ctx.fillStyle = color;
  ctx.textAlign = "center";
  ctx.fillText(text, 128, 42);
  const t = new THREE.CanvasTexture(c);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true }));
  s.scale.set(1.7, 0.42, 1);
  return s;
}

const nodes = {}, targets = {}, entropyOf = {};
function makeNode(name, colorHex, size) {
  const grp = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({
    color: colorHex, emissive: colorHex, emissiveIntensity: 0.55,
    roughness: 0.35, metalness: 0.15 });
  grp.add(new THREE.Mesh(new THREE.SphereGeometry(size, 24, 24), mat));
  const halo = new THREE.Mesh(
    new THREE.SphereGeometry(size * 1.9, 16, 16),
    new THREE.MeshBasicMaterial({ color: colorHex, transparent: true,
      opacity: 0.12, depthWrite: false }));
  grp.add(halo);
  const lb = label(name, "#" + colorHex.toString(16).padStart(6, "0"));
  lb.position.y = size + 0.42;
  grp.add(lb);
  grp.userData = { halo };
  world.add(grp);
  return grp;
}
for (const n of Object.keys(COLORS)) {
  nodes[n] = makeNode(n, COLORS[n], 0.16);
  const a = Math.random() * Math.PI * 2;
  nodes[n].position.set(Math.cos(a) * 2.4, (Math.random() - .5) * 1.6, Math.sin(a) * 2.4);
  targets[n] = nodes[n].position.clone();
  entropyOf[n] = 6;
}
const consensusNode = makeNode("Consensus", 0xf72585, 0.22);
consensusNode.visible = false;
targets.Consensus = new THREE.Vector3(0, 0, 0);

// 役割 → 合意 のエッジと、注入パルス
const edgeMat = new THREE.LineBasicMaterial({ color: 0x7b6cff, transparent: true, opacity: 0.5 });
let edges = [];
function rebuildEdges() {
  edges.forEach(e => world.remove(e));
  edges = [];
  if (!consensusNode.visible) return;
  for (const n of Object.keys(nodes)) {
    const g = new THREE.BufferGeometry().setFromPoints(
      [nodes[n].position, consensusNode.position]);
    const l = new THREE.Line(g, edgeMat);
    world.add(l); edges.push(l);
  }
}
let pulses = [];
function firePulses() {
  for (const n of Object.keys(nodes)) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.06, 10, 10),
      new THREE.MeshBasicMaterial({ color: 0xf72585 }));
    m.userData = { from: consensusNode.position.clone(),
                   to: nodes[n].position.clone(), t: 0 };
    world.add(m); pulses.push(m);
  }
}

function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== w || canvas.height !== h) {
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
}
let t = 0;
(function animate() {
  requestAnimationFrame(animate);
  resize();
  t += 0.016;
  world.rotation.y += 0.0018;
  for (const n of Object.keys(nodes)) {
    nodes[n].position.lerp(targets[n], 0.06);
    const pulse = 1 + Math.sin(t * (1.5 + entropyOf[n] * 0.4)) * 0.05 * Math.min(entropyOf[n] / 4, 2);
    nodes[n].userData.halo.scale.setScalar(pulse);
  }
  consensusNode.position.lerp(targets.Consensus, 0.08);
  edges.forEach((e, i) => {
    const n = Object.keys(nodes)[i];
    e.geometry.setFromPoints([nodes[n].position, consensusNode.position]);
  });
  pulses = pulses.filter(p => {
    p.userData.t += 0.03;
    if (p.userData.t >= 1) { world.remove(p); return false; }
    p.position.lerpVectors(p.userData.from, p.userData.to, p.userData.t);
    p.material.opacity = 1 - p.userData.t;
    return true;
  });
  renderer.render(scene, camera);
})();

const SCALE = 1.35;
function setTarget(name, pos) {
  targets[name] = new THREE.Vector3(pos[0] * SCALE, pos[1] * SCALE, pos[2] * SCALE);
}

// ── レーダー (6軸) ───────────────────────────────────────────────────────────
const AXES = ["Logic", "Syntax", "Fact", "Time", "Creative", "Consensus"];
function drawRadar(sig) {
  const c = document.getElementById("radar"), ctx = c.getContext("2d");
  const cx = 110, cy = 110, R = 78;
  ctx.clearRect(0, 0, 220, 220);
  ctx.strokeStyle = "#273154"; ctx.fillStyle = "#7d89ad";
  ctx.font = "10px system-ui"; ctx.textAlign = "center";
  for (let ring = 1; ring <= 3; ring++) {
    ctx.beginPath();
    for (let i = 0; i <= 6; i++) {
      const a = -Math.PI / 2 + i * Math.PI / 3, r = R * ring / 3;
      ctx[i ? "lineTo" : "moveTo"](cx + Math.cos(a) * r, cy + Math.sin(a) * r);
    }
    ctx.stroke();
  }
  AXES.forEach((n, i) => {
    const a = -Math.PI / 2 + i * Math.PI / 3;
    ctx.fillText(n, cx + Math.cos(a) * (R + 16), cy + Math.sin(a) * (R + 16) + 3);
  });
  if (!sig) return;
  ctx.beginPath();
  sig.forEach((v, i) => {
    const a = -Math.PI / 2 + i * Math.PI / 3, r = R * (0.25 + 0.75 * v);
    ctx[i ? "lineTo" : "moveTo"](cx + Math.cos(a) * r, cy + Math.sin(a) * r);
  });
  ctx.closePath();
  ctx.fillStyle = "rgba(123,108,255,.25)"; ctx.fill();
  ctx.strokeStyle = "#7b6cff"; ctx.stroke();
}
drawRadar(null);

// ── UI / SSE ────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const log = $("log");
function put(cls, html) {
  const d = document.createElement("div");
  d.className = cls; d.innerHTML = html;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}
const fmtTop = top => top.map(([s, p]) =>
  `<span class="tok">'${escapeHtml(s)}'</span>(${Math.round(p * 100)}%)`).join(" ");
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;",
    '"': "&quot;", "'": "&#39;" }[c]));
}

function buildPresets() {
  const box = $("presets");
  box.innerHTML = "";
  T().presets.forEach(p => {
    const b = document.createElement("button");
    b.textContent = p;
    b.onclick = () => { $("q").value = p; askQuestion(); };
    box.appendChild(b);
  });
}

$("lang").addEventListener("change", e => {
  LANG = e.target.value;
  localStorage.setItem("vx_lang", LANG);
  applyLang();
});
applyLang();

fetch("/api/health").then(r => r.json()).then(h => {
  const el = $("status");
  el.textContent = `● ${h.model} — ${T().running}`;
  el.classList.add("ready");
}).catch(() => { $("status").textContent = T().loading; });

async function askQuestion() {
  const q = $("q").value.trim();
  if (!q) return;
  $("askBtn").disabled = true;
  log.innerHTML = "";
  $("councilCard").hidden = true;
  $("baselineCard").hidden = true;
  $("roundBadge").textContent = "";
  put("sys", `Q: ${escapeHtml(q)}`);

  const res = await fetch("/api/ask", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: q, language: LANG }) });
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
      if (chunk.startsWith("data: ")) handleEvent(JSON.parse(chunk.slice(6)));
    }
  }
  $("askBtn").disabled = false;
}

function statusText(ev) {
  // バックエンドは言語非依存のキーを送る。辞書にあれば選択言語で表示。
  return (ev.key && T()[ev.key]) || ev.msg || "";
}

function handleEvent(ev) {
  switch (ev.type) {
    case "status": put("sys", escapeHtml(statusText(ev))); break;
    case "round_start":
      $("roundBadge").textContent = `ROUND ${ev.round}`;
      put("sys", fmt(T().round, { r: ev.round }));
      break;
    case "opinion":
      entropyOf[ev.name] = ev.entropy;
      setTarget(ev.name, ev.pos);
      put(CLASSMAP[ev.name] || "sys",
        `${ev.name.padEnd(9)} H=${ev.entropy.toFixed(2)}bits 整合=${ev.coherence >= 0 ? "+" : ""}${ev.coherence.toFixed(2)} → ${fmtTop(ev.top)}`);
      break;
    case "consensus":
      consensusNode.visible = true;
      setTarget("Consensus", ev.pos);
      rebuildEdges();
      $("cosBar").style.width = `${Math.max(0, Math.min(1, ev.agreement)) * 100}%`;
      $("cosVal").textContent = ev.agreement.toFixed(3);
      $("entBar").style.width = `${Math.min(ev.entropy / 10, 1) * 100}%`;
      $("entVal").textContent = ev.entropy.toFixed(2);
      drawRadar(ev.axes);
      put("cons", `${T().consensusLine} | ${ev.unanimous ? T().unanimous : T().split} | cos=${ev.agreement.toFixed(3)} | ${fmtTop(ev.top)}`);
      break;
    case "inject":
      firePulses();
      put("sys", escapeHtml(statusText(ev)));
      break;
    case "perturb":
      put(ev.recovered ? "ok" : "warn",
        ev.recovered
          ? fmt(T().perturbOk, { d: ev.drift_cos.toFixed(2) })
          : fmt(T().perturbNg, { l: escapeHtml(ev.lured_to || "?"),
                                 d: ev.drift_cos.toFixed(2) }));
      break;
    case "concepts":
      put("sys", fmt(T().conceptsLine,
        { c: ev.concepts.map(escapeHtml).join(", "), s: ev.deliberation_s }));
      $("concepts").innerHTML = ev.concepts.map(c => `<span>${escapeHtml(c)}</span>`).join("");
      break;
    case "answer":
      $("councilCard").hidden = false;
      $("councilAnswer").textContent = ev.text || T().noAnswer;
      $("councilMeta").textContent = fmt(T().councilMeta, { s: ev.total_s });
      break;
    case "baseline":
      $("baselineCard").hidden = false;
      $("baselineAnswer").textContent = ev.text || T().noAnswer;
      $("baselineMeta").textContent = `${ev.elapsed_s}s / ${ev.tokens} tokens`;
      break;
    case "error":
      put("warn", fmt(T().error, { m: escapeHtml(ev.msg) }));
      break;
  }
}

$("askBtn").onclick = askQuestion;
$("q").addEventListener("keydown", e => { if (e.key === "Enter") askQuestion(); });
