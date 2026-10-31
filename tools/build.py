#!/usr/bin/env python3
"""Bygger det som skal genereres automatisk:

  - validerer alle JSON-filer i projects_data/
  - skriver projects_data/manifest.json (sortert etter startdato)
  - skriver sitemap.xml og robots.txt
  - oppdaterer SEO-blokken (canonical, Open Graph, Twitter, JSON-LD)
    mellom <!-- seo:start --> og <!-- seo:end --> i index.html og projects/*.html

Bruk:
  python tools/build.py          bygg og skriv filer
  python tools/build.py --check  feil (exit 1) hvis noe må bygges på nytt
"""
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "projects_data"
CATEGORIES = {"work", "school", "hobby"}
STATUSES = {"ongoing", "nda", "lost"}
DATE_RE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2]))?$")


def load_site():
    return json.loads((ROOT / "site.json").read_text(encoding="utf-8"))


def validate_entry(path, e):
    errs = []
    for key in ("id", "title", "category", "start", "shortDescription"):
        if key not in e:
            errs.append(f"mangler feltet '{key}'")
    if e.get("category") not in CATEGORIES:
        errs.append(f"category må være en av {sorted(CATEGORIES)}")
    if not DATE_RE.match(str(e.get("start", ""))):
        errs.append("start må være ÅÅÅÅ eller ÅÅÅÅ-MM")
    end = e.get("end")
    if end is not None and end != "present" and not DATE_RE.match(str(end)):
        errs.append("end må være ÅÅÅÅ, ÅÅÅÅ-MM eller 'present'")
    imp = e.get("importance", 40)
    if not isinstance(imp, int) or not 1 <= imp <= 100:
        errs.append("importance må være et heltall mellom 1 og 100")
    if "status" in e and e["status"] not in STATUSES:
        errs.append(f"status må være en av {sorted(STATUSES)}")
    page = e.get("projectPage")
    if page and not (ROOT / f"{page}.html").exists():
        errs.append(f"projectPage '{page}' finnes ikke som {page}.html")
    if e.get("id") and e["id"] != path.stem:
        errs.append(f"id '{e['id']}' bør være lik filnavnet '{path.stem}'")
    return errs


def build_manifest():
    entries, problems = [], []
    for p in sorted(DATA.glob("*.json")):
        if p.name == "manifest.json":
            continue
        try:
            e = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as ex:
            problems.append(f"{p.name}: ugyldig JSON ({ex})")
            continue
        errs = validate_entry(p, e)
        problems += [f"{p.name}: {m}" for m in errs]
        entries.append((str(e.get("start", "")), p.name))
    entries.sort()
    return [name for _, name in entries], problems


def page_list():
    pages = [ROOT / "index.html", ROOT / "en" / "index.html"]
    for d in ("projects", "en/projects"):
        pages += sorted(p for p in (ROOT / d).glob("*.html") if not p.name.startswith("_"))
    return [p for p in pages if p.exists()]


def url_for(site, page):
    base = site["siteUrl"].rstrip("/")
    rel = page.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return base + "/"
    if rel == "en/index.html":
        return base + "/en/"
    return f"{base}/{rel}"


def alternates(site, page):
    """(norsk url, engelsk url) for en side og dens språkmotstykke."""
    rel = page.relative_to(ROOT).as_posix()
    no_rel = rel[3:] if rel.startswith("en/") else rel
    en_rel = rel if rel.startswith("en/") else "en/" + rel
    return url_for(site, ROOT / no_rel), url_for(site, ROOT / en_rel)


def meta_of(text, pattern, default=""):
    m = re.search(pattern, text, re.S)
    return html.unescape(m.group(1).strip()) if m else default


