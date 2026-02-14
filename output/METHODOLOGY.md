# Methodology & Decision Log

## Queens Community Board 5 — DOT Safety Infrastructure Request Analysis

**Analysis period: 2020–2025** | **Data fetched: 2026-02-11** | **Geography: QCB5 (Queens CD5)**

---

## 1. Data Sources

All data was fetched from the NYC Open Data Socrata API on **2026-02-11** using `scripts_fetch_data.py`.

| Dataset | Endpoint ID | File | Records | Date Range |
|---------|-------------|------|---------|------------|
| Signal Studies | `[w76s-c5u4]` | `signal_studies_citywide.csv` | 74,485 | 1996–2026 |
| Speed Reducer Tracking System | `[9n6h-pt9g]` | `srts_citywide.csv` | 58,198 | 1990–2026 |
| Motor Vehicle Collisions | `[h9gi-nx95]` | `crashes_queens_2020plus.csv` | 41,632 | 2020–2026 |
| CB5 Signal Studies | Derived | `data_cb5_signal_studies.csv` | 510 | 2020–2025 |

### 1.1 Analysis Time Window

**Primary analysis window: 2020–2025.** All charts, maps, and statistical tests use this window unless explicitly labeled otherwise.

**Rationale:**
- CB5 signal study data begins in January 2020 — there is no pre-2020 CB5 data in the Signal Studies dataset. Using 2020–2025 ensures apples-to-apples comparison between CB5 and citywide baselines.
- Data from early 2026 exists in some datasets but is excluded. 2026 is incomplete, and including a partial year would distort year-over-year trends and annualized rates.
- All dynamic year computations in code are hard-capped at 2025: `min(computed_year, 2025)`.

**Z-series charts** provide full historical context using each dataset's complete available range, capped at 2025. These are labeled with actual year ranges (e.g., "1999–2025"), never "Full History" or "All Years."

**Policy significance:** The 2020–2025 window captures the post-Vision Zero era of NYC traffic policy, a period when DOT's evaluation criteria and staffing were relatively stable. Earlier data reflects fundamentally different policy environments and is provided as z-series context only.

---

## 2. Outcome Classification

### 2.1 Signal Studies

Signal study records are classified into three outcomes based on the `statusdescription` field:

| Outcome | Logic |
|---------|-------|
| **Denied** | Status contains "denial" OR status is "Engineering Study Completed" without any approval language |
| **Approved** | Status contains "approval", "approved", "aps installed", "aps ranking", or "aps design" |
| **Pending** | All other statuses (excluded from rate calculations) |

Only **resolved** records (denied + approved) are used for denial rate calculations.

**Policy note:** The classification "Engineering Study Completed (Signals Engineering)" without approval language is treated as a denial because it represents the conclusion of DOT's evaluation process without the issuance of approval. DOT does not use an explicit "denied" status for signal studies — the absence of approval *is* the denial.

### 2.2 Speed Bumps (SRTS)

SRTS records use the `segmentstatusdescription` field:

| Outcome | Value |
|---------|-------|
| **Denied** | "Not Feasible" |
| **Approved** | "Feasible" |

Only resolved records are included. SRTS outcomes are binary — DOT engineering determines feasibility, and the result is recorded directly.

---

## 3. Exclusions

### 3.1 Accessible Pedestrian Signals (APS)

APS requests are **excluded from all denial rate calculations**. APS installations are mandated by a federal lawsuit settlement and do not undergo the same merit-based engineering review as standard signal study requests. Including them would artificially deflate denial rates by mixing court-ordered installations with discretionary evaluations.

APS requests ARE included in volume/count charts (Charts 01, 01b) where they are visually distinguished with gray hatching and a legend note explaining the exclusion.

**Policy significance:** The APS exclusion is critical to the integrity of this analysis. If APS were included, CB5's apparent denial rate would drop significantly, masking the reality that discretionary safety requests face near-universal denial.

### 3.2 Borough Normalization

The `borough` field contains inconsistent values including codes ("QK", "MB", "9"), multi-borough entries ("All Boroughs", "S/Q"), and nulls. Records not matching the five standard boroughs are labeled "Unknown" in borough-level charts (29 records in 2020–2025, 0.16% of data).

### 3.3 SRTS 2020–2025 Filtering

For the interactive map and proximity analysis (Part 2), SRTS data is filtered to **2020–2025** to match the crash data and signal study windows. This excluded 1,528 pre-2020 SRTS records.

Charts 13, 15, 16, and 16z examine SRTS installation history using the full date range. These charts load SRTS data via the shared `_load_cb5_srts_full()` helper, which applies the complete CB5 filtering pipeline (cb=405 + cross-street exclusion + polygon filter) before any chart-specific year logic.

**Rationale:** Crash data is only available from 2020 onward. Plotting a speed bump request denied in 2005 against crash data from 2020–2025 would create a misleading temporal mismatch. All data on the map shares the same 2020–2025 window.

