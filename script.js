"use strict";

const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (id) => document.getElementById(id);
const LANG = document.documentElement.lang === "en" ? "en" : "no";
const ROOT = document.documentElement.dataset.root || "";
const STR = {
  no: { ongoing: "pågår", today: "i dag", to: "til", more: "til", go: "klikk for å lese mer →", cats: { work: "Jobb", school: "Skole", hobby: "Hobby" }, empty: "Ingen treff i dette filteret." },
  en: { ongoing: "ongoing", today: "present", to: "to", more: "more", go: "click to read more →", cats: { work: "Work", school: "School", hobby: "Hobby" }, empty: "No entries match this filter." },
}[LANG];

// ---------- Små automatikker ----------
$("year").textContent = new Date().getFullYear();
$("yearsBiz").textContent = new Date().getFullYear() - 2018; // bedriften startet i 2018

const burger = $("burger"), menu = $("menu");
burger.addEventListener("click", () => {
  const open = menu.classList.toggle("open");
  burger.setAttribute("aria-expanded", open);
});
menu.addEventListener("click", (e) => { if (e.target.tagName === "A") { menu.classList.remove("open"); burger.setAttribute("aria-expanded", false); } });

const io = new IntersectionObserver((entries) => {
  entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("is-revealed"); io.unobserve(en.target); } });
}, { threshold: 0.08 });
document.querySelectorAll(".fade-in").forEach((el) => reduceMotion ? el.classList.add("is-revealed") : io.observe(el));

