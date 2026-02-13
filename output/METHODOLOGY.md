# Chart Methodology & Decision Log

## Data Sources

All data was fetched from the NYC Open Data Socrata API on **2026-02-11**.

| Dataset | Endpoint ID | File | Rows | Date Range in Data | Columns |
|---------|-------------|------|------|--------------------|---------|
| Signal Studies | `w76s-c5u4` | `signal_studies_citywide.csv` | 74,485 | 1996-04-11 to 2026-01-20 | 57 |
| Speed Reducers (SRTS) | `9n6h-pt9g` | `srts_citywide.csv` | 58,198 | 1990-01-01 to 2026-02-09 | 42 |
| Motor Vehicle Crashes | `h9gi-nx95` | `crashes_queens_2020plus.csv` | 41,632 | 2020-01-01 to 2026-02-08 | 29 |
| CB5 Signal Studies | Derived | `data_cb5_signal_studies.csv` | 510 | 2020-01-07 to 2025-10-06 | 57 |

### Analysis Time Window

**Primary analysis window: 2020–2025.** All focused charts use this range for consistency. Rationale:

- CB5 signal study data only exists from 2020 onward (earliest record: 2020-01-07).
- Using 2020–2025 ensures apples-to-apples comparison between CB5 and citywide baselines.
- Data beyond 2025 exists in some datasets (into early 2026) but is excluded for consistency, as 2026 is incomplete.

**Z-series charts** provide full historical context using each dataset's complete available range, capped at 2025.

---

## Outcome Classification

Signal study records are classified into three outcomes based on the `statusdescription` field:

| Outcome | Logic |
|---------|-------|
| **Denied** | Status contains "denial" OR status is "Engineering Study Completed" without any approval language |
| **Approved** | Status contains "approval", "approved", "aps installed", "aps ranking", or "aps design" |
| **Pending** | All other statuses (excluded from rate calculations) |

Only **resolved** records (denied + approved) are used for denial rate calculations.

### Speed Bump Outcome Classification

SRTS records use the `segmentstatusdescription` field:

| Outcome | Value |
|---------|-------|
| **Denied** | "Not Feasible" |
| **Approved** | "Feasible" |

Only resolved records (Not Feasible + Feasible) are included in analysis.

---

## Exclusions

### Accessible Pedestrian Signals (APS)

APS requests are **excluded from all denial rate calculations** because they are court-mandated under a federal lawsuit and do not undergo standard merit-based review. Including them would artificially lower denial rates.

APS requests ARE included in volume/count charts (Charts 01, 01b) where they are visually distinguished with hatching and a legend note explaining the exclusion.

### Borough Normalization

The `borough` field contains inconsistent values including codes ("QK", "MB", "9"), multi-borough entries ("All Boroughs", "S/Q"), and nulls. Records not matching the five standard boroughs (Bronx, Brooklyn, Manhattan, Queens, Staten Island) are labeled "Unknown" in borough-level charts. These account for 29 records in the 2020–2025 window (0.16% of data).

---

## CB5 Identification

All three datasets use geography-based filtering to ensure consistent CB5 boundaries.

### Signal Studies

CB5 is identified by filtering Queens borough records to streets within CB5 geographic boundaries. A pre-filtered file (`data_cb5_signal_studies.csv`) contains 510 records. See `REFERENCE_cb5_boundaries.md` for the boundary filtering rules used to exclude misattributed records north of the LIE.

### Speed Bumps (SRTS)

CB5 is identified by `cb = '405'` (borough code 4 for Queens + district 05) **plus** two additional filters:

1. **Cross-street exclusion filter**: Records with cross streets indicating locations north of the LIE (52nd Avenue, 53rd Avenue, Calamus Avenue, Queens Boulevard, etc.) are excluded. See `REFERENCE_cb5_boundaries.md` for the full exclusion list. Impact: 6 resolved records excluded from 1,988 raw cb=405 resolved records.

2. **Polygon boundary filter**: All records with coordinates are tested against the official CB5 community district polygon (see below). Impact: 23 additional records excluded that had cb=405 labels but coordinates outside the actual district boundary.

