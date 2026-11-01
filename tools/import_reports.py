#!/usr/bin/env python3
"""Lager tidslinjeoppføringer og dypdykksider fra Overleaf-rapporter.

Hver rapport ligger i sin egen mappe under reports/:

  reports/2026-09-iels2020-designprosjekt/
    main.pdf                      (påkrevd, kompilert PDF fra Overleaf)
    main.tex                      (valgfri, leses for metadata)
    1.Seksjoner/0.Sammendrag.tex  (valgfri, brukes som ingress)
    meta.json                     (valgfri, overstyrer alt som er funnet)

Mappenavnet bør starte med ÅÅÅÅ- eller ÅÅÅÅ-MM-, som blir startdato.

Skriptet leser \\dokumenttype, \\dokumentnr, \\fagkode, \\dokumenttittel og
\\versjon fra main.tex (malen din), og lager:
  projects_data/<mappenavn>.json
  projects/<mappenavn>.html

Filer som skriptet har laget selv er merket ("generated": true i JSON,
en kommentar i HTML) og oppdateres hver gang. Fjern merket for å ta over
en fil selv, så blir den aldri overskrevet.

Bruk:
  python tools/import_reports.py
"""
import hashlib
import html
import json
from urllib.parse import quote
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARK = "<!-- generated:import_reports -->"
MACROS = ["dokumenttype", "dokumentnr", "fagkode", "dokumenttittel", "forfatter", "versjon"]


# ---------- LaTeX-lesing ----------
def strip_comments(tex):
    return re.sub(r"(?<!\\)%.*", "", tex)


def read_braced(text, pos):
    """Leser innholdet i {...} som starter på pos, med nøstede klammer."""
    depth, i, start = 0, pos, pos + 1
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return None


def read_macros(tex):
    tex = strip_comments(tex)
    found = {}
    for name in MACROS:
        pat = re.compile(r"\\(?:re)?(?:newcommand|providecommand|def)\s*\{?\\" + name + r"\}?\s*(?:\[\d\])?\s*\{")
        m = pat.search(tex)
        if m:
            val = read_braced(tex, m.end() - 1)
            if val is not None:
                found[name] = clean_tex(val)
    return found


UNITS = {
    "kilo": "k", "mega": "M", "giga": "G", "milli": "m", "micro": "µ", "nano": "n", "pico": "p",
    "hertz": "Hz", "ohm": "Ω", "volt": "V", "ampere": "A", "farad": "F", "henry": "H", "watt": "W",
    "second": "s", "metre": "m", "meter": "m", "gram": "g", "decibel": "dB", "percent": "%",
    "degreeCelsius": "°C", "celsius": "°C", "per": "/", "squared": "²", "cubed": "³", "tothe": "^",
    "bit": "bit", "byte": "B", "volt": "V", "coulomb": "C", "joule": "J", "lumen": "lm", "lux": "lx",
}
ACCENTS = {'"': "\u0308", "'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303"}
LETTERS = {"aa": "å", "AA": "Å", "ae": "æ", "AE": "Æ", "oe": "œ", "o": "ø", "O": "Ø", "ss": "ß"}


def convert_unit(u):
    u = re.sub(r"\\([a-zA-Z]+)", lambda m: UNITS.get(m.group(1), m.group(1)), u)
    return re.sub(r"[{}\s]", "", u)


def convert_accents(s):
    import unicodedata
    s = re.sub(r"\\(aa|AA|ae|AE|oe|ss|o|O)(?![a-zA-Z])\s?(?:\{\})?", lambda m: LETTERS[m.group(1)], s)
    def acc(m):
        return unicodedata.normalize("NFC", m.group(2) + ACCENTS[m.group(1)])
    return re.sub(r"\\([\"'`^~])\s*\{?([a-zA-Z])\}?", acc, s)