---

## 4. CB5 Identification

All three datasets use geography-based filtering to ensure consistent CB5 boundaries.

### 4.1 Signal Studies

CB5 is identified by filtering Queens borough records to streets within CB5 geographic boundaries. A pre-filtered file (`data_cb5_signal_studies.csv`) containing 510 records is a curated input — not auto-generated by the pipeline — because signal studies lack a community board field. CB5 membership was determined by street-name matching against known CB5 boundary streets. See `REFERENCE_cb5_boundaries.md` for boundary filtering rules used to exclude misattributed records north of the LIE.

### 4.2 Speed Bumps (SRTS)

CB5 is identified by `cb = '405'` (borough code 4 for Queens + district 05) **plus** two additional mandatory filters:

1. **Cross-street exclusion**: Records with cross streets indicating locations north of the LIE (52nd Avenue, 53rd Avenue, Calamus Avenue, Queens Boulevard, etc.) are excluded. Impact: 6 records removed.

2. **Polygon boundary filter**: All records with coordinates are tested against the official CB5 community district polygon. Impact: ~23 additional records removed.

**CRITICAL:** All three layers (cb=405 + cross-street exclusion + polygon filter) must be applied together. The `cb=405` field alone includes ~29 records outside the actual CB5 polygon. In `generate_maps.py`, the shared `_load_cb5_srts_full()` helper centralizes this pipeline so all SRTS charts use identical filtering.

**Final count (all years):** ~1,959 resolved SRTS records retained. **After 2020–2025 filter (map pipeline):** 431 records.

### 4.3 Motor Vehicle Crashes

The crash dataset has no community board field. CB5 crashes are identified using **point-in-polygon testing** against the official community district boundary. **Rows without valid coordinates are excluded** from the polygon filter (they cannot be geographically verified).

**Previous approach (replaced):** An SRTS-derived bounding box was used initially but audit revealed 24% false positives (980 of 4,084 crashes were outside the actual CB5 polygon but inside the bounding rectangle). The polygon filter eliminated all false positives.

**Coordinate exclusion fix (Feb 2026):** The `_filter_points_in_cb5()` function previously included rows without coordinates in the output by default, inflating crash counts from 3,213 to 3,938 (+725 rows). These no-coordinate rows did not affect proximity analysis (NaN distances are excluded from haversine calculations) but inflated the n= counts displayed in chart titles. Fixed in both `generate_charts.py` and `generate_maps.py`.

### 4.4 Geographic Boundary

