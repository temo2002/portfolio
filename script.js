// ---------- Tidslinje ----------
// size: 1 = liten, 2 = middels, 3 = stor (betydning)
// cat: skole | jobb | hobby | ledelse | musikk
const ITEMS = [
  { start: 2018, end: "i dag", title: "Trompet ved Altaie", cat: ["musikk", "jobb"], size: 3,
    text: "Startet egen virksomhet med trompetopptredener i begravelser, bryllup og gudstjenester." },
  { start: 2018, end: 2021, title: "Idrettsfag, Vest-Lofoten videregående", cat: ["skole"], size: 2,
    text: "Videregående med idrettsfag. Her startet interessen for trening og lagarbeid." },
  { start: 2021, end: "i dag", title: "Deli de Luca, Leknes", cat: ["jobb"], size: 1,
    text: "Deltids- og sesongjobb på Esso-stasjonen i Leknes." },
  { start: 2023, end: 2024, title: "Forkurs i realfag", cat: ["skole"], size: 2,
    text: "Forkurs som åpnet døren til ingeniørstudier." },
  { start: 2024, end: 2027, title: "Elektronisk systemdesign, NTNU", cat: ["skole"], size: 3,
    text: "Bachelor i elektronisk systemdesign i Trondheim. Fokus på analog elektronikk, innebygde systemer og kommunikasjon." },
  { start: 2024, end: "i dag", title: "Tillitsvalgt og referansegrupper", cat: ["ledelse", "skole"], size: 2,
    text: "Klassens stemme inn mot instituttet, med plass i flere referansegrupper og en rolle i linjeforeningen." },
  { start: 2025, end: "i dag", title: "Nestleder, NTNUI Calisthenics", cat: ["ledelse", "hobby"], size: 3,
    text: "Nestleder siden januar 2025. Over 200 utøvere og 14 trenere å holde sammen." },
  { start: 2025, end: "i dag", title: "Lynkurs i C og analog elektronikk", cat: ["skole", "jobb"], size: 2,
    text: "Holdt egne kurs for medstudenter i C-programmering og filterdesign." },
  { start: 2026, end: "i dag", title: "Læringsassistent, IELS2021 og IELS2022", cat: ["skole", "jobb"], size: 3,
    text: "Veileder studenter i elektronikkfag, også i IELS2031." },
];
const CATS = [["alle", "Alle"], ["skole", "Skole"], ["jobb", "Jobb"], ["ledelse", "Ledelse"], ["hobby", "Hobby"], ["musikk", "Musikk"]];

const filters = document.getElementById("filters");
const list = document.getElementById("timeline");
let current = "alle";

function renderTimeline() {
  list.innerHTML = "";
  [...ITEMS].sort((a, b) => b.start - a.start).forEach(it => {
    const li = document.createElement("li");
    li.className = `tl s${it.size}` + (current !== "alle" && !it.cat.includes(current) ? " hide" : "");
    li.innerHTML = `<span class="when">${it.start} til ${it.end}</span><h3>${it.title}</h3><p>${it.text}</p>`;
    list.appendChild(li);
  });
}
CATS.forEach(([key, label]) => {
  const b = document.createElement("button");
  b.textContent = label;
  if (key === current) b.classList.add("on");
  b.onclick = () => {
    current = key;
    filters.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b));
    renderTimeline();
  };
  filters.appendChild(b);
});
renderTimeline();

// ---------- Oscilloskop i hero ----------
const scope = document.getElementById("scope");
const sctx = scope.getContext("2d");
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
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
  if (!reduce) { t += 0.04; requestAnimationFrame(drawScope); }
}
drawScope();

// ---------- RC-lavpassfilter (Bode) ----------
const bode = document.getElementById("bode");
const bctx = bode.getContext("2d");
const rIn = document.getElementById("r"), cIn = document.getElementById("c");
const fmt = (v, unit) => {
  const pre = [[1e6, "M"], [1e3, "k"], [1, ""], [1e-3, "m"], [1e-6, "µ"], [1e-9, "n"], [1e-12, "p"]];
  for (const [m, p] of pre) if (v >= m * 0.9995) return `${+(v / m).toPrecision(3)} ${p}${unit}`;
  return `${v} ${unit}`;
};
function drawBode() {
  const R = Math.pow(10, +rIn.value), C = Math.pow(10, +cIn.value);
  const fc = 1 / (2 * Math.PI * R * C);
  document.getElementById("rOut").textContent = fmt(R, "Ω");
  document.getElementById("cOut").textContent = fmt(C, "F");
  document.getElementById("fcOut").textContent = fmt(fc, "Hz");

  const w = bode.width, h = bode.height, L = 52, B = 34, T = 14, Rr = 16;
  const fMin = 1, fMax = 1e6, dbMin = -60, dbMax = 5;
  const X = f => L + (Math.log10(f) - Math.log10(fMin)) / (Math.log10(fMax) - Math.log10(fMin)) * (w - L - Rr);
  const Y = d => T + (dbMax - d) / (dbMax - dbMin) * (h - T - B);
  bctx.clearRect(0, 0, w, h);
  bctx.font = "12px ui-monospace, monospace"; bctx.fillStyle = "#8d95b8"; bctx.strokeStyle = "#1c2447"; bctx.lineWidth = 1;
  for (let e = 0; e <= 6; e++) {
    const x = X(Math.pow(10, e)); bctx.beginPath(); bctx.moveTo(x, T); bctx.lineTo(x, h - B); bctx.stroke();
    bctx.fillText(e === 0 ? "1" : e < 3 ? `${10 ** e}` : e < 6 ? `${10 ** (e - 3)}k` : "1M", x - 8, h - 14);
  }
  for (let d = 0; d >= dbMin; d -= 20) {
    const y = Y(d); bctx.beginPath(); bctx.moveTo(L, y); bctx.lineTo(w - Rr, y); bctx.stroke();
    bctx.fillText(`${d} dB`, 4, y + 4);
  }
  // -3 dB linje
  bctx.setLineDash([4, 4]); bctx.strokeStyle = "#f2b84b55";
  bctx.beginPath(); bctx.moveTo(L, Y(-3)); bctx.lineTo(w - Rr, Y(-3)); bctx.stroke(); bctx.setLineDash([]);
  // kurve
  bctx.strokeStyle = "#4fd1c5"; bctx.lineWidth = 2.5; bctx.beginPath();
  for (let i = 0; i <= 300; i++) {
    const f = Math.pow(10, (i / 300) * 6);
    const db = -10 * Math.log10(1 + (f / fc) ** 2);
    const x = X(f), y = Y(Math.max(db, dbMin));
    i ? bctx.lineTo(x, y) : bctx.moveTo(x, y);
  }
  bctx.stroke();
  // knekkpunkt
  if (fc >= fMin && fc <= fMax) {
    bctx.fillStyle = "#f2b84b"; bctx.beginPath(); bctx.arc(X(fc), Y(-3), 6, 0, 7); bctx.fill();
  }
}
rIn.oninput = cIn.oninput = drawBode;
drawBode();