def clean_tex(s):
    s = strip_comments(s)
    s = convert_accents(s)
    s = re.sub(r"\\(?:label|cite|citep|citet|cref|Cref|ref|eqref|autocite)\s*\{[^}]*\}", "", s)
    s = re.sub(r"\\(?:usectionn|section\*?|subsection\*?|subsubsection\*?)\s*\{[^}]*\}", "", s)
    s = re.sub(r"\\(?:SI|qty)\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}\s*\{((?:[^{}]|\{[^}]*\})*)\}", lambda m: f"{m.group(1)} {convert_unit(m.group(2))}", s)
    s = re.sub(r"\\(?:si|unit)\s*\{((?:[^{}]|\{[^}]*\})*)\}", lambda m: convert_unit(m.group(1)), s)
    s = re.sub(r"\\(?:num)\s*\{([^}]*)\}", r"\1", s)
    s = s.replace("\\\\", " ").replace("\\%", "%").replace("\\&", "&").replace("\\_", "_").replace("~", " ")
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", s)
    s = re.sub(r"[{}$]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def read_summary(folder):
    """Finner sammendraget (0.Sammendrag*.tex) og returnerer ren tekst."""
    cands = sorted(folder.glob("**/0.Sammendrag*.tex")) + sorted(folder.glob("**/Sammendrag*.tex"))
    if not cands:
        return ""
    raw = cands[0].read_text(encoding="utf-8", errors="ignore")
    paragraphs = [clean_tex(p) for p in re.split(r"\n\s*\n", strip_comments(raw))]
    paragraphs = [p for p in paragraphs if len(p) > 40]
    return " ".join(paragraphs[:2])


def shorten(text, limit):
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return (cut[: end + 1] if end > limit * 0.5 else cut.rsplit(" ", 1)[0] + "…").strip()


# ---------- Oppføring ----------
def parse_start(folder_name, pdf):
    m = re.match(r"^(\d{4})(?:-(\d{2}))?-", folder_name)
    if m:
        return m.group(1) + (f"-{m.group(2)}" if m.group(2) else ""), True
    ref = pdf if pdf is not None else ROOT
    return datetime.fromtimestamp(ref.stat().st_mtime).strftime("%Y-%m"), False


def build_entry(folder):
    meta, notes = {}, []
    meta_path = folder / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as ex:
            notes.append(f"{folder.name}/meta.json er ugyldig JSON ({ex}), ignorert")
    pdfs = [folder / "main.pdf"] if (folder / "main.pdf").exists() else sorted(folder.glob("*.pdf"))
    pdf = pdfs[0] if pdfs else None
    if pdf is None and not meta.get("noPdf"):
        return None, f"{folder.name}: fant ingen PDF, hoppet over (bruk noPdf: true i meta.json for en side uten PDF)"
    macros = {}
    if (folder / "main.tex").exists():
        macros = read_macros((folder / "main.tex").read_text(encoding="utf-8", errors="ignore"))
    summary = read_summary(folder)
    kind = macros.get("dokumenttype", "")
    fag = macros.get("fagkode", "")
    title = macros.get("dokumenttittel") or folder.name.replace("-", " ")
    if fag and fag.lower() not in title.lower():
        title = f"{title} ({fag})"
    start, from_name = parse_start(folder.name, pdf)
    is_design = "design" in kind.lower()
    entry = {
        "id": folder.name,
        "title": title,
        "category": "school",
        "isProject": is_design,
        "start": start,
        "shortDescription": shorten(summary, 190) if summary else (f"{kind} i {fag}".strip() or "Rapport"),
        "tags": [t for t in [fag, kind.lower(), "rapport"] if t],
        "importance": 60 if is_design else 35,
        "projectPage": f"projects/{folder.name}",
        "generated": True,
    }
    if not from_name:
        notes.append(f"{folder.name}: mappenavnet starter ikke med ÅÅÅÅ-MM-, brukte filens dato ({start})")
    skip = bool(meta.pop("skip", False))
    meta.pop("noPdf", None)
    lede = meta.pop("lede", "")
    sections = meta.pop("sections", [])
    links = meta.pop("links", [])
    en = meta.pop("en", None)
    hero = meta.pop("hero", None)
    figures = meta.pop("figures", [])
    # Portrett og nesten kvadratiske bilder fungerer dårlig som bredt toppbilde: legg dem først i galleriet
    if hero and hero.get("w") and hero.get("h") and hero["w"] / hero["h"] < 1.2:
        figures = [hero] + figures
        hero = None
    entry.update(meta)
    if skip:
        return None, None
    entry["_pdf"] = f"reports/{folder.name}/{pdf.name}" if pdf is not None else None
    entry["_summary"] = shorten(summary, 700)
    entry["_lede"] = lede
    entry["_sections"] = sections
    entry["_links"] = links
    entry["_hero"] = hero
    entry["_en"] = en or {}
    if en:  # tittel, beskrivelse og tagger leses av tidslinjen på engelsk
        entry["en"] = {k: en[k] for k in ("title", "label", "shortDescription", "tags") if k in en}
    entry["_figures"] = figures
    entry["_macros"] = macros
    return entry, "; ".join(notes) or None


# ---------- Side ----------
UI = {
    "no": {"html": "nb", "back": "← tilbake til tidslinjen", "ids": {"work": "arbeid", "timeline": "tidslinje", "about": "om", "contact": "kontakt"},
           "nav": {"work": "Arbeid", "timeline": "Tidslinje", "about": "Om meg", "contact": "Kontakt"},
           "cats": {"work": "jobb", "school": "skole", "hobby": "hobby"}, "version": "versjon", "report": "Rapporten", "open_pdf": "Åpne PDF",
           "no_pdf": "Nettleseren din viser ikke PDF direkte.", "download": "Last ned rapporten her", "links": "Lenker", "figures": "Figurer",
           "footer": "håndlaget · ingen rammeverk · servert av GitHub Pages", "pdf_aria": "Rapport som PDF", "alt_label": "EN", "alt_title": "English version",
           "locale": "nb"},
    "en": {"html": "en", "back": "← back to the timeline", "ids": {"work": "work", "timeline": "timeline", "about": "about", "contact": "contact"},
           "nav": {"work": "Work", "timeline": "Timeline", "about": "About", "contact": "Contact"},
           "cats": {"work": "work", "school": "school", "hobby": "hobby"}, "version": "version", "report": "The report", "open_pdf": "Open PDF",
           "no_pdf": "Your browser cannot display PDFs directly.", "download": "Download the report here", "links": "Links", "figures": "Figures",
           "footer": "handmade · no framework · served by GitHub Pages", "pdf_aria": "Report as PDF", "alt_label": "NO", "alt_title": "Norsk versjon",
           "locale": "en"},
}


def asset_v(name):
    return hashlib.md5((ROOT / name).read_bytes()).hexdigest()[:8]


def localize(e, lang):
    """Returnerer en kopi av oppføringen med tekster på valgt språk (norsk er standard)."""
    L = dict(e)
    en = e.get("_en") or {}
    caps = en.get("captions", {}) if lang == "en" else {}

    def cap(f):
        g = dict(f)
        if f["file"] in caps:
            g["caption"] = caps[f["file"]]
        return g

    secs = []
    for i, sec in enumerate(e["_sections"]):
        s2 = dict(sec)
        if lang == "en" and i < len(en.get("sections", [])):
            for k in ("title", "paragraphs", "bullets"):
                if k in en["sections"][i]:
                    s2[k] = en["sections"][i][k]
        s2["figures"] = [cap(f) for f in sec.get("figures", [])]
        secs.append(s2)
    L["_sections"] = secs
    L["_hero"] = cap(e["_hero"]) if e["_hero"] else None
    L["_figures"] = [cap(f) for f in e["_figures"]]
    if lang == "en":
        L["title"] = en.get("title", e["title"])
        L["shortDescription"] = en.get("shortDescription", e["shortDescription"])
        L["tags"] = en.get("tags", e.get("tags", []))
        L["_lede"] = en.get("lede") or (en.get("shortDescription") if en else "") or e["_lede"]
        labels = en.get("links", [])
        L["_links"] = [dict(l, label=labels[i]) if i < len(labels) else l for i, l in enumerate(e["_links"])]
    return L


def fig_html(e, f, esc, up, hero=False):
    """En figur som klikkbar rute i galleriet. Valgfrie felt: caption, alt, w, h, fit, bg."""
    url = f"{up}reports/{e['id']}/{f['file']}"
    w, h = f.get("w"), f.get("h")
    dims = f' width="{w}" height="{h}"' if w and h else ""
    fit = "contain" if hero else f.get("fit", "contain")
    bg = f.get("bg", "#0b0f20")
    cap_txt = f.get("caption", "")
    cap = f'<figcaption>{esc(cap_txt)}</figcaption>' if cap_txt else ""
    lazy = "" if hero else ' loading="lazy"'
    wide = bool(w and h and w / h > 3)
    cls = "fig fig-hero" if hero else ("fig wide" if wide else "fig")
    alt = esc(f.get("alt") or cap_txt)
    src_var = f";--src:url({esc(quote(url))})" if hero else ""
    return (f'<figure class="{cls}"><a class="tile" href="{esc(url)}" data-caption="{esc(cap_txt)}" '
            f'style="--bg:{esc(bg)};--fit:{fit}{src_var}"><img src="{esc(url)}" alt="{alt}"{dims}{lazy}></a>{cap}</figure>')


def fig_grid(e, figs, esc, up):
    return '<div class="gallery">' + "".join(fig_html(e, f, esc, up) for f in figs) + "</div>" if figs else ""


def render_sections(e, esc, pdf_rel, up, ui):
    out = []
    for sec in e["_sections"]:
        body = "".join(f"<p>{esc(p)}</p>" for p in sec.get("paragraphs", []))
        if sec.get("bullets"):
            body += "<ul>" + "".join(f"<li>{esc(b)}</li>" for b in sec["bullets"]) + "</ul>"
        body += fig_grid(e, sec.get("figures", []), esc, up)
        out.append(f'  <section class="project-section">\n    <h2>{esc(sec["title"])}</h2>\n    {body}\n  </section>')
    if e["_figures"]:
        out.append(f'  <section class="project-section">\n    <h2>{ui["figures"]}</h2>\n    {fig_grid(e, e["_figures"], esc, up)}\n  </section>')
    if pdf_rel:
        out.append(f"""  <section class="project-section">
    <h2>{ui["report"]}</h2>
    <p class="project-links"><a class="btn primary" href="{esc(pdf_rel)}" target="_blank" rel="noopener">{ui["open_pdf"]} ↗</a></p>
    <object class="pdf-view" data="{esc(pdf_rel)}#view=FitH" type="application/pdf" aria-label="{ui["pdf_aria"]}">
      <p class="muted">{ui["no_pdf"]} <a href="{esc(pdf_rel)}">{ui["download"]}</a>.</p>
    </object>
  </section>""")
    if e["_links"]:
        btns = " ".join(f'<a class="btn" href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l["label"])} ↗</a>' for l in e["_links"])
        out.append(f'  <section class="project-section">\n    <h2>{ui["links"]}</h2>\n    <p class="project-links">{btns}</p>\n  </section>')
    return "\n\n".join(out)


def render_page(e0, lang="no"):
    e = localize(e0, lang)
    ui = UI[lang]
    up = "../" if lang == "no" else "../../"
    esc = lambda s: html.escape(str(s), quote=True)
    m = e["_macros"]
    meta_bits = [f'<span class="cat-tag">{esc(ui["cats"].get(e["category"], e["category"]))}</span>',
                 f'<span class="project-year">{esc(e["start"][:4])}</span>']
    if m.get("versjon"):
        meta_bits.append(f'<span class="project-year">{ui["version"]} {esc(m["versjon"])}</span>')
    lede = e["_lede"] or e["_summary"] or e["shortDescription"]
    tags = "".join(f"<li>{esc(t)}</li>" for t in e.get("tags", []))
    pdf_rel = up + e["_pdf"] if e["_pdf"] else None
    extra_sections = render_sections(e, esc, pdf_rel, up, ui)
    hero_html = fig_html(e, e["_hero"], esc, up, hero=True) if e["_hero"] else ""
    ids = ui["ids"]
    alt_href = f"../en/projects/{e['id']}.html" if lang == "no" else f"../../projects/{e['id']}.html"
    alt_lang = "en" if lang == "no" else "nb"
    return f"""<!DOCTYPE html>
<html lang="{ui["html"]}">
<head>
{MARK}
<!-- Denne siden er laget av tools/import_reports.py. Fjern merket over for å redigere den selv. -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(e["title"])} · Temmam Nabil Altaie</title>
<meta name="description" content="{esc(e["shortDescription"])}">
<meta name="theme-color" content="#0a0d18">
<link rel="icon" href="{up}icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{up}style.css?v={asset_v("style.css")}">
<!-- seo:start -->
<!-- seo:end -->
</head>
<body>

<header class="nav">
  <a class="logo" href="../#top"><span class="logo-mark">TA</span> <span class="logo-text">temmam.altaie</span></a>
  <nav class="open-static">
    <a href="../#{ids["work"]}">{ui["nav"]["work"]}</a>
    <a href="../#{ids["timeline"]}">{ui["nav"]["timeline"]}</a>
    <a href="../#{ids["about"]}">{ui["nav"]["about"]}</a>
    <a href="../#{ids["contact"]}">{ui["nav"]["contact"]}</a>
    <a class="lang-switch" href="{alt_href}" hreflang="{alt_lang}" lang="{alt_lang}" title="{ui["alt_title"]}">{ui["alt_label"]}</a>
  </nav>
</header>

<main class="project-page">
  <a class="back" href="../#{ids["timeline"]}">{ui["back"]}</a>

  <div class="project-meta-row">{" ".join(meta_bits)}</div>

  <h1 class="project-title">{esc(e["title"])}</h1>
  <p class="project-lede">{esc(lede)}</p>
  <ul class="tags">{tags}</ul>
  {hero_html}

{extra_sections}

  <a class="back" href="../#{ids["timeline"]}">{ui["back"]}</a>
</main>

<footer>
  <span>© <span id="year">2026</span> Temmam Nabil Altaie</span>
  <span>{ui["footer"]}</span>
</footer>
<script>document.getElementById("year").textContent = new Date().getFullYear();</script>
<script src="{up}lightbox.js?v={asset_v("lightbox.js")}"></script>
</body>
</html>
"""


# ---------- Kjøring ----------
def is_generated_json(p):
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("generated") is True
    except (json.JSONDecodeError, OSError):
        return False


def write_if_changed(path, content):
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def page_path(entry_id, lang):
    return ROOT / ("projects" if lang == "no" else "en/projects") / f"{entry_id}.html"


def main():
    reports = ROOT / "reports"
    if not reports.is_dir():
        print("Ingen reports/-mappe, ingenting å importere.")
        return
    data = ROOT / "projects_data"
    current, log = set(), []
    for folder in sorted(p for p in reports.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
        entry, note = build_entry(folder)
        if note:
            log.append(note)
        if not entry:
            continue
        current.add(entry["id"])
        jpath = data / f"{entry['id']}.json"
        public = {k: v for k, v in entry.items() if not k.startswith("_")}
        if jpath.exists() and not is_generated_json(jpath):
            log.append(f"{entry['id']}: JSON er redigert for hånd, ikke overskrevet")
        elif write_if_changed(jpath, json.dumps(public, ensure_ascii=False, indent=2) + "\n"):
            log.append(f"{entry['id']}: oppdaterte {jpath.relative_to(ROOT)}")
        for lang in ("no", "en"):
            hpath = page_path(entry["id"], lang)
            if hpath.exists() and MARK not in hpath.read_text(encoding="utf-8"):
                log.append(f"{entry['id']} ({lang}): siden er redigert for hånd, ikke overskrevet")
            elif write_if_changed(hpath, render_page(entry, lang)):
                log.append(f"{entry['id']} ({lang}): oppdaterte {hpath.relative_to(ROOT)}")

    # Rydd bort det vi laget selv for rapporter som er fjernet
    for jpath in sorted(data.glob("*.json")):
        if jpath.name != "manifest.json" and is_generated_json(jpath) and jpath.stem not in current:
            jpath.unlink()
            for lang in ("no", "en"):
                hpath = page_path(jpath.stem, lang)
                if hpath.exists() and MARK in hpath.read_text(encoding="utf-8"):
                    hpath.unlink()
            log.append(f"{jpath.stem}: rapporten er fjernet, ryddet bort")

    print(f"{len(current)} rapport(er) funnet." + ("\n  - " + "\n  - ".join(log) if log else " Ingen endringer."))


if __name__ == "__main__":
    sys.exit(main())