def seo_block(site, page, text):
    url = url_for(site, page)
    no_url, en_url = alternates(site, page)
    lang = meta_of(text, r'<html lang="(\w+)"', "nb")
    is_en = lang == "en"
    title = meta_of(text, r"<title>(.*?)</title>", site["title"])
    desc = meta_of(text, r'<meta name="description" content="(.*?)"', site["description"])
    img = site["siteUrl"].rstrip("/") + "/" + site["image"]
    e = lambda s: html.escape(s, quote=True)
    is_index = page.name == "index.html"
    lines = [
        f'<link rel="canonical" href="{e(url)}">',
        f'<link rel="alternate" hreflang="nb" href="{e(no_url)}">',
        f'<link rel="alternate" hreflang="en" href="{e(en_url)}">',
        f'<link rel="alternate" hreflang="x-default" href="{e(no_url)}">',
        f'<meta property="og:type" content="{"website" if is_index else "article"}">',
        f'<meta property="og:locale" content="{"en_US" if is_en else site["locale"]}">',
        f'<meta property="og:locale:alternate" content="{site["locale"] if is_en else "en_US"}">',
        f'<meta property="og:site_name" content="{e(site["name"])}">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(desc)}">',
        f'<meta property="og:url" content="{e(url)}">',
        f'<meta property="og:image" content="{e(img)}">',
        '<meta name="twitter:card" content="summary_large_image">',
    ]
    if is_index:
        ld = {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": site["name"],
            "url": url,
            "jobTitle": site.get("jobTitleEn", site["jobTitle"]) if is_en else site["jobTitle"],
            "alumniOf": site["university"],
            "image": img,
            "inLanguage": lang,
        }
        lines.append('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>")
    return "\n".join(lines)


def apply_seo(site, page):
    text = page.read_text(encoding="utf-8")
    pat = re.compile(r"(<!-- seo:start -->).*?(<!-- seo:end -->)", re.S)
    if not pat.search(text):
        return None
    new = pat.sub(lambda m: f"{m.group(1)}\n{seo_block(site, page, text)}\n{m.group(2)}", text)
    return page, new


def sitemap(site, pages):
    today = date.today().isoformat()
    rows = "".join(
        f"  <url>\n    <loc>{html.escape(url_for(site, p))}</loc>\n    <lastmod>{today}</lastmod>\n  </url>\n"
        for p in pages
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}</urlset>\n'


def main():
    check = "--check" in sys.argv
    site = load_site()
    names, problems = build_manifest()
    if problems:
        print("Feil i prosjektdata:")
        for p in problems:
            print("  -", p)
        sys.exit(1)

    outputs = {DATA / "manifest.json": json.dumps(names, indent=2, ensure_ascii=False) + "\n"}
    outputs[ROOT / "robots.txt"] = f"User-agent: *\nAllow: /\n\nSitemap: {site['siteUrl'].rstrip('/')}/sitemap.xml\n"

    pages = page_list()
    for pg in pages:
        res = apply_seo(site, pg)
        if res:
            outputs[res[0]] = res[1]

    # Sitemap: behold forrige lastmod hvis URL-listen er uendret, så sjekken ikke endrer seg hver dag
    sm_path = ROOT / "sitemap.xml"
    new_sm = sitemap(site, pages)
    if sm_path.exists():
        old = sm_path.read_text(encoding="utf-8")
        strip = lambda s: re.sub(r"<lastmod>.*?</lastmod>", "", s)
        if strip(old) == strip(new_sm):
            new_sm = old
    outputs[sm_path] = new_sm

    changed = [p for p, content in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != content]
    if check:
        if changed:
            print("Disse filene må bygges på nytt (kjør python tools/build.py):")
            for p in changed:
                print("  -", p.relative_to(ROOT))
            sys.exit(1)
        print("Alt er oppdatert.")
        return
    for p in changed:
        p.write_text(outputs[p], encoding="utf-8")
    print(f"{len(names)} oppføringer, {len(pages)} sider. Skrev: " + (", ".join(p.relative_to(ROOT).as_posix() for p in changed) or "ingenting nytt"))


if __name__ == "__main__":
    main()
