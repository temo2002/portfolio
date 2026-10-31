"use strict";

const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (id) => document.getElementById(id);

// ---------- Små automatikker ----------
$("year").textContent = new Date().getFullYear();
$("yearsBiz").textContent = new Date().getFullYear() - 2018; // bedriften startet i 2018

// Meny på mobil
const burger = $("burger"), menu = $("menu");
burger.addEventListener("click", () => {
  const open = menu.classList.toggle("open");
  burger.setAttribute("aria-expanded", open);
});
menu.addEventListener("click", (e) => { if (e.target.tagName === "A") { menu.classList.remove("open"); burger.setAttribute("aria-expanded", false); } });

// Fade inn ved scrolling
const io = new IntersectionObserver((entries) => {
  entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("is-revealed"); io.unobserve(en.target); } });
}, { threshold: 0.08 });
document.querySelectorAll(".fade-in").forEach((el) => reduceMotion ? el.classList.add("is-revealed") : io.observe(el));

// Skrivemaskin
(function typewriter() {
  const el = $("typed");
  const phrases = ["elektronikk", "filterdesign", "å forklare ting", "ledelse og lagarbeid", "trompet", "sommerjobb 2027"];
  if (reduceMotion) return;
  let i = 0, j = 0, del = false;
  (function tick() {
    const full = phrases[i];
    j += del ? -1 : 1;
    el.textContent = full.slice(0, j);
    let wait = del ? 35 : 75;
    if (!del && j === full.length) { wait = 1600; del = true; }
    else if (del && j === 0) { del = false; i = (i + 1) % phrases.length; wait = 350; }
    setTimeout(tick, wait);
  })();
})();

// ---------- Tidslinje ----------
const MOBILE_BREAK = 900, PX_PER_YEAR = 170, ROW_H = 58, ROW_GAP = 10, HEAD_H = 34, LABEL_MIN = 190;
const CAT_LABEL = { work: "Jobb", school: "Skole", hobby: "Hobby" };
const nowYear = () => { const d = new Date(); return d.getFullYear() + d.getMonth() / 12; };
const toYear = (s) => {
  if (s === "present") return nowYear();
  const [y, m] = String(s).split("-").map(Number);
  return y + ((m || 1) - 1) / 12;
};
const fmtDate = (e) => {
  const end = e.end === "present" ? "i dag" : e.end;
  return !e.end || e.end === e.start ? e.start : `${e.start} til ${end}`;
};
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function normalize(raw) {
  const start = toYear(raw.start);
  const end = raw.end ? toYear(raw.end) : start;
  const importance = Math.min(100, Math.max(1, raw.importance ?? 40));
  return { ...raw, startVal: start, endVal: Math.max(end, start), importance, types: raw.types || [] };
}
const matches = (e, f) => f === "all" || (f === "project" ? e.isProject : e.category === f || e.types.includes(f));

let entries = [], activeFilter = "all";

async function loadEntries() {
  const manifest = await (await fetch("projects_data/manifest.json")).json();
  const loaded = await Promise.all(manifest.map(async (f) => {
    try { return normalize(await (await fetch("projects_data/" + f)).json()); }
    catch (err) { console.warn("Hoppet over", f, err); return null; }
  }));
  return loaded.filter(Boolean).sort((a, b) => a.startVal - b.startVal);
}

function renderLane() {
  const lane = $("lane");
  lane.innerHTML = "";
  const minYear = Math.floor(Math.min(...entries.map((e) => e.startVal)));
  const maxYear = Math.ceil(Math.max(...entries.map((e) => e.endVal)) + 0.01);

  // Plasser tyngste først; første rad uten overlapp
  const rows = [];
  const placed = [...entries].sort((a, b) => b.importance - a.importance).map((e) => {
    const left = (e.startVal - minYear) * PX_PER_YEAR;
    const width = Math.max((e.endVal - e.startVal) * PX_PER_YEAR, LABEL_MIN);
    let r = rows.findIndex((used) => used.every(([a, b]) => left + width + 8 <= a || left >= b + 8));
    if (r === -1) { rows.push([]); r = rows.length - 1; }
    rows[r].push([left, left + width]);
    return { e, left, width, r };
  });
  const totalW = Math.max((maxYear - minYear) * PX_PER_YEAR, ...placed.map((p) => p.left + p.width)) + 24;
  const totalH = HEAD_H + rows.length * (ROW_H + ROW_GAP) + 8;
  lane.style.width = totalW + "px";
  lane.style.height = totalH + "px";

  for (let y = minYear; y <= maxYear; y++) {
    const t = document.createElement("div");
    t.className = "yr";
    t.style.left = (y - minYear) * PX_PER_YEAR + "px";
    t.innerHTML = `<span>${y}</span>`;
    lane.appendChild(t);
  }
  placed.forEach(({ e, left, width, r }) => {
    const b = document.createElement("button");
    b.className = `bar cat-${e.category}` + (e.importance >= 70 ? " big" : e.importance < 45 ? " small" : "") + (e.projectPage ? " link" : "");
    b.dataset.id = e.id;
    b.style.cssText = `left:${left}px;top:${HEAD_H + r * (ROW_H + ROW_GAP)}px;width:${width}px;height:${ROW_H}px`;
    b.innerHTML = `<span class="bar-title">${esc(e.title)}</span><span class="bar-date">${fmtDate(e)}${e.status === "ongoing" ? " · pågår" : ""}</span>`;
    b.addEventListener("mouseenter", () => showTip(e, b));
    b.addEventListener("focus", () => showTip(e, b));
    b.addEventListener("mouseleave", hideTip);
    b.addEventListener("blur", hideTip);
    if (e.projectPage) b.addEventListener("click", () => { location.href = e.projectPage + ".html"; });
    b._left = left; b._width = width;
    lane.appendChild(b);
  });
  const wrap = $("laneWrap");
  wrap.scrollLeft = wrap.scrollWidth;
  keepLabelsVisible();
}

