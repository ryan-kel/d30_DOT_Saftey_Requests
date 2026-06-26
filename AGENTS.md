# QCB5 DOT Safety — AGENTS.md

**Verified state:** `docs/status.md` (2026-06-19 evaluation). Read `README.md` for operator workflow.
Orientation for AI agents. Read `README.md`. **Reproduce outputs from committed `data_raw/` before changing methodology.**

## Standards (shared)

- Writing: `~/shared/docs/ea-writing-standards.md`
- Style guides: `~/sites/electoralanalytics-site/docs/style/README.md`

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

Charts/maps copied via site `fetch-maps.sh` / publish pipeline. See `electoralanalytics-site` `publish/projects/qcb5-dot-safety.json`.
