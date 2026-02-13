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
| APS Installed | `de3m-c5p4` | Installed accessible pedestrian signals |
| Motor Vehicle Crashes | `h9gi-nx95` | Crash data for correlation |
| 311 Requests | `erm2-nwe9` | Maintenance complaints (less reliable for new infrastructure) |

## Analysis Logic

### Outcome Classification
- **Denied**: `statusdescription` contains "denial" OR "Engineering Study Completed" without approval
- **Approved**: Contains "approval", "approved", "aps installed", or "aps ranking"
- **Pending**: All other statuses

### CB5 Identification
- Signal Studies: Filter by borough='Queens' and street names within CB5 boundaries
- SRTS: `cb='405'` (Queens CB5 code format: borough 4 + district 05)
- See `REFERENCE_cb5_boundaries.md` for boundary filtering rules to exclude misattributed records north of the LIE

### APS Exclusion
Accessible Pedestrian Signals are **excluded** from approval rate calculations because they are court-mandated (federal lawsuit) and do not undergo standard merit-based review.

## Reference Documentation

- `REFERENCE_data_dictionary.md` - Field descriptions, status codes, denial reasons
- `REFERENCE_data_sources.md` - Dataset URLs and usage notes
- `REFERENCE_cb5_boundaries.md` - CB5 geographic boundaries and filtering logic