// Lange rader: la tittelen følge med når man scroller, så den aldri havner utenfor synsfeltet
function keepLabelsVisible() {
  const sl = $("laneWrap").scrollLeft;
  document.querySelectorAll(".bar").forEach((b) => {
    const pad = Math.min(Math.max(14, sl - b._left + 14), Math.max(14, b._width - 170));
    b.style.paddingLeft = pad + "px";
  });
}
$("laneWrap").addEventListener("scroll", keepLabelsVisible, { passive: true });

function renderList() {
  const list = $("tlList");
  list.innerHTML = "";
  const byYear = new Map();
  [...entries].sort((a, b) => b.startVal - a.startVal).forEach((e) => {
    const y = Math.floor(e.startVal);
    if (!byYear.has(y)) byYear.set(y, []);
    byYear.get(y).push(e);
  });
  const card = (e) => `<article class="tl cat-${e.category}" data-id="${e.id}">
      <span class="when">${fmtDate(e)}${e.status === "ongoing" ? " · pågår" : ""} · ${CAT_LABEL[e.category]}</span>
      <h3>${e.projectPage ? `<a href="${e.projectPage}.html">${esc(e.title)}</a>` : esc(e.title)}</h3>
      <p>${esc(e.shortDescription)}</p></article>`;
  byYear.forEach((items, y) => {
    const major = items.filter((e) => e.importance >= 50), minor = items.filter((e) => e.importance < 50);
    const g = document.createElement("div");
    g.className = "tl-year";
    g.innerHTML = `<h4>${y}</h4>${major.map(card).join("")}` +
      (minor.length ? `<details><summary>${minor.length} til</summary>${minor.map(card).join("")}</details>` : "");
    list.appendChild(g);
  });
}

function applyFilter() {
  const byId = new Map(entries.map((e) => [e.id, e]));
  document.querySelectorAll("[data-id]").forEach((el) => {
    const ok = matches(byId.get(el.dataset.id), activeFilter);
    el.classList.toggle("is-faded", !ok);
    if (el.classList.contains("tl")) el.hidden = !ok;
  });
  document.querySelectorAll(".tl-year").forEach((g) => { g.hidden = !g.querySelector(".tl:not([hidden])"); });
  document.querySelectorAll(".tl-year details").forEach((d) => { d.hidden = !d.querySelector(".tl:not([hidden])"); });
}

// Tooltip
const tip = $("tip");
function showTip(e, el) {
  if (innerWidth < MOBILE_BREAK) return;
  tip.innerHTML = `<span class="tip-cat">${CAT_LABEL[e.category]} · ${fmtDate(e)}</span><strong>${esc(e.title)}</strong>
    <p>${esc(e.shortDescription)}</p>
    ${e.tags?.length ? `<span class="tip-tags">${e.tags.map((t) => `<i>${esc(t)}</i>`).join("")}</span>` : ""}
    ${e.projectPage ? `<span class="tip-go">klikk for å lese mer →</span>` : ""}`;
  tip.hidden = false;
  const r = el.getBoundingClientRect(), tr = tip.getBoundingClientRect();
  const left = Math.min(Math.max(8, r.left + r.width / 2 - tr.width / 2), innerWidth - tr.width - 8);
  const top = r.top - tr.height - 10 > 8 ? r.top - tr.height - 10 : r.bottom + 10;
  tip.style.left = left + "px";
  tip.style.top = top + "px";
}
const hideTip = () => { tip.hidden = true; };

document.getElementById("filters").addEventListener("click", (ev) => {
  const b = ev.target.closest(".filter-chip");
  if (!b) return;
  activeFilter = b.dataset.filter;
  document.querySelectorAll(".filter-chip").forEach((x) => x.classList.toggle("on", x === b));
  applyFilter();
});

