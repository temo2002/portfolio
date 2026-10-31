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
import html
import json
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
    entry.update(meta)
    if skip:
        return None, None
    entry["_pdf"] = f"reports/{folder.name}/{pdf.name}" if pdf is not None else None
    entry["_summary"] = shorten(summary, 700)
    entry["_lede"] = lede
    entry["_sections"] = sections
    entry["_links"] = links
    entry["_macros"] = macros
    return entry, "; ".join(notes) or None


# ---------- Side ----------

def render_sections(e, esc, pdf_rel):
    out = []
    for sec in e["_sections"]:
        body = "".join(f"<p>{esc(p)}</p>" for p in sec.get("paragraphs", []))
        if sec.get("bullets"):
            body += "<ul>" + "".join(f"<li>{esc(b)}</li>" for b in sec["bullets"]) + "</ul>"
        out.append(f'  <section class="project-section">\n    <h2>{esc(sec["title"])}</h2>\n    {body}\n  </section>')
    links = list(e["_links"])
    if pdf_rel:
        out.append(f'''  <section class="project-section">
    <h2>Rapporten</h2>
    <p class="project-links"><a class="btn primary" href="{esc(pdf_rel)}" target="_blank" rel="noopener">Åpne PDF ↗</a></p>
    <object class="pdf-view" data="{esc(pdf_rel)}#view=FitH" type="application/pdf" aria-label="Rapport som PDF">
      <p class="muted">Nettleseren din viser ikke PDF direkte. <a href="{esc(pdf_rel)}">Last ned rapporten her</a>.</p>
    </object>
  </section>''')
    if links:
        btns = " ".join(f'<a class="btn" href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l["label"])} ↗</a>' for l in links)
        out.append(f'  <section class="project-section">\n    <h2>Lenker</h2>\n    <p class="project-links">{btns}</p>\n  </section>')
    return "\n\n".join(out)

def render_page(e):
    esc = lambda s: html.escape(str(s), quote=True)
    m = e["_macros"]
    meta_bits = [f'<span class="cat-tag">{esc({"work": "jobb", "school": "skole", "hobby": "hobby"}.get(e["category"], e["category"]))}</span>',
                 f'<span class="project-year">{esc(e["start"][:4])}</span>']
    if m.get("versjon"):
        meta_bits.append(f'<span class="project-year">versjon {esc(m["versjon"])}</span>')
    lede = e["_lede"] or e["_summary"] or e["shortDescription"]
    tags = "".join(f"<li>{esc(t)}</li>" for t in e.get("tags", []))
    pdf_rel = "../" + e["_pdf"] if e["_pdf"] else None
    extra_sections = render_sections(e, esc, pdf_rel)
    return f"""<!DOCTYPE html>
<html lang="nb">
<head>
{MARK}
<!-- Denne siden er laget av tools/import_reports.py. Fjern merket over for å redigere den selv. -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(e["title"])} · Temmam Nabil Altaie</title>
<meta name="description" content="{esc(e["shortDescription"])}">
<meta name="theme-color" content="#0a0d18">
<link rel="icon" href="../icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../style.css">
<!-- seo:start -->
<!-- seo:end -->
</head>
<body>

<header class="nav">
  <a class="logo" href="../#top"><span class="logo-mark">TA</span> <span class="logo-text">temmam.altaie</span></a>
  <nav class="open-static">
    <a href="../#arbeid">Arbeid</a>
    <a href="../#tidslinje">Tidslinje</a>
    <a href="../#om">Om meg</a>
    <a href="../#kontakt">Kontakt</a>
  </nav>
</header>

<main class="project-page">
  <a class="back" href="../#tidslinje">← tilbake til tidslinjen</a>

  <div class="project-meta-row">{" ".join(meta_bits)}</div>

  <h1 class="project-title">{esc(e["title"])}</h1>
  <p class="project-lede">{esc(lede)}</p>
  <ul class="tags">{tags}</ul>

{extra_sections}
  <a class="back" href="../#tidslinje">← tilbake til tidslinjen</a>
</main>

<footer>
  <span>© <span id="year">2026</span> Temmam Nabil Altaie</span>
  <span>håndlaget · ingen rammeverk · servert av GitHub Pages</span>
</footer>
<script>document.getElementById("year").textContent = new Date().getFullYear();</script>
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


def main():
    reports = ROOT / "reports"
    if not reports.is_dir():
        print("Ingen reports/-mappe, ingenting å importere.")
        return
    data, pages = ROOT / "projects_data", ROOT / "projects"
    current, log = set(), []
    for folder in sorted(p for p in reports.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
        entry, note = build_entry(folder)
        if note:
            log.append(note)
        if not entry:
            continue
        current.add(entry["id"])
        jpath, hpath = data / f"{entry['id']}.json", pages / f"{entry['id']}.html"
        page = render_page(entry)
        public = {k: v for k, v in entry.items() if not k.startswith("_")}
        if jpath.exists() and not is_generated_json(jpath):
            log.append(f"{entry['id']}: JSON er redigert for hånd, ikke overskrevet")
        elif write_if_changed(jpath, json.dumps(public, ensure_ascii=False, indent=2) + "\n"):
            log.append(f"{entry['id']}: oppdaterte {jpath.relative_to(ROOT)}")
        if hpath.exists() and MARK not in hpath.read_text(encoding="utf-8"):
            log.append(f"{entry['id']}: siden er redigert for hånd, ikke overskrevet")
        elif write_if_changed(hpath, page):
            log.append(f"{entry['id']}: oppdaterte {hpath.relative_to(ROOT)}")

    # Rydd bort det vi laget selv for rapporter som er fjernet
    for jpath in sorted(data.glob("*.json")):
        if jpath.name != "manifest.json" and is_generated_json(jpath) and jpath.stem not in current:
            hpath = pages / f"{jpath.stem}.html"
            jpath.unlink()
            if hpath.exists() and MARK in hpath.read_text(encoding="utf-8"):
                hpath.unlink()
            log.append(f"{jpath.stem}: rapporten er fjernet, ryddet bort")

    print(f"{len(current)} rapport(er) funnet." + ("\n  - " + "\n  - ".join(log) if log else " Ingen endringer."))


if __name__ == "__main__":
    sys.exit(main())
