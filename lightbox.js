"use strict";
// Enkel lightbox for galleriet på prosjektsidene: klikk, piltaster, Esc og sveip.
(function () {
  const tiles = Array.from(document.querySelectorAll("a.tile"));
  if (!tiles.length) return;

  const ov = document.createElement("div");
  ov.className = "lb"; ov.hidden = true; ov.setAttribute("role", "dialog"); ov.setAttribute("aria-modal", "true"); ov.setAttribute("aria-label", "Bildevisning");
  ov.innerHTML = '<div class="lb-c"></div><button class="lb-x" aria-label="Lukk">×</button>' +
    '<button class="lb-p" aria-label="Forrige bilde">‹</button><button class="lb-n" aria-label="Neste bilde">›</button>' +
    '<figure><img alt=""><figcaption></figcaption></figure>';
  document.body.appendChild(ov);
  const img = ov.querySelector("img"), cap = ov.querySelector("figcaption"), count = ov.querySelector(".lb-c");
  let i = 0, opener = null;

  function show(n) {
    i = (n + tiles.length) % tiles.length;
    const t = tiles[i], im = t.querySelector("img");
    img.src = t.href; img.alt = im.alt || "";
    img.style.setProperty("--bg", getComputedStyle(t).getPropertyValue("--bg") || "#fff");
    cap.textContent = t.dataset.caption || "";
    count.textContent = (i + 1) + " / " + tiles.length;
    const nxt = new Image(); nxt.src = tiles[(i + 1) % tiles.length].href; // forhåndslast neste
  }
  function open(n, from) { opener = from; show(n); ov.hidden = false; document.body.classList.add("lb-open"); ov.querySelector(".lb-x").focus(); }
  function close() { ov.hidden = true; document.body.classList.remove("lb-open"); img.removeAttribute("src"); if (opener) opener.focus(); }

  tiles.forEach((t, n) => t.addEventListener("click", (e) => { e.preventDefault(); open(n, t); }));
  ov.querySelector(".lb-x").addEventListener("click", close);
  ov.querySelector(".lb-p").addEventListener("click", () => show(i - 1));
  ov.querySelector(".lb-n").addEventListener("click", () => show(i + 1));
  ov.addEventListener("click", (e) => { if (e.target === ov) close(); });
  document.addEventListener("keydown", (e) => {
    if (ov.hidden) return;
    if (e.key === "Escape") close();
    else if (e.key === "ArrowLeft") show(i - 1);
    else if (e.key === "ArrowRight") show(i + 1);
  });
  let x0 = null;
  ov.addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  ov.addEventListener("touchend", (e) => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0; x0 = null;
    if (Math.abs(dx) > 50) show(i + (dx < 0 ? 1 : -1));
  });
})();
