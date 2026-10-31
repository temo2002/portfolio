# Portefølje

Statisk nettside uten rammeverk og uten byggesteg for nettleseren. Hostes på GitHub Pages.

## Filstruktur

```
index.html            forsiden
style.css             alle stiler, også for prosjektsidene
script.js             tidslinje, filter, tooltip, skrivemaskin, demo
site.json             adresse, tittel og beskrivelse som brukes til SEO
serve.py              lokal server (bygger først)
tools/build.py        genererer manifest, sitemap, robots.txt og SEO-tagger
projects_data/        én JSON-fil per tidslinjeoppføring + manifest.json (generert)
projects/             dypdykk, med _template.html som mal
.github/workflows/    bygger automatisk ved push
```

## Kjøre lokalt

```
python serve.py
```

Bygger først, og åpner siden på http://localhost:8080. Serveren lytter bare på din egen maskin.

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

## Eget domene

1. Legg en fil som heter `CNAME` i rota, med bare domenet på én linje.
2. Pek DNS mot GitHub (se GitHubs dokumentasjon for Pages).
3. Endre `siteUrl` i `site.json`, og kjør `python tools/build.py`.