// Skrivemaskin: fraser ligger i data-phrases på elementet, så de kan oversettes
(function typewriter() {
  const el = $("typed");
  let phrases;
  try { phrases = JSON.parse(el.dataset.phrases); } catch (e) { phrases = [el.textContent]; }
  if (reduceMotion || !phrases.length) return;
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
const MOBILE_BREAK = 900, PX_PER_YEAR = 270, ROWS = 15, ROW_H = 36, PAD_T = 12, RANGE_MIN_YEARS = 0.25;
const nowYear = () => { const d = new Date(); return d.getFullYear() + d.getMonth() / 12; };
const toYear = (s) => {
  if (s === "present") return nowYear();
  const [y, m] = String(s).split("-").map(Number);
  return y + ((m || 1) - 1) / 12;
};
const loc = (e, k) => (LANG === "en" && e.en && e.en[k]) || e[k];
const fmtDate = (e) => {
  const end = e.end === "present" ? STR.today : e.end;
  return !e.end || e.end === e.start ? e.start : `${e.start} ${STR.to} ${end}`;
};
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pageUrl = (e) => e.projectPage + ".html";

function normalize(raw) {
  const start = toYear(raw.start);
  const end = raw.end ? toYear(raw.end) : start;
  const importance = Math.min(100, Math.max(1, raw.importance ?? 40));
  const endVal = Math.max(end, start);
  return { ...raw, startVal: start, endVal, importance, imp: importance / 100, isRange: endVal - start >= RANGE_MIN_YEARS, types: raw.types || [] };
}
const matches = (e, f) => f === "all" || (f === "project" ? e.isProject : e.category === f || e.types.includes(f));

let entries = [], activeFilter = "all";

async function loadEntries() {
  const manifest = await (await fetch(ROOT + "projects_data/manifest.json")).json();
  const loaded = await Promise.all(manifest.map(async (f) => {
    try { return normalize(await (await fetch(ROOT + "projects_data/" + f)).json()); }
    catch (err) { console.warn("Hoppet over", f, err); return null; }
  }));
  return loaded.filter(Boolean).sort((a, b) => a.startVal - b.startVal);
}

// Plassering: tyngst først, fra midtraden og utover. Etiketter som ikke får plass skjules.
function layout(items, minYear) {
  const mid = Math.floor(ROWS / 2), order = [];
  for (let d = 0; order.length < ROWS; d++) {
    if (d === 0) order.push(mid);
    else { if (mid - d >= 0) order.push(mid - d); if (mid + d < ROWS) order.push(mid + d); }
  }
  const used = Array.from({ length: ROWS }, () => []);
  const free = (r, a, b) => used[r].every(([x, y]) => b + 6 <= x || a >= y + 6);
  items.forEach((it) => {
    it.x = (it.startVal - minYear) * PX_PER_YEAR;
    it.title_ = loc(it, "title");
    if (it.isRange) {
      it.w = Math.max((it.endVal - it.startVal) * PX_PER_YEAR, 150);
      it.wMin = it.wFull = it.w;
    } else {
      it.marker = Math.round(6 + it.imp * 12);
      const lab = Math.min(230, Math.round(it.title_.length * 7 + 20));
      it.wMin = it.marker + 6;
      it.wFull = it.marker + 8 + lab;
    }
  });
  [...items].sort((a, b) => b.importance - a.importance).forEach((it) => {
    let row = order.find((r) => free(r, it.x, it.x + it.wFull));
    it.hideLabel = false;
    if (row === undefined) { row = order.find((r) => free(r, it.x, it.x + it.wMin)); it.hideLabel = !it.isRange; }
    if (row === undefined) { row = order[0]; it.hideLabel = !it.isRange; }
    used[row].push([it.x, it.x + (it.hideLabel ? it.wMin : it.wFull)]);
    it.row = row;
  });
  const rows = items.map((i) => i.row), lo = Math.min(...rows), hi = Math.max(...rows);
  items.forEach((i) => { i.row -= lo; });
  return hi - lo + 1;
}

function renderSwimlane() {
  const lane = $("lane"), axis = $("yearAxis"), inner = $("swimInner");
  lane.innerHTML = ""; axis.innerHTML = "";
  const minYear = Math.floor(Math.min(...entries.map((e) => e.startVal)));
  const maxYear = Math.ceil(Math.max(...entries.map((e) => e.endVal)) + 0.01);
  const rowsUsed = layout(entries, minYear);
  const right = Math.max(...entries.map((e) => e.x + e.wFull));
  const total = Math.max((maxYear - minYear) * PX_PER_YEAR, right) + 30;
  inner.style.width = total + "px";
  lane.style.height = PAD_T * 2 + rowsUsed * ROW_H + "px";

  const cur = Math.floor(nowYear());
  for (let y = minYear; y <= maxYear; y++) {
    const t = document.createElement("div");
    t.className = "year-tick" + (y === cur ? " current" : "");
    t.style.left = (y - minYear) * PX_PER_YEAR + "px"; t.style.width = PX_PER_YEAR + "px";
    t.textContent = y; axis.appendChild(t);
    const g = document.createElement("div");
    g.className = "year-guide"; g.style.left = (y - minYear) * PX_PER_YEAR + "px"; lane.appendChild(g);
  }

  entries.forEach((e) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = `entry ${e.isRange ? "range" : "point"} cat-${e.category}` + (e.projectPage ? " clickable" : "") + (e.hideLabel ? " label-hidden" : "") + (e.status === "ongoing" && e.isRange ? " ongoing" : "");
    b.dataset.id = e.id;
    b.style.cssText = `left:${e.x}px;top:${PAD_T + e.row * ROW_H}px;height:${ROW_H}px;--imp:${e.imp};z-index:${Math.round(1 + e.imp * 10)};` + (e.isRange ? `width:${e.w}px;` : "");
    b.innerHTML = e.isRange
      ? `<span class="bar">${esc(e.title_)}</span>${e.status === "ongoing" ? '<span class="ongoing-arrow"></span>' : ""}`
      : `<span class="marker"></span><span class="label">${esc(e.title_)}</span>`;
    b.setAttribute("aria-label", `${e.title_}, ${fmtDate(e)}`);
    b.addEventListener("mouseenter", () => showTip(e, b));
    b.addEventListener("focus", () => showTip(e, b));
    b.addEventListener("mouseleave", hideTip);
    b.addEventListener("blur", hideTip);
    if (e.projectPage) b.addEventListener("click", () => { location.href = pageUrl(e); });
    lane.appendChild(b);
  });
  const sc = $("laneWrap");
  // Åpne med dagens dato i synsfeltet, og la tittelen i lange barer følge med når man scroller
  sc.scrollLeft = Math.max(0, (nowYear() - minYear) * PX_PER_YEAR - sc.clientWidth * 0.7);
  const follow = () => {
    const edge = sc.scrollLeft - 24;
    lane.querySelectorAll(".entry.range").forEach((b) => {
      const x = parseFloat(b.style.left), w = parseFloat(b.style.width);
      b.firstChild.style.paddingLeft = Math.min(Math.max(10, edge - x + 10), Math.max(10, w - 130)) + "px";
    });
  };
  sc.onscroll = follow; follow();
}

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
      <span class="when">${fmtDate(e)}${e.status === "ongoing" ? " · " + STR.ongoing : ""} · ${STR.cats[e.category]}</span>
      <h3>${e.projectPage ? `<a href="${pageUrl(e)}">${esc(loc(e, "title"))}</a>` : esc(loc(e, "title"))}</h3>
      <p>${esc(loc(e, "shortDescription"))}</p></article>`;
  byYear.forEach((items, y) => {
    const major = items.filter((e) => e.importance >= 50), minor = items.filter((e) => e.importance < 50);
    const g = document.createElement("div");
    g.className = "tl-year";
    g.innerHTML = `<h4>${y}</h4>${major.map(card).join("")}` +
      (minor.length ? `<details><summary>${minor.length} ${STR.more}</summary>${minor.map(card).join("")}</details>` : "");
    list.appendChild(g);
  });
  const empty = document.createElement("p");
  empty.className = "muted"; empty.id = "tlEmpty"; empty.hidden = true; empty.textContent = STR.empty; list.appendChild(empty);
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
  const any = entries.some((e) => matches(e, activeFilter));
  const emp = $("tlEmpty"); if (emp) emp.hidden = any;
}

// Tooltip (kun på desktop)
const tip = $("tip");
function showTip(e, el) {
  if (innerWidth < MOBILE_BREAK) return;
  const tags = loc(e, "tags") || [];
  tip.innerHTML = `<span class="tt-cat">${STR.cats[e.category]} · ${fmtDate(e)}${e.status === "ongoing" ? ` · <i class="dot"></i>${STR.ongoing}` : ""}</span>
    <strong class="tt-title">${esc(loc(e, "title"))}</strong>
    <p>${esc(loc(e, "shortDescription"))}</p>
    ${tags.length ? `<span class="tip-tags">${tags.map((t) => `<i>${esc(t)}</i>`).join("")}</span>` : ""}
    ${e.projectPage ? `<span class="tip-go">${STR.go}</span>` : ""}`;
  tip.hidden = false;
  const r = el.getBoundingClientRect(), tr = tip.getBoundingClientRect();
  const left = Math.min(Math.max(8, r.left + r.width / 2 - tr.width / 2), innerWidth - tr.width - 8);
  const top = r.top - tr.height - 12 > 8 ? r.top - tr.height - 12 : r.bottom + 12;
  tip.style.left = left + "px"; tip.style.top = top + "px";
}
const hideTip = () => { tip.hidden = true; };

$("filters").addEventListener("click", (ev) => {
  const b = ev.target.closest(".filter-chip");
  if (!b) return;
  activeFilter = b.dataset.filter;
  document.querySelectorAll(".filter-chip").forEach((x) => x.classList.toggle("on", x === b));
  applyFilter();
});

loadEntries().then((list) => {
  entries = list;
  if (!entries.length) throw new Error("ingen oppføringer");
  renderSwimlane(); renderList(); applyFilter();
}).catch((err) => { console.error(err); $("tlError").hidden = false; });

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
