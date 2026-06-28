# QCB5 DOT Safety — AGENTS.md

**Verified state:** `docs/status.md` (2026-06-19 evaluation). Read `README.md` for operator workflow.
Orientation for AI agents. Read `README.md`. **Reproduce outputs from committed `data_raw/` before changing methodology.**

## Standards (shared)

- Style: `~/sites/electoralanalytics-site/docs/style/README.md`

## What this is

Approval-rate analysis of NYC DOT safety requests in Queens CB5 (signals, speed reducers, crashes). Site slug: `qcb5-dot-safety`. Site layout: `analysis`.

## Data provenance

Signal studies `w76s-c5u4`, SRTS `9n6h-pt9g`, crashes `h9gi-nx95` (+ others in fetch script). CB5 polygon is sole geographic authority for coordinate-bearing layers.

## Pipeline

```bash
source .venv/bin/activate
python generate_charts.py && python generate_maps.py
python scripts_validate_outputs.py
python -m unittest discover -s tests
```

## Deployment

**`master` is the live line.** Pushes that change `output/` trigger an automatic site rebuild
(`.github/workflows/notify-site.yml` → `electoralanalytics-site` deploy). Monthly data refresh
runs on `master` via `.github/workflows/refresh-data.yml`.

Manual publish when needed: `npm run publish:project -- qcb5-dot-safety` from `electoralanalytics-site`
(see `publish/projects/qcb5-dot-safety.json`). CI also fetches maps from `master` at build time.