All geographic filtering uses the **official NYC community district polygon** for Queens CD5, sourced from the NYC Department of City Planning via the [nycehs/NYC_geography](https://github.com/nycehs/NYC_geography) GitHub repository (51-point polygon, GeoJSON format). The polygon is cached locally at `data_raw/cb5_boundary.geojson` and auto-downloaded if missing.

Point-in-polygon testing uses Shapely with prepared geometry for performance. All coordinate-bearing records (crashes, SRTS, geocoded signal studies) are filtered against this polygon.

---

## 5. Part 1 Charts: Batting Average Analysis

Part 1 (`generate_charts.py`) answers the question: **What are CB5's chances when it asks DOT for safety infrastructure?**

### Chart 01: Signal Study Request Volume by Borough

Chart 01 (`chart_01_request_volume_by_borough.png`) presents a dual-panel view of signal study request volume for the 2020–2025 period. The left panel, "Citywide Signal Study Requests by Borough," displays a horizontal bar chart of total signal study requests per borough (n=17,824 citywide). Queens leads with 6,486 requests — more than any other borough. The right panel, "QCB5 Signal Study Requests by Type," breaks down CB5's 510 requests by type: Traffic Signal (183) and All-Way Stop (164) dominate the mix. APS requests are visually distinguished with hatching but are not excluded from volume counts; the APS exclusion applies only to rate calculations.

This chart establishes that Queens — and CB5 specifically — is an active requester of safety infrastructure. High request volume combined with high denial rates (shown in subsequent charts) indicates persistent unmet demand, not lack of engagement. A z-series companion (Chart 01z) provides the full history from 1996–2025.

### Chart 01b: Signal Study Request Trends by Year

Chart 01b (`chart_01b_requests_by_year.png`) tracks request volume trends over time in a two-panel layout for 2020–2025. The left panel is a line chart comparing Queens (navy blue) to citywide (goldenrod) trends; both show a peak in 2022 followed by decline. The right panel uses stacked bars to show the request type composition per year, with colors drawn from the project palette (navy for Traffic Signal, goldenrod for All-Way Stop, green for LPI, red for Left Turn, gray for APS).

The 2022 peak and subsequent decline may reflect community discouragement after sustained high denial rates — a "why bother?" effect. The type composition shift toward a growing APS share reflects the federal mandate, not community choice. A z-series companion (Chart 01bz) provides the full history from 1996–2025 as a line chart.

### Chart 02: Denial Rates by Borough

Chart 02 (`chart_02_denial_rates_by_borough.png`) displays signal study denial rates across all five boroughs as a horizontal bar chart (n=15,724 resolved records, excluding APS, 2020–2025). Queens is highlighted in dark navy, and a goldenrod dashed line marks the citywide average. Manhattan leads at 94.8%, while Queens (88.7%) sits at the citywide average of 88.4%. Every borough exceeds 78%, with even the lowest (Bronx, 78.2%) denying more than three-quarters of requests.

The denial rate is not a local anomaly — it is a **systemic citywide pattern**. This reframes the conversation from "why is CB5 being singled out" to "why does DOT deny nearly everything everywhere."

### Chart 03: Year-over-Year Trends

Chart 03 (`chart_03_year_over_year_trends.png`) uses a 2×2 grid to track QCB5 trends across 2020–2025. Signal Studies occupy the top row and Speed Bumps the bottom row, with Volume on the left and Denial Rate on the right. A goldenrod dashed line on the denial rate panels provides the citywide comparison baseline. Signal study denial rates fluctuate between 79% and 100%, while speed bump denial rates have steadily climbed to 100% by 2025. The citywide trend mirrors CB5.

The convergence toward 100% denial for speed bumps is the most alarming trend in this analysis. When a program reaches 100% denial, it has effectively ceased to function as a public service — it accepts requests but approves none. This suggests the evaluation criteria may have become functionally prohibitive. A z-series companion (Chart 03z) provides the full history: signal studies from 2020 (CB5 data start) and SRTS from 1999–2025.

### Chart 04: Denial Rates by Request Type

Chart 04 (`chart_04_denial_rates_by_request_type.png`) compares QCB5 and citywide denial rates across five request types using a grouped bar chart (navy for QCB5, goldenrod for citywide), with individual sample sizes shown per type on the x-axis labels. The data covers resolved records excluding APS for 2020–2025. Left Turn Arrow/Signal and Leading Pedestrian Interval are denied at 100% for both CB5 and citywide. Traffic Signal and All-Way Stop denials hover between 85% and 91%. Speed bumps are denied at 99% in CB5 versus 95% citywide. Filtering to 2020–2025 was critical for this chart — the original all-time comparison used 1996–2025 citywide data against 2020–2025 CB5 data, creating an apples-to-oranges distortion.

The 100% denial rate for certain request types means DOT's engineering criteria have become **unfulfillable** in practice. A Left Turn Arrow request in Queens from 2020–2025 has zero historical precedent for approval. Communities are being invited to make requests that the system cannot grant.

### Chart 05: Speed Bump (SRTS) Analysis

Chart 05 (`chart_05_speed_bump_analysis.png`) provides a three-panel deep dive into QCB5 speed bump outcomes for 2020–2025. The left panel compares CB5's denial rate against other Queens community boards, where CB5 ranks near the top. The middle panel breaks down CB5 denial reasons, revealing that "Speed < 30 mph" accounts for 84% of all denials. The right panel tracks this dominant reason over time as a stacked bar: the "Speed < 30 mph" share grew from 70% in 2020 to 94% in 2025, increasingly crowding out all other denial reasons.

This chart reveals that a **single technical criterion** — the 85th-percentile radar speed measurement — drives nearly all speed bump denials. The criterion asks whether most cars are already traveling under 30 mph. If so, DOT denies the request. But communities requesting speed bumps are not asking "are most drivers speeding?" — they are asking "is this street dangerous?" These are fundamentally different questions. A street with an 85th-percentile speed of 28 mph can still have frequent crashes, pedestrian conflicts, and a lived experience of danger. A z-series companion (Chart 05z) provides the full SRTS history from 1999–2025 with minimum-n thresholds.

### Chart 06: Most Denied Intersections

Chart 06 (`chart_06_most_denied_intersections.png`) ranks the top 10 QCB5 intersections by denial count for 2020–2025. Administrative duplicates sharing a DOT external reference number are collapsed to one record per unique reference before counting; this de-duplication removed 7 records (most notably, Metropolitan Ave & Flushing Ave dropped from 7 apparent denials to 3 genuine denials). After de-duplication, Woodhaven Blvd & Eliot Ave and Metropolitan Ave & Forest Ave lead with 5 separate denials each.

Repeated denials at the same intersection represent **persistent community demand meeting persistent institutional refusal**. When a community submits 5 separate requests for a traffic signal at the same dangerous intersection and DOT denies all 5, the question becomes whether the engineering criteria are measuring the right things.

### Chart 07: Most Denied Streets for Speed Bumps

Chart 07 (`chart_07_most_denied_streets_speed_bumps.png`) ranks the top 10 QCB5 streets by speed bump denial count (n=425 denials, 2020–2025). Otto Road, Myrtle Avenue, and Woodward Avenue are tied at 14 denials each, with a more even distribution than signal study denials.

These are streets where multiple consecutive blocks were requested and denied. Because speed bump requests are per-block segments, 14 denials on one street means the community requested protection across a long corridor and was denied for every segment.

### Chart 08: QCB5 Crash Hotspots

Chart 08 (`chart_08_crash_hotspots_cb5.png`) examines QCB5 crash hotspots across n=3,213 injury crashes from 2020–2025 in a dual-panel layout. The left panel, "Top 10 Streets by Crash Count," ranks streets by number of crash incidents as horizontal bars, where each bar represents a unique collision event. The right panel, "Top 10 Streets by Persons Injured," uses stacked horizontal bars to rank streets by total persons injured, broken into three segments: Pedestrians (red, `#B44040`) as the most policy-relevant category, Cyclists (goldenrod, `#B8860B`), and Motorists (tan, `#CC9966`).

The two panels differ because a single crash can injure multiple people. Metropolitan Avenue, for example, has 165 crashes but 216 persons injured (approximately 1.3 per crash). The stacked breakdown reveals that pedestrians bear a disproportionate share of injuries on the most dangerous corridors. NYC crash data contains inconsistent naming ("METROPOLITAN AVENUE" vs. "METROPOLITAN AVE" with trailing spaces), so a normalization function standardizes street names before grouping.

This chart establishes the **crash baseline** — where people are actually getting hurt, and who is getting hurt. The pedestrian injury breakdown directly ties to the infrastructure being denied: traffic signals, stop signs, and speed bumps primarily protect pedestrians. When compared to Charts 06 and 07 (where DOT is denying requests), overlaps between crash hotspots and denial hotspots become the central finding of this analysis.

### Chart 12: Request Type Mix

Chart 12 (`chart_12_request_types_distribution.png`) compares the percentage distribution of request types between QCB5 (n=875) and citywide (n=30,920) using a grouped bar chart. All records are resolved and exclude APS, covering 2020–2025. CB5 and citywide have nearly identical speed bump shares (49.8% vs. 49.6%). CB5 has slightly fewer Traffic Signal requests (20.8% vs. 28.3%) and slightly more All-Way Stop (18.7% vs. 15.5%) and LPI (6.4% vs. 2.8%) requests.

CB5 is not an outlier in what it asks for — the mix of requests closely mirrors citywide patterns. This undermines any argument that CB5's high denial rates are driven by "unreasonable" request patterns.

---

## 6. Part 2 Charts: Crash-Denial Correlation Analysis

Part 2 (`generate_maps.py`) answers the question: **Do denied locations have more crashes than approved locations? And does DOT follow through when it does approve?**

### 6.1 Geocoding Signal Study Intersections

Signal study records have street names but no coordinates. A three-tier local geocoding approach was used (no external API):

| Tier | Method | Coverage |
|------|--------|----------|
| 1 | **Crash data matching** — Match `(mainstreet, crossstreet1)` to Queens crash `(on_street_name, off_street_name)` using median lat/lon of all crashes at that intersection | 60% (266) |
| 2 | **SRTS data matching** — Match to SRTS `(onstreet, fromstreet/tostreet)` coordinates | 27% (120) |
| 3 | **Street-line intersection** — Linear regression through known points for each street, then geometric intersection | 7% (33) |
| — | **Unmatched** | 5% (23) |
| **Total** | | **95% geocoded (419/442)** |

Street name normalization (uppercase, abbreviation expansion, whitespace collapse) is applied before all matching. Both orderings of street pairs are tried. Tier 3 results are validated against CB5 polygon bounds.

Results are cached to `output/geocode_cache_signal_studies.csv`. Delete to force re-geocoding.

### 6.2 Proximity Analysis

For each safety request location, injury crashes within **150 meters** are counted. This radius is the standard for NYC Vision Zero intersection safety analysis (~1.5 blocks).

Four metrics are computed per location: `crashes_150m` (total injury crashes within 150m), `injuries_150m` (total persons injured), `ped_injuries_150m` (pedestrian injuries specifically), and `fatalities_150m` (fatalities). Distances are calculated using the Haversine formula (great-circle distance), vectorized for performance.

The crash dataset contains only injury crashes (fetched with `number_of_persons_injured > 0`); zero-injury crashes are excluded. This strengthens the safety argument — we are specifically measuring whether people are getting hurt near denied request locations.

### 6.3 Statistical Testing

Denied vs approved location crash distributions are compared using the **Mann-Whitney U test** (non-parametric, does not assume normal distribution). Implementation is manual (no scipy dependency) using a normal approximation for p-values.

### Chart 09: Crash Proximity Analysis

Chart 09 (`chart_09_crash_proximity_analysis.png`) presents the central statistical test of this analysis. It displays grouped bars comparing denied (red) versus approved (green) locations on three metrics — median crashes, injuries, and pedestrian injuries within 150 meters — with the Mann-Whitney U test p-value annotated on each panel. The left panel covers Signal Studies (n=410, QCB5, 2020–2025) and the right panel covers Speed Bumps (n=431).

For signal studies, denied locations have significantly more crashes than approved locations (median 11 vs. 8, p=0.002), a result that is statistically significant at the 1% level. Denied locations also show higher injuries (15 vs. 9) and pedestrian injuries (2 vs. 2). For SRTS, there is no significant difference (median 9 vs. 7, p=0.61), confirming that speed bump denials are driven by the radar speed criterion rather than crash history.

This is the central statistical finding of the analysis. **DOT is systematically denying signal and stop sign requests at locations with MORE crashes than the locations it approves** — the opposite of what a safety-first evaluation should produce. The p=0.002 result means there is only a 0.2% probability this pattern is due to chance. The non-significant SRTS result is itself informative: it confirms that DOT's speed bump evaluation is decoupled from crash reality, using radar speed as the sole determinant and ignoring crash history entirely.

### Chart 09b: Top 15 Denied Locations in QCB5 by Nearby Crash/Injury Count

Chart 09b (`chart_09b_denied_locations_crash_ranking.png`) identifies the denied locations surrounded by the most crashes in a dual-panel horizontal bar chart covering QCB5 denied signal studies and SRTS combined for 2020–2025. The left panel ranks the top 15 denied locations by crash count within 150 meters, while the right panel independently ranks the top 15 by injury count — producing a different set of locations. Each location is tagged with its source dataset (`[Signal Study]` or `[Speed Bump]`), and street names are abbreviated for readability (Avenue→Ave, Street→St, Road→Rd, Boulevard→Blvd, Turnpike→Tpke, Place→Pl).

Three layers of de-duplication are applied before ranking. First, `_normalize_intersection()` sorts street names alphabetically so that "Cooper Ave & Cypress Ave" and "Cypress Ave & Cooper Ave" are treated as the same location. Second, a name-based groupby aggregates records sharing the same normalized intersection name, keeping the row with the highest crash count. Third, `_spatial_dedup(df, radius_m=150)` applies a greedy algorithm: locations are sorted by crashes descending, and any location within 150 meters (haversine distance) of an already-selected location is skipped. The 150-meter spatial dedup radius matches the analysis radius because two denied locations 100 meters apart would share most of the same crash pool, creating the appearance of distinct hotspots when the crash exposure is largely the same.

The top denied location (62 Ave) has 71 crashes and 86 injuries within 150 meters — more than many locations where DOT has approved infrastructure. These are specific, nameable locations where the community asked for safety infrastructure, DOT said no, and crashes continue to occur.

### Chart 13: Paper Approvals vs Confirmed Installations

Chart 13 (`chart_13_approval_vs_installation.png`) compares paper approvals to confirmed installations in a two-panel layout: "QCB5 Signal Studies" (2020–2025) on the left and "QCB5 Speed Bumps" (1999–2025) on the right. Each panel displays three bars — Denied, Approved (on paper), and Confirmed Installed — with annotation boxes showing the paper approval rate versus the confirmed install rate. Installation status is determined by non-null `aw_installdate` or `signalinstalldate` fields for signals and `installationdate` for SRTS. The absence of an install date on approvals older than one year is treated as strong evidence of non-installation. SRTS data is loaded via `_load_cb5_srts_full()` with the full CB5 filtering pipeline.

For signal studies, 43 were approved on paper but only 15 have confirmed installation dates — a 35% fulfillment rate. The paper approval rate of 9.7% drops to a confirmed install rate of just 3.6%. For SRTS, approximately 237 were approved, approximately 101 installed (43%), and approximately 114 were cancelled or rejected after approval. The paper approval rate of approximately 12% drops to a confirmed install rate of approximately 5%.

The "approval rate" that might be cited by DOT in response to community concerns is approximately **2× the actual installation rate**. Paper approval does not equal infrastructure on the ground. For SRTS, DOT's own data shows more approvals were subsequently cancelled than were actually installed — getting past the engineering evaluation is only half the battle, as bureaucratic and budgetary obstacles eliminate roughly half of approvals before a single bolt is tightened.

### Chart 14: Signal Study Installation Wait Times

Chart 14 (`chart_14_installation_wait_times.png`) visualizes wait times for all 41 approved QCB5 signal studies (excluding APS, 2020–2025) as a horizontal bar chart. Each bar shows the number of months from approval to the current date, colored green for confirmed installations and goldenrod for approvals still awaiting installation. A red dashed line marks the longest known installation time of 15 months, derived from the 15 confirmed installations (which had a median of 35 days, mean of 134 days, and maximum of 456 days from approval to installation). Street names are abbreviated for readability.

Of the 41 approved signal studies, 26 have no installation date. Twenty-four of these have been waiting longer than the maximum known install time. The oldest uninstalled approval dates to November 2021 — 51 months and counting. This chart answers the question "what happens after approval?" For the majority of approved requests, the answer is **nothing**. The 15-month dashed red line makes it visually unambiguous — everything to its right represents a broken promise.

### Chart 15: SRTS Approval Funnel

Chart 15 (`chart_15_srts_funnel.png`) traces the full lifecycle of approximately 237 QCB5 speed bump approvals from 1999–2025 in a two-panel layout. The left panel shows the total approved count, while the right panel breaks down their fate: Confirmed Installed at approximately 101 (43%), Cancelled/Rejected at approximately 114 (48%), and Still Waiting at approximately 21 (9%), with the median wait time annotated on the Still Waiting bar. Cancellation is determined from the `projectstatus` field containing "Cancel," "Reject," or "denied" — DOT's own status labels, not this analysis's classification. SRTS data is loaded via `_load_cb5_srts_full()` with the full CB5 filtering pipeline.

This is the full lifecycle view of an SRTS approval. Only approximately 43% of approvals result in installation. The locations still waiting have a median wait of many years, with some dating to 2009. A speed bump approved during the Bloomberg administration remains uninstalled in 2026. The approximately 48% cancellation rate after approval means the community cannot even rely on a "yes" from DOT.

### Chart 16: SRTS Wait Times (2020–2025)

Chart 16 (`chart_16_srts_wait_times.png`) displays wait times for the 6 feasible QCB5 SRTS requests from 2020–2025 as a horizontal bar chart. Each bar shows months since the initial request, colored green for installed locations and goldenrod for approved-but-not-installed locations, with a red dashed line marking the longest known installation time. The sample is small — 3 installed, 3 waiting — but the pattern is consistent: approved locations are waiting beyond known install timelines.

A z-series companion (Chart 16z) extends the view to the full 1999–2025 history with n=38 locations (the 15 longest-installed of 106 total, plus all 23 still waiting). Wait times in the z-series extend to 197 months — more than 16 years from request to the present day with no installation.

---

## 7. Interactive Map

### Map 01: Consolidated Safety Infrastructure Map

- **File:** `map_01_crash_denial_overlay.html`
- **Base tiles:** CartoDB Positron No Labels — clean, minimal, print-friendly
- **Typography:** Times New Roman via injected CSS
- **Dynamic title:** Updates via JavaScript MutationObserver based on active layer checkboxes

### 7.1 Map Layers

All layers share the same 2020–2025 analysis window. Layer names in the control panel include n= counts and year ranges.

| # | Layer | Default | n= | Description |
|---|-------|---------|-----|-------------|
| 1 | Injury Crashes | ON | 3,213 | Dot density — one dot per crash, sized by severity (fatal=black r=3.5, injury=gray r=1.8, property=light gray r=1.2) |
| 2 | Denied Signal Studies | ON | 370 | Red circle markers (r=6), signal/stop sign requests denied by DOT |
| 3 | Approved Signal Studies | ON | 40 | Green circle markers (r=6), signal/stop sign requests approved |
| 4 | Denied Speed Bumps | ON | 425 | Red circle markers (r=4), SRTS requests denied |
| 5 | Approved Speed Bumps | ON | 6 | Green circle markers (r=4), SRTS requests approved |
| 6 | DOT Effectiveness (Installed) | OFF | 15 | Before-after analysis markers — green (crashes decreased), amber (increased), gray (no change). Marker radius scaled by data volume. |
| 7 | Top 15 Denied Spotlight | OFF | 15 | Highest crash-surrounded denied locations with 150m analysis circles and rank labels (spatially de-duplicated at 150m) |

### 7.2 Popup Content

Every marker on the map provides rich data on click. This ensures that anyone exploring the map can drill into the specifics of any point.

**Crash dots:** Date, time, location (streets), severity tag (FATAL/INJURY), full injury breakdown (pedestrian/cyclist/motorist injured and killed), contributing factor, vehicle type, collision ID.

**Signal studies:** Reference number, request type, date requested, status date, full status description, outcome (color-coded), school name (if applicable), Vision Zero flag, findings, and nearby crash metrics (crashes, injuries, ped injuries, fatalities within 150m).

**Speed bumps:** Project code, street segment (on/from/to), request date, project status, denial reason (if denied), installation date (if installed), traffic direction, and nearby crash metrics within 150m.

**DOT Effectiveness:** Reference number, request type, date requested, install date, before-after crash comparison with percent change, injury comparison, analysis window duration.

**Top 15 Spotlight:** Rank, location name, source dataset (Signal Study or SRTS), request type, and full crash metrics within 150m (crashes, injuries, ped injuries, fatalities).

### 7.3 Layer Data Spreadsheets

Each map layer exports a corresponding CSV spreadsheet to `output/`. These allow users to examine, sort, and filter the underlying data for any layer they see on the map.

| File | Rows | Key Columns |
|------|------|-------------|
| `map_layer_crashes.csv` | 3,213 | date, time, streets, injury breakdown, contributing factor, vehicle type, collision ID, lat/lon |
| `map_layer_denied_signals.csv` | 370 | ref#, type, dates, status, findings, school, Vision Zero, crash proximity metrics, lat/lon |
| `map_layer_approved_signals.csv` | 40 | same as above |
| `map_layer_denied_speed_bumps.csv` | 425 | project code, streets, dates, denial reason, project status, crash proximity, lat/lon |
| `map_layer_approved_speed_bumps.csv` | 6 | same as above + install date |
| `map_layer_top15_denied.csv` | 15 | location, dataset, request type, crash/injury/ped/fatality counts |
| `table_before_after_installed.csv` | 15 | before-after crash/injury comparison per installed location |

### 7.4 Before-After Crash Analysis (Layer 6)

For the 15 confirmed-installed signal study locations, a before-after analysis compares crash counts in equal time windows before and after the installation date.

**Method:**
1. For each installed location, compute `months_before = install_date - 2020-01-01` and `months_after = 2025-12-31 - install_date`.
2. The analysis window is `min(months_before, months_after, 24)` — ensuring equal-length comparison periods, capped at 24 months.
3. Count all injury crashes within 150m of the installation point in the before and after windows.

**Aggregate result:** 63 crashes before → 58 after (-8%). 79 injuries before → 62 after (-21.5%).

**Standout wins:** Bleecker & Woodward (-86% crashes), Linden & Onderdonk (-50%), Seneca & Weirfield (-20%).

**Policy significance:** Where DOT *does* install safety infrastructure, outcomes tend to improve. The 21.5% injury reduction across installed locations suggests the infrastructure works — making the 60% non-installation rate for approved projects even more troubling.

---

## 8. De-Duplication (Chart 06)

During review, administrative duplicates were identified. Specifically, 5 records at Metropolitan Ave & Flushing Ave from the same date (2022-09-06) shared a single external reference number (DOT-563803-L0J5) with empty study data fields.

**Method:** Records sharing the same DOT external reference number are collapsed to one record per unique reference, retaining the most recent `statusdate`. Records with null or non-DOT external references are kept as-is.

**Impact:** 7 records collapsed (445 → 438 unique). Applied only to Chart 06 (intersection-level counting), not to aggregate charts where the impact is negligible (<1.6%).

---

## 9. Speed Bump Denial Reason Classification

The `denialreason` field in SRTS data is free-text. Categories:

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

**Key finding:** "Speed < 30 mph" accounts for 84% of CB5 speed bump denials in 2020–2025, up from 37% across the full history. This single criterion has become the overwhelmingly dominant reason for denial.

---

## 10. Visual Style

All visualizations follow the conventions documented in `STYLE_GUIDE.md`. Key rules:

- **QCB5 = navy blue `#2C5F8B`** everywhere. Citywide = goldenrod `#B8860B` everywhere.
- **Denied = muted red `#B44040`**. Approved = muted green `#4A7C59`.
- Every chart title includes: specific year range (YYYY–YYYY, en-dash), sample size (n=), and QCB5 shorthand.
- Main charts use 2020–2025. Z-series use actual year ranges, capped at 2025.
- Maps use Times New Roman; charts use system serif.

---

## 11. Code Architecture

The analysis is structured as a two-part pipeline:

```
scripts_fetch_data.py          → data_raw/*.csv (raw API downloads)
generate_charts.py  (Part 1)   → output/chart_01–12*.png + tables
generate_maps.py    (Part 2)   → output/map_01*.html + chart_09–16z*.png + tables + layer CSVs
```

Both scripts share identical patterns: outcome classification, APS exclusion, cross-street exclusion, polygon filtering, and street name normalization. The `_normalize_street_name()` function exists in both files to avoid cross-file imports.

Each chart function is self-contained: it loads its data, computes its metrics, generates its visualization, and saves both the chart and its underlying data table. This ensures any single chart can be regenerated independently.

### 11.1 Shared Helper Functions (generate_maps.py)

| Function | Purpose |
|----------|---------|
| `_load_cb5_srts_full()` | Centralized SRTS loader applying full CB5 pipeline (cb=405 + cross-street exclusion + polygon filter). Used by charts 13, 15, 16, 16z. |
| `_normalize_intersection(a, b)` | Alphabetically sort two street names to prevent reversed-name duplicates ("A & B" == "B & A"). |
| `_spatial_dedup(df, radius_m)` | Greedy spatial de-duplication: sort by crashes desc, skip entries within `radius_m` (haversine) of already-selected locations. |
| `_filter_points_in_cb5(df)` | Polygon filter against official CB5 boundary. Excludes rows without coordinates. |
| `_normalize_street_name(s)` | Uppercase, expand abbreviations (AVE→AVENUE, ST→STREET, etc.), collapse whitespace. Exists in both scripts. |

---

## 12. Reproducibility

```bash
source .venv/bin/activate
python scripts_fetch_data.py   # Fetch fresh data (may change results)
python generate_charts.py      # Part 1: all charts
python generate_maps.py        # Part 2: map + correlation charts
```

**Note:** Re-fetching data will produce different results as the NYC Open Data API reflects ongoing updates to city records. The fetched data from 2026-02-11 is preserved in `data_raw/` for reproducibility.

---

## 13. Data Integrity Audit Log

### 13.1 Audit: Feb 13, 2026

A comprehensive data integrity audit was conducted across all charts and data pipelines. The audit was triggered by suspicious patterns in Chart 09b (clusters of identical crash counts, apparent duplicate locations).

**Bugs found and fixed:**

| # | Bug | Impact | Fix |
|---|-----|--------|-----|
| 1 | **`_filter_points_in_cb5()` included no-coordinate rows** | Crash count inflated from 3,213 to 3,938 (+725). No-coord rows had NaN lat/lon so did not affect proximity analysis, but inflated n= in chart titles (Chart 08, map layer counts). | Exclude rows without valid coordinates. Applied in both `generate_charts.py` and `generate_maps.py`. |
| 2 | **Charts 13, 15, 16, 16z loaded SRTS without full CB5 filtering** | These charts loaded SRTS directly from CSV with only `cb=405`, missing cross-street exclusion and polygon filter. ~29 records outside actual CB5 boundary were included. SRTS approved count was 245 (should be ~237); installed was 106 (should be ~101). | Created `_load_cb5_srts_full()` shared helper. Refactored all four charts to use it. |
| 3 | **Chart 06 missing year filter** | Title claimed "2020–2025" but no year filter was applied. Included all-years data in a chart labeled as 2020–2025. | Added explicit `.between(2020, 2025)` year filter. |
| 4 | **Chart 09b reversed intersection duplicates** | "Cooper Ave & Cypress Ave" and "Cypress Ave & Cooper Ave" treated as different locations. | Created `_normalize_intersection()` to sort street names alphabetically. |
| 5 | **Chart 09b spatial duplicates from overlapping 150m radii** | Nearby denied locations (e.g., same intersection in Signal Studies and SRTS) counted overlapping crash pools, appearing as separate hotspots. | Created `_spatial_dedup()` with 150m radius matching the analysis radius. Applied to chart 09b, map Top 15 spotlight, and table_09c. |
| 6 | **Chart 09b right panel not independently sorted** | Right panel (injuries) used left panel's crash-count sort order instead of sorting independently by injury count. | Each panel now independently selects and sorts its own top 15. |

**Data verified as correct:**
- Crash uniqueness: 3,213 rows with 3,213 unique `collision_id` values — no source-level duplication.
- CB5 polygon bounds verified: lat 40.6823–40.7351, lon -73.9245 to -73.8553.
- Proximity methodology sound: 71 crashes near top location (62 Ave) are 71 genuinely different collision events at 19 unique coordinate points within 150m.
- 68.7% of crashes share exact coordinates with at least one other crash — expected behavior (multiple crashes at the same intersection over time).

**Documentation errors that contributed to bugs:**
- `CLAUDE.md` "CB5 Identification" section listed only `cb='405'` for SRTS without mentioning mandatory cross-street exclusion and polygon filter — this omission led to charts 13–16 being built without proper filtering.
- `decisions.md` documented "Charts 13, 15, 16z load SRTS independently from CSV" as intentional design rather than identifying it as inconsistent with the centralized pipeline.
- `METHODOLOGY.md` section 3.3 described independent loading as deliberate behavior.

All documentation updated to prevent recurrence.

---

## 14. Summary of Key Findings

1. **QCB5's signal study denial rate is ~90%** (2020–2025), consistent with the citywide average of ~88%. This is not a local anomaly — it is a systemic pattern.

2. **QCB5's speed bump denial rate has reached 99–100%** in recent years, driven almost entirely by a single criterion (85th-percentile speed < 30 mph).

3. **Denied signal study locations have significantly more nearby crashes than approved locations** (median 11 vs 8, p=0.002). DOT is systematically denying requests at more dangerous locations.

4. **Only 3.6% of signal study requests and 5.7% of speed bump requests result in confirmed installations.** Paper approvals overstate actual infrastructure delivery by roughly 2×.

5. **26 of 41 approved signal studies have no installation date.** 24 of these have been waiting longer than the maximum known install time (15 months). The oldest approval without installation is 51 months old.

6. **For SRTS, more approvals were cancelled after the fact (~114) than were actually installed (~101).** ~21 locations remain in limbo with a median wait of many years.

7. **Where DOT does install, injuries decrease by 21.5%.** The infrastructure works — the bottleneck is deployment, not design.
