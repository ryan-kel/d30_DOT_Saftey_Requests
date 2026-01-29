# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Geospatial analysis correlating rejected NYC DOT safety requests with traffic accidents in Queens Community Board 5. Uses NYC Open Data APIs to demonstrate potential correlations between denied safety infrastructure requests and subsequent vehicle collisions.

## Tech Stack

- **Python 3.x** with pandas, numpy, geopandas
- **Visualization:** matplotlib, seaborn, folium (interactive maps)
- **Data Source:** NYC Open Data Socrata API

## Running Analysis Scripts

```bash
# Generate visualization charts
python chart_builder.py

# Main correlation analysis
python correlation_analysis.py

# Build interactive map (outputs index.html)
python map_builder.py

# Launch local server at http://localhost:8000
python start_server.py

# Specialized analyses
python infrastructure_analysis.py
python maintenance_analysis.py
python identify_denied_crashes.py
python identify_pending_risks.py
python baseline_benchmark.py

# Data quality audits
python data_dictionary_audit.py
python check_complaint_types.py
```

## Architecture

### Data Pipeline
`chart_builder.fetch_data()` is the central data fetching function used across all analysis modules. It queries NYC Open Data via Socrata API with SQL-like WHERE clauses.

### Analysis Modules
Each analysis script is standalone and follows the pattern:
1. Fetch data via `chart_builder.fetch_data()` or direct API calls
2. Apply spatial/temporal correlation logic
3. Output results as CSV + PNG charts

### Key Constants (found at top of each module)
- **RADIUS_METERS:** 150m spatial correlation threshold
- **TIME_WINDOW_DAYS:** 180 days post-decision window
- **TARGET_ZIPS:** ['11378', '11379', '11385']
- **REJECTION_KEYWORDS:** ["not warranted", "condition not found", "insufficient", "denied", "no action necessary"]

## Code Patterns

### Spatial Calculations
Uses vectorized numpy haversine distance calculations. Always convert degrees to radians before trigonometry. Filter by time BEFORE spatial to optimize O(N*M) comparisons.

### Data Type Handling
- Coerce string coordinates to numeric with `errors='coerce'`
- Use `.dropna(subset=[cols])` for missing coordinate/date validation
- Street name normalization: AVE→AVENUE, ST→STREET, RD→ROAD

### API Calls
```python
url = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"
# Use $where for SQL filtering, $limit for record limits
```

## NYC Open Data Datasets

| Dataset | ID | Description |
|---------|-----|-------------|
| 311 Service Requests | erm2-nwe9 | DOT complaints and resolutions |
| Motor Vehicle Collisions | h9gi-nx95 | NYPD crash data |
| Traffic Studies | w76s-c5u4 | DOT traffic study results |
| Community Districts | 5crt-au7u | GeoJSON boundaries |

## Known Data Issues

- Traffic Studies dataset lacks coordinates (requires geocoding via 311 intersection lookup)
- ~10-20% geocoding failure rate for street intersections
- Some outlier coordinates exist outside Queens (boundary filtering handles this)
- API limit: 50,000 records per call
