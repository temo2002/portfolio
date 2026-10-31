#!/usr/bin/env python3
"""Lager forsidene fra index.template.html og språkfilene i i18n/.

  i18n/no.json  ->  index.html
  i18n/en.json  ->  en/index.html

Rediger tekstene i språkfilene (eller strukturen i malen), ikke i de genererte filene.
SEO-blokken (<!-- seo:start --> ... <!-- seo:end -->) fylles av tools/build.py og beholdes her.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEO = re.compile(r"(<!-- seo:start -->)(.*?)(<!-- seo:end -->)", re.S)


def asset_v(name):
    return hashlib.md5((ROOT / name).read_bytes()).hexdigest()[:8]


def render(template, strings, lang):
    missing = sorted(set(re.findall(r"\{\{(\w+)\}\}", template)) - set(strings))
    if missing:
        sys.exit(f"i18n/{lang}.json mangler nøkler: {', '.join(missing)}")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: strings[m.group(1)], template)


def main():
    check = "--check" in sys.argv
    template = (ROOT / "index.template.html").read_text(encoding="utf-8")
    stale = []
    for lang, out in (("no", "index.html"), ("en", "en/index.html")):
        strings = json.loads((ROOT / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        strings.update({"v_css": asset_v("style.css"), "v_js": asset_v("script.js")})
        html = render(template, strings, lang)
        path = ROOT / out
        if path.exists():  # behold SEO-blokken som build.py har fylt ut
            old = SEO.search(path.read_text(encoding="utf-8"))
            if old:
                html = SEO.sub(lambda m: m.group(1) + old.group(2) + m.group(3), html, count=1)
        if not path.exists() or path.read_text(encoding="utf-8") != html:
            stale.append(out)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(html, encoding="utf-8")
    if check and stale:
        print("Disse sidene må bygges på nytt (kjør python tools/build_pages.py):", ", ".join(stale))
        sys.exit(1)
    print("Skrev: " + ", ".join(stale) if stale and not check else "Forsidene er oppdatert.")


if __name__ == "__main__":
    main()