loadEntries().then((list) => {
  entries = list;
  if (!entries.length) throw new Error("ingen oppføringer");
  renderLane();
  renderList();
  applyFilter();
}).catch((err) => {
  console.error(err);
  $("tlError").hidden = false;
});

// ---------- Oscilloskop i hero ----------
const scope = $("scope"), sctx = scope.getContext("2d");
let t = 0;
function drawScope() {
  const w = scope.width, h = scope.height;
  sctx.clearRect(0, 0, w, h);
  sctx.strokeStyle = "#1c2447"; sctx.lineWidth = 1;
  for (let x = 0; x <= w; x += w / 10) { sctx.beginPath(); sctx.moveTo(x, 0); sctx.lineTo(x, h); sctx.stroke(); }
  for (let y = 0; y <= h; y += h / 4) { sctx.beginPath(); sctx.moveTo(0, y); sctx.lineTo(w, y); sctx.stroke(); }
  sctx.strokeStyle = "#4fd1c5"; sctx.lineWidth = 2; sctx.beginPath();
  for (let x = 0; x < w; x++) {
    const p = (x / w) * Math.PI * 6 + t;
    const noise = Math.sin(x * 1.7 + t * 9) * 0.07 + Math.sin(x * 0.63 + t * 5) * 0.05;
    const y = h / 2 - (Math.sin(p) + noise) * h * 0.34;
    x ? sctx.lineTo(x, y) : sctx.moveTo(x, y);
  }
  sctx.stroke();
  if (!reduceMotion) { t += 0.04; requestAnimationFrame(drawScope); }
}
drawScope();

// ---------- RC-lavpassfilter (Bode) ----------
const bode = $("bode"), bctx = bode.getContext("2d");
const rIn = $("r"), cIn = $("c");
const fmt = (v, unit) => {
  const pre = [[1e6, "M"], [1e3, "k"], [1, ""], [1e-3, "m"], [1e-6, "µ"], [1e-9, "n"], [1e-12, "p"]];
  for (const [m, p] of pre) if (v >= m * 0.9995) return `${+(v / m).toPrecision(3)} ${p}${unit}`;
  return `${v} ${unit}`;
};
function drawBode() {
  const R = Math.pow(10, +rIn.value), C = Math.pow(10, +cIn.value);
  const fc = 1 / (2 * Math.PI * R * C);
  $("rOut").textContent = fmt(R, "Ω");
  $("cOut").textContent = fmt(C, "F");
  $("fcOut").textContent = fmt(fc, "Hz");
  const w = bode.width, h = bode.height, L = 52, B = 34, T = 14, Rr = 16;
  const fMin = 1, fMax = 1e6, dbMin = -60, dbMax = 5;
  const X = (f) => L + (Math.log10(f) - Math.log10(fMin)) / (Math.log10(fMax) - Math.log10(fMin)) * (w - L - Rr);
  const Y = (d) => T + (dbMax - d) / (dbMax - dbMin) * (h - T - B);
  bctx.clearRect(0, 0, w, h);
  bctx.font = "12px ui-monospace, monospace"; bctx.fillStyle = "#8d95b8"; bctx.strokeStyle = "#1c2447"; bctx.lineWidth = 1;
  for (let e = 0; e <= 6; e++) {
    const x = X(10 ** e); bctx.beginPath(); bctx.moveTo(x, T); bctx.lineTo(x, h - B); bctx.stroke();
    bctx.fillText(e === 0 ? "1" : e < 3 ? `${10 ** e}` : e < 6 ? `${10 ** (e - 3)}k` : "1M", x - 8, h - 14);
  }
  for (let d = 0; d >= dbMin; d -= 20) {
    const y = Y(d); bctx.beginPath(); bctx.moveTo(L, y); bctx.lineTo(w - Rr, y); bctx.stroke();
    bctx.fillText(`${d} dB`, 4, y + 4);
  }
  bctx.setLineDash([4, 4]); bctx.strokeStyle = "#f2b84b55";
  bctx.beginPath(); bctx.moveTo(L, Y(-3)); bctx.lineTo(w - Rr, Y(-3)); bctx.stroke(); bctx.setLineDash([]);
  bctx.strokeStyle = "#4fd1c5"; bctx.lineWidth = 2.5; bctx.beginPath();
  for (let i = 0; i <= 300; i++) {
    const f = 10 ** ((i / 300) * 6);
    const db = -10 * Math.log10(1 + (f / fc) ** 2);
    const x = X(f), y = Y(Math.max(db, dbMin));
    i ? bctx.lineTo(x, y) : bctx.moveTo(x, y);
  }
  bctx.stroke();
  if (fc >= fMin && fc <= fMax) { bctx.fillStyle = "#f2b84b"; bctx.beginPath(); bctx.arc(X(fc), Y(-3), 6, 0, 7); bctx.fill(); }
}
rIn.oninput = cIn.oninput = drawBode;
drawBode();