**Final count:** 1,959 resolved SRTS records retained.

### Motor Vehicle Crashes

The crash dataset (`h9gi-nx95`) has no community board field. CB5 crashes are identified using **point-in-polygon testing** against the official community district boundary (see Geographic Boundary below).

**Previous approach (replaced):** An SRTS-derived bounding box was used initially, but audit revealed 24% false positives (980 of 4,084 crashes were outside the actual CB5 polygon but inside the bounding rectangle). The polygon filter eliminated all false positives.

### Geographic Boundary

All geographic filtering uses the **official NYC community district polygon** for Queens CD5, sourced from the NYC Department of City Planning via the [nycehs/NYC_geography](https://github.com/nycehs/NYC_geography) GitHub repository (51-point polygon, GeoJSON format). The polygon is cached locally at `data_raw/cb5_boundary.geojson` and auto-downloaded if missing.

Point-in-polygon testing uses the [Shapely](https://shapely.readthedocs.io/) library with prepared geometry for performance. All coordinate-bearing records (crashes, SRTS, geocoded signal studies) are filtered against this polygon to ensure zero data from outside the district boundary.

---

## De-Duplication (Chart 06)

During review, we identified administrative duplicate records in the signal studies data. Specifically:

- **7 records** at Metropolitan Ave & Flushing Ave included **5 records from the same date (2022-09-06)** with sequential internal reference numbers (CQ22-2600B through CQ22-2604B) but sharing a single external reference number (DOT-563803-L0J5). All 5 had empty study data fields (no speed, count, or findings data).

**De-duplication method:** Records sharing the same DOT external reference number (`externalreferencenumber` starting with "DOT-") are collapsed to one record per unique external reference, retaining the most recent `statusdate`. Records with null or non-DOT external references (e.g., "INTERNAL REQUEST") are kept as-is.

**Impact:** 7 records collapsed across the full CB5 dataset (445 DOT-referenced records → 438 unique). This affected Chart 06 (Most Denied Intersections) where Metropolitan Ave & Flushing Ave dropped from 7 apparent denials to 3 genuine denials.

This de-duplication is applied only to Chart 06 (intersection-level counting), not to aggregate charts where the impact is negligible (<1.6% of records).

---

## Speed Bump Denial Reason Classification

The `denialreason` field in SRTS data is free-text. We categorize reasons as follows:

| Category | Matching Logic |
|----------|---------------|
| Speed < 30 mph | Contains "speed" AND ("below" OR "radar") |
| Driveways | Contains "driveway" or "curb cut" |
| Street Too Short | Contains "street too short" or "block" |
| Stop Controls | Contains "stop control" |
| Bus Route | Contains "bus" |
| Near Speed Camera | Contains "camera" |
| Not Specified | Null/empty denial reason |
| Other | All remaining reasons |

**Key finding:** "Speed < 30 mph" accounts for 84% of CB5 speed bump denials in 2020–2025, up from 37% across the full history. This single technical criterion — radar-measured 85th-percentile speeds below 30 mph — has become the overwhelmingly dominant reason for denial.

---

## Chart-by-Chart Decisions

### Chart 01: Request Volume by Borough
- **Time range:** 2020–2025 (matched to CB5 data availability)
- **Left panel:** Citywide signal study requests by borough (n=17,824)
- **Right panel:** CB5 request types with APS hatched and annotated
- **Decision:** "Various" borough label renamed to "Unknown" (incomplete records with no street data); minor request types aggregated as "Other" on right panel
- **Z-series (01z):** Full history 1996–2025

### Chart 01b: Request Trends by Year
- **Time range:** 2020–2025
- **Left panel:** Citywide and Queens line trends
- **Right panel:** CB5 stacked bar by request type (replaced original 5-line spaghetti chart)
- **Color palette:** Tableau-inspired qualitative palette (#4E79A7, #F28E2B, #59A14F, #E15759, #BAB0AC) for stacked segments — chosen for contrast between adjacent segments
- **Decision:** APS shown with hatching consistent with Chart 01; "Other" aggregates minor types (Consultant/Capital, Right Turn Arrow, Speed Study, Signal Removal)
- **Z-series (01bz):** Full history 1996–2025 (Citywide + Queens lines only)

### Chart 02: Denial Rates by Borough
- **Time range:** 2020–2025 (updated from original 1996–2025)
- **Scope:** Five boroughs, excl. APS, resolved records only (n=15,724)
- **Decision:** Queens highlighted with dark navy (#1B3F5E) instead of pure black for softer emphasis; horizontal gridlines removed (categorical axis); citywide average reference line retained
- **Key finding:** Manhattan (94.8%) leads in recent years, displacing Staten Island from the full-history #1 position. Queens (88.7%) sits at the citywide average (88.4%).

### Chart 03: Year-over-Year Trends
- **Time range:** 2020–2025 (all four panels aligned)
- **Structure:** 2×2 grid — Signal Studies (top) and Speed Bumps (bottom), Volume (left) and Denial Rate (right)
- **Decision:** Narrowed bottom row from 2005–2025 to 2020–2025 for consistency; vertical gridlines removed on bar panels; n= added to subtitles
- **Z-series (03z):** Full history — signal studies from 2020 (CB5 data start), speed bumps from 1999

### Chart 04: Denial Rates by Request Type
- **Time range:** 2020–2025 (updated from original all-time)
- **Scope:** CB5 vs Citywide, five request types (Traffic Signal, All-Way Stop, Left Turn Arrow/Signal, Leading Pedestrian Interval, Speed Bumps)
- **Decision:** Filtering to 2020–2025 changed the story significantly — Left Turn Arrow and Leading Pedestrian Interval became 100%/100% for both CB5 and citywide (universally denied in recent years). All-Way Stop reversed: CB5 (85%) now higher than citywide (78%).
- **Data note:** CB5 signal study data inherently covers 2020–2025 only; the fix was applying the same filter to the citywide baseline (previously using 1996–2025, creating an apples-to-oranges comparison).

### Chart 05: Speed Bump (SRTS) Analysis
- **Time range:** 2020–2025
- **Structure:** 3-panel — Queens CB comparison (left), CB5 denial reasons (middle), denial reason trend by year (right)
- **Decision:** Right panel replaced redundant denial rate trend (already in Chart 03) with stacked bar showing "Speed < 30 mph" vs "All Other Reasons" by year — this uniquely reveals the growing dominance of a single denial criterion.
- **Key finding:** "Speed < 30 mph" grew from 70% of CB5 denials in 2020 to 94% in 2025.
- **Z-series (05z):** Full history with x-axis ticks every 5 years for readability; minimum-n thresholds applied (CB5 n≥5, citywide n≥10) to exclude unreliable early-year rates.

### Chart 06: Most Denied Intersections
- **Time range:** 2020–2025 (inherent — CB5 data only exists from 2020)
- **De-duplication:** Applied (see De-Duplication section above); source note documents this
- **Decision:** Trimmed from 15 to 10 intersections (bottom entries had only 2 denials — noisy); location names title-cased for readability
- **Key finding:** Woodhaven Blvd & Eliot Ave and Metropolitan Ave & Forest Ave lead with 5 genuine separate denials each.

### Chart 07: Most Denied Streets for Speed Bumps
- **Time range:** 2020–2025 (filtered from full SRTS history)
- **Scope:** CB5 speed bump denials (n=430 denials), top 10 streets
- **Decision:** Title-cased street names; each entry counts individual street segments denied (not intersections)
- **Key finding:** Otto Road, Myrtle Avenue, and Woodward Avenue tied at 14 denials each. Much more even distribution in 2020–2025 compared to all-time data.

### Chart 08: Crash Hotspots
- **Time range:** 2020–2025 (explicit cap to exclude 2026 data)
- **CB5 identification:** Official community district polygon boundary (point-in-polygon test). This replaced an earlier bounding box approach that included 24% false positives.
- **Street name normalization:** NYC crash data contains inconsistent street naming (e.g., "METROPOLITAN AVENUE", "METROPOLITAN AVE", "METROPOLITAN AVENUE             " with trailing spaces). A normalization function strips whitespace and expands abbreviations (AVE→AVENUE, BLVD→BOULEVARD, etc.) before grouping.
- **Two-panel structure:** Left sorted by crashes, right independently sorted by injuries — ranking differences reveal streets where crash severity differs from frequency

### Charts 10, 11: Removed
- **Chart 10 (Combined Annual Summary):** Removed — fully redundant with Chart 03 (identical data, same time range, same view)
- **Chart 11 (Denial Reasons Detailed):** Removed — left panel was low-information (only 2 denial status categories); right panel redundant with Chart 05/05z (speed bump denial reason trends)

### Chart 12: Request Type Mix
- **Time range:** 2020–2025 (corrected from original all-time)
- **Scope:** CB5 (n=875) vs Citywide (n=30,920), resolved records excl. APS
- **Decision:** Replaced buggy pie chart (which hid Speed Bumps in "Other" due to a sorting/head() issue) with a single focused grouped bar chart comparing percentage distributions
- **Key finding:** With the proper 2020–2025 filter, CB5 and citywide have nearly identical speed bump shares (49.8% vs 49.6%). The original all-time comparison (82% vs 51%) was misleading. The actual CB5 distinctiveness is modest: slightly fewer Traffic Signal requests (20.8% vs 28.3%) and slightly more All-Way Stop (18.7% vs 15.5%) and LPI (6.4% vs 2.8%) requests.

---

## Gridline Conventions

- **Horizontal bar charts:** Vertical gridlines only (value axis); horizontal gridlines removed (categorical axis adds no information)
- **Vertical bar charts (grouped/stacked):** Horizontal gridlines only; vertical gridlines removed for discrete categories
- **Line charts:** Both gridlines retained (both axes are continuous/meaningful)
- **Global settings:** Grid alpha 0.3, dashed style, applied via rcParams

## Color Conventions

| Use Case | Color | Hex |
|----------|-------|-----|
| Primary / CB5 data | Navy blue | `#2C5F8B` |
| Citywide comparison | Dark goldenrod | `#B8860B` |
| CB5 highlight (bar charts) | Dark navy | `#1B3F5E` |
| Denied | Dark red | `#8B0000` |
| Approved | Dark green | `#006400` |
| Average reference line | Dark red dashed | `#8B0000` |
| APS (court-mandated) | Gray with `///` hatching | `#666666` |
| Crash data (count) | Muted red | `#A12020` |
| Crash data (injuries) | Lighter muted red | `#C04040` |

### Stacked/Categorical Palette (Chart 01b)

Tableau-inspired for maximum segment contrast:

| Segment | Color | Hex |
|---------|-------|-----|
| Traffic Signal | Steel blue | `#4E79A7` |
| All-Way Stop | Warm orange | `#F28E2B` |
| Leading Ped Interval | Green | `#59A14F` |
| Left Turn Arrow | Coral | `#E15759` |
| APS | Warm gray (hatched) | `#BAB0AC` |
| Other | Light gray | `#D4D4D4` |

---

## File Naming Conventions

| Pattern | Meaning |
|---------|---------|
| `chart_NN_description.png` | Focused chart (2020–2025) |
| `chart_NNz_description.png` | Z-series: full history version |
| `table_NN_description.csv` | Underlying data table for chart NN |

---

---

## Part 2: Crash-Denial Correlation Analysis

### Core Question

Does crash data correlate with the denial of DOT safety requests in CB5?

### Geocoding Signal Study Intersections

Signal study records have street names but no coordinates. A three-tier local geocoding approach was used (no external API):

| Tier | Method | Coverage | Records |
|------|--------|----------|---------|
| 1 | **Crash data matching** — Match `(mainstreet, crossstreet1)` to Queens crash `(on_street_name, off_street_name)` using median lat/lon of all crashes at that intersection | 60% | 266 |
| 2 | **SRTS data matching** — Match to SRTS `(onstreet, fromstreet/tostreet)` coordinates | 27% | 120 |
| 3 | **Street-line intersection** — Fit linear regression lines through all known lat/lon points for each street, then find the geometric intersection point | 7% | 33 |
| — | **Unmatched** | 5% | 23 |
| **Total** | | **95%** | **419/442** |

**Street name normalization:** All street names are uppercased, whitespace-collapsed, and common abbreviations expanded (AVE→AVENUE, BLVD→BOULEVARD, etc.) before matching. Both orderings of street pairs are tried.

**Validation:** Tier 3 (street-line) results are validated against CB5 geographic bounds. Points falling outside the bounding box are rejected.

**Caching:** Results are cached to `output/geocode_cache_signal_studies.csv`. Delete this file to force re-geocoding.

### Proximity Analysis

For each safety request location (signal studies and SRTS), crashes within **150 meters** are counted. This radius is the standard for NYC Vision Zero intersection analysis (~1.5 blocks).

**Metrics computed per location:**
- `crashes_150m` — total injury crashes within 150m
- `injuries_150m` — total persons injured
- `ped_injuries_150m` — pedestrian injuries specifically
- `fatalities_150m` — fatalities

**Distance calculation:** Haversine formula (great-circle distance).

**Crash data note:** The crash dataset only contains injury crashes (`number_of_persons_injured > 0` from the fetch query). This means zero-injury crashes are not included, but this actually strengthens the safety argument — we're specifically measuring "are people getting hurt near denied requests?"

### Statistical Testing

Denied vs approved location crash distributions are compared using the **Mann-Whitney U test** (non-parametric, does not assume normal distribution). Implementation is manual (no scipy dependency) using a normal approximation for p-values.

### Key Findings

| Dataset | Denied Median Crashes (150m) | Approved Median Crashes (150m) | p-value |
|---------|------------------------------|-------------------------------|---------|
| Signal Studies | 12 | 8 | **0.002** * |
| SRTS (Speed Bumps) | 8 | 8 | 0.661 |

**Signal studies:** Statistically significant (p=0.002). Denied signal/stop sign request locations have 50% more nearby injury crashes than approved locations. Denied locations also have higher median injuries (16 vs 9) and higher mean crashes (17.8 vs 11.0).

**SRTS:** Not statistically significant (p=0.66). Speed bump denials are driven primarily by technical speed criteria (85th-percentile radar speed < 30 mph), not crash history. This is consistent with the finding in Part 1 that "Speed < 30 mph" accounts for 84% of CB5 speed bump denials.

### Map Outputs

| Map | File | Description |
|-----|------|-------------|
| Map 01 | `map_01_crash_denial_overlay.html` | Primary analysis map: crash heatmap + all denied/approved locations with layer toggles |
| Map 02 | `map_02_top_denied_with_crashes.html` | Top 15 denied locations by nearby crash count with 150m analysis circles |
| Map 03 | `map_03_srts_crashes.html` | SRTS-only map (cleanest dataset, 100% coordinate coverage) |

All maps use CartoDB positron tiles (clean gray basemap for print/article use) with interactive popups showing location details and crash statistics.

### Chart Outputs

**Chart 09:** Crash Proximity Comparison — grouped bar chart showing median crashes/injuries/pedestrian injuries near denied vs approved locations, for both signal studies and SRTS. Includes Mann-Whitney p-values.

**Chart 09b:** Top 15 Denied Locations by Nearby Crash Count — horizontal bar chart ranking the most crash-surrounded denied locations across both datasets.

---

## Reproducibility

All charts are generated by running:

```bash
source .venv/bin/activate
python generate_charts.py
```

Maps and correlation analysis are generated by running:

```bash
python generate_maps.py
```

Raw data can be refreshed by running:

```bash
python scripts_fetch_data.py
```

Note: Re-fetching data may produce different results as the NYC Open Data API reflects ongoing updates to city records.
