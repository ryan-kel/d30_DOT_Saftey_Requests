# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a data analysis project examining NYC DOT safety infrastructure request outcomes for Queens Community Board 5 (CB5). The analysis calculates "batting average" (approval rates) for traffic signals, stop signs, speed bumps, and other safety requests, comparing CB5 to citywide baselines.

## Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Fetch fresh data from NYC Open Data API
python scripts_fetch_data.py

# Generate all charts (Part 1)
python generate_charts.py

# Generate maps & crash-denial correlation analysis (Part 2)
python generate_maps.py

# View analysis notebook (displays charts, doesn't generate them)
jupyter notebook analysis_notebook.ipynb
```

## Data Pipeline

1. **Data Fetching**: `scripts_fetch_data.py` downloads from NYC Open Data Socrata API
2. **Raw Storage**: CSV files saved to `data_raw/`
3. **Chart Generation**: `generate_charts.py` creates all charts from raw data (Part 1)
4. **Map & Correlation Generation**: `generate_maps.py` geocodes intersections, runs proximity analysis, generates interactive maps and correlation charts (Part 2)
5. **Analysis**: `analysis_notebook.ipynb` displays charts and summary statistics
6. **Output**: Charts (PNG), maps (HTML), and processed data saved to `output/`

## Key Datasets

| Dataset | Endpoint ID | Purpose |
|---------|-------------|---------|
| Signal Studies | `w76s-c5u4` | Primary - traffic signals, stop signs, APS requests |
| Speed Reducers (SRTS) | `9n6h-pt9g` | Speed bump/hump requests |
| Motor Vehicle Crashes | `h9gi-nx95` | Crash data for correlation |

*Note: `scripts_fetch_data.py` also downloads APS Installed (`de3m-c5p4`) and 311 Requests (`erm2-nwe9`) but these are not consumed by the analysis pipeline.*

## Analysis Logic

### Outcome Classification
- **Denied**: `statusdescription` contains "denial" OR "Engineering Study Completed" without approval
- **Approved**: Contains "approval", "approved", "aps installed", or "aps ranking"
- **Pending**: All other statuses

### CB5 Identification

**CRITICAL: All three datasets MUST be filtered using the official CB5 polygon (shapely point-in-polygon). Never rely solely on field-level filters.**

- **Signal Studies**: Filter by borough='Queens' and street names within CB5 boundaries → then polygon filter on geocoded coordinates
- **SRTS (Speed Bumps)**: Two filtering layers:
  1. `cb='405'` (Queens CB5 code format: borough 4 + district 05)
  2. **Polygon boundary filter** (shapely point-in-polygon against official CB5 GeoJSON) — **sole geographic authority**

  **WARNING:** `cb=405` alone is insufficient — ~26 records pass the cb filter but fall outside the actual CB5 polygon. In `generate_maps.py`, use `_load_cb5_srts_full()` which applies both layers automatically. **Never load SRTS data directly from CSV with only `cb=405`.** The polygon is the sole geographic authority — no street-name heuristics.
- **Crashes**: No community board field — uses polygon filter exclusively
- See `REFERENCE_cb5_boundaries.md` for boundary filtering rules

### Coordinate Filtering Rule

The `_filter_points_in_cb5()` function in both scripts filters geographic data against the CB5 polygon. **Rows without valid coordinates are excluded** (not included by default). This prevents no-coordinate rows from inflating counts.

### APS Exclusion
Accessible Pedestrian Signals are **excluded** from approval rate calculations because they are court-mandated (federal lawsuit) and do not undergo standard merit-based review.

## Visual Style Guide

**`STYLE_GUIDE.md`** — Official color palette, typography, chart conventions, and map standards. **All visualizations must follow this guide.** Key rules:
- QCB5 = navy `#2C5F8B`, Citywide = goldenrod `#B8860B`, Denied = red `#B44040`, Approved = green `#4A7C59`
- Every chart title: year range (YYYY–YYYY), sample size (n=), QCB5 shorthand
- Main charts = 2020–2025; z-series = actual year range, capped at 2025

## Shared Helper Functions (generate_maps.py)

| Function | Purpose |
|----------|---------|
| `_load_cb5_srts_full()` | Load SRTS data with full CB5 pipeline (cb=405 + polygon filter). **All SRTS charts must use this.** |
| `_normalize_intersection(a, b)` | Alphabetically sort two street names so "A & B" == "B & A". Prevents reversed-name duplicates. |
| `_spatial_dedup(df, radius_m)` | Greedy spatial de-duplication: sort by crashes desc, skip entries within `radius_m` of already-selected locations. Used at 150m for top-15 rankings. |
| `_filter_points_in_cb5(df)` | Polygon filter against official CB5 boundary. Excludes rows without coordinates. |

## Reference Documentation

- `STYLE_GUIDE.md` - **Official visual style guide** (colors, typography, chart/map conventions)
- `REFERENCE_data_dictionary.md` - Field descriptions, status codes, denial reasons
- `REFERENCE_data_sources.md` - Dataset URLs and usage notes
- `REFERENCE_cb5_boundaries.md` - CB5 geographic boundaries and filtering logic
- `output/METHODOLOGY.md` - Full methodology, decision log, and audit trail
