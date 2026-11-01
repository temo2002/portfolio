# Portefølje

Statisk nettside uten rammeverk og uten byggesteg for nettleseren. Hostes på GitHub Pages.

## Filstruktur

```
index.template.html   mal for forsidene (struktur)
i18n/no.json, en.json tekstene på norsk og engelsk
index.html, en/       genererte forsider (rediger ikke direkte)
style.css             alle stiler, også for prosjektsidene
script.js             tidslinje, filter, tooltip, skrivemaskin, demo
site.json             adresse, tittel og beskrivelse som brukes til SEO
serve.py              lokal server (bygger først)
tools/build_pages.py  lager index.html og en/index.html fra mal og språkfiler
tools/build.py        genererer manifest, sitemap, robots.txt og SEO-tagger
tools/import_reports.py  lager oppføring og side fra Overleaf-rapporter i reports/
projects_data/        én JSON-fil per tidslinjeoppføring + manifest.json (generert)
projects/             dypdykk, med _template.html som mal
.github/workflows/    bygger automatisk ved push
```

## Kjøre lokalt

```
python serve.py
```

Bygger først, og åpner siden på http://localhost:8080. Serveren lytter bare på din egen maskin.

## Skjule «Prøv selv»

`"showDemo": false` i `site.json` skjuler RC-filteret på forsiden. Sett den til `true` (eller fjern linjen) og kjør `python tools/build_pages.py` for å vise det igjen.

## Språk

Siden finnes på norsk (rotmappa) og engelsk (`en/`). Forsidetekstene ligger i `i18n/no.json` og `i18n/en.json`, og strukturen i `index.template.html`. Kjør `python tools/build_pages.py` etter endringer. Rapportsidene får engelsk tekst fra feltet `"en"` i `reports/<mappe>/meta.json` (tittel, beskrivelse, tagger, seksjoner og bildetekster). Mangler `"en"`, vises norsk tekst på begge språk. For oppføringer du skriver for hånd i `projects_data/` legger du `"en": {"title", "shortDescription", "tags"}` i JSON-filen.

## Legge til noe på tidslinjen

1. Lag `projects_data/ÅÅÅÅ-kort-navn.json`. Kopier en eksisterende fil.
2. Ferdig. Manifestet oppdateres av `tools/build.py` (lokalt via `serve.py`, og automatisk på GitHub ved push).

| Felt | Beskrivelse |
|---|---|
| `id` | Må være lik filnavnet uten `.json` |
| `title` | Tittel |
| `category` | `work`, `school` eller `hobby` |
| `isProject` | `true` hvis det skal komme med under filteret Prosjekter |
| `start` | `ÅÅÅÅ` eller `ÅÅÅÅ-MM` |
| `end` | `ÅÅÅÅ`, `ÅÅÅÅ-MM` eller `present` (valgfri) |
| `shortDescription` | Vises i tooltip og på mobil |
| `tags` | Liste med emneord |
| `importance` | 1 til 100. Styrer størrelse og plassering. Over 70 er stor |
| `status` | `ongoing`, `nda` eller `lost` (valgfri) |
| `types` | Ekstra filterord, for eksempel `["ledelse"]` (valgfri) |
| `projectPage` | Sti uten `.html`, for eksempel `projects/mitt-prosjekt` (valgfri) |

Bygg-skriptet gir en tydelig feilmelding hvis noe er feil i en JSON-fil, for eksempel en ugyldig dato eller en `projectPage` som ikke finnes.

## Lage et dypdykk

1. Kopier `projects/_template.html` til `projects/<navn>.html`.
2. Fyll inn innholdet.
3. Sett `"projectPage": "projects/<navn>"` i JSON-filen til oppføringen.

Raden på tidslinjen blir klikkbar, og siden havner automatisk i sitemap.xml.

## Det som genereres automatisk

`python tools/build.py` oppdaterer:

- `projects_data/manifest.json`
- `sitemap.xml` og `robots.txt`
- SEO-blokken (canonical, Open Graph, JSON-LD) mellom `<!-- seo:start -->` og `<!-- seo:end -->`

`python tools/build.py --check` feiler hvis noe er utdatert, uten å skrive noe.

Ved hver push til `main` kjører GitHub Actions det samme og committer eventuelle endringer. Husk å hente ned endringene (`git pull`) før du pusher igjen.

## Rapporter fra Overleaf

Rapporter blir til tidslinjeoppføring og dypdykkside automatisk.

1. I Overleaf: Menu, så Download, så **Source** (zip) og **PDF**.
2. Pakk ut i `reports/<ÅÅÅÅ-MM>-<navn>/`, for eksempel `reports/2026-09-iels2020-designprosjekt/`. Mappenavnet må starte med dato, og bør bare ha små bokstaver, tall og bindestrek. PDF-en må ligge i mappa som `main.pdf`.
3. Push. GitHub Actions kjører `tools/import_reports.py` og `tools/build.py` og committer resultatet. Lokalt gjør `python serve.py` det samme.

Skriptet leser `\dokumenttype`, `\fagkode`, `\dokumenttittel` og `\versjon` fra `main.tex`, og bruker `0.Sammendrag.tex` som ingress og kort beskrivelse. Designprosjekt får `isProject: true` og høyere vekt enn øvinger. Alt kan overstyres med en `meta.json` i rapportmappa, for eksempel:

```json
{ "importance": 85, "tags": ["filter", "opamp"], "end": "2026-12" }
```

`{ "skip": true }` i `meta.json` hopper over mappa. Filer skriptet har laget er merket og oppdateres hver gang. Fjern `"generated": true` fra JSON-filen, eller merkekommentaren øverst i HTML-siden, for å ta over en fil selv. Slettes rapportmappa, ryddes det som ble generert bort.

Husk at repoet er offentlig, så PDF-ene også er det. Sjekk at faget tillater å dele det du legger ut.

## Eget domene

1. Legg en fil som heter `CNAME` i rota, med bare domenet på én linje.
2. Pek DNS mot GitHub (se GitHubs dokumentasjon for Pages).
3. Endre `siteUrl` i `site.json`, og kjør `python tools/build.py`.
