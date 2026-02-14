# QCB5 DOT Safety Analysis — Official Style Guide

This document defines the visual language for all charts, maps, and data visualizations in this project. **All future work must follow these conventions exactly.** When in doubt, reference the hex codes and rules below — do not improvise.

---

## 1. Color Palette

### 1.1 Semantic Colors (Primary)

These colors have fixed meanings. Never swap them or use them for other purposes.

| Role | Hex | Swatch | Usage |
|------|-----|--------|-------|
| **QCB5 / Local** | `#2C5F8B` | Navy blue | QCB5 bars, QCB5 trend lines, primary subject data |
| **Citywide / Comparison** | `#B8860B` | Dark goldenrod | Citywide bars, citywide trend lines, citywide avg reference lines |
| **Denied** | `#B44040` | Muted red | Denied request markers (maps + charts), denial-themed bars |
| **Approved** | `#4A7C59` | Muted green | Approved request markers (maps + charts), approval-themed bars |
| **Crash data** | `#996633` | Warm brown | Crash count bars, crash density |
| **Crash alt (injuries)** | `#CC9966` | Light warm brown | Injury count overlays |

### 1.2 Semantic Colors (Secondary)

| Role | Hex | Usage |
|------|-----|-------|
| **QCB5 highlight** | `#1B3F5E` | Darker navy — used to highlight QCB5/Queens in ranked borough lists |
| **Installed (improved)** | `#2d7d46` | Strong green — before-after markers where crashes decreased |
| **Installed (worse)** | `#cc8400` | Amber — before-after markers where crashes increased |
| **Installed (no change)** | `#777777` | Neutral gray — before-after markers with no change |
| **Neutral / secondary text** | `#666666` | Gray — secondary labels, muted annotations |
| **APS / court-mandated** | `#999999` | Gray with `///` hatch — Accessible Pedestrian Signals (excluded from analysis) |

### 1.3 Denial Shade Gradient

For ranked denial bars (darkest = most denied, lightest = least):

```
'#8B2020', '#B44040', '#C46060', '#D48080', '#DDA0A0', '#E6B8B8', '#EED0D0'
```

### 1.4 Categorical Palette (Stacked Bars)

For multi-category breakdowns (e.g., request type stacked bars). Order matches typical request type frequency:

| Category | Hex | Color |
|----------|-----|-------|
| Traffic Signal | `#2C5F8B` | Navy (matches QCB5 primary) |
| All-Way Stop | `#B8860B` | Goldenrod (matches citywide) |
| Leading Pedestrian Interval | `#4A7C59` | Green (matches approved) |
| Left Turn Arrow/Signal | `#B44040` | Red (matches denied) |
| APS | `#999999` | Gray + `///` hatch |
| Other | `#D4D4D4` | Light gray |

### 1.5 Map-Specific Colors

| Element | Hex | Opacity | Usage |
|---------|-----|---------|-------|
| Fatal crash dot | `#1a1a1a` | 0.8 | Black, radius 3.5 |
| Injury crash dot | `#888888` | 0.35 | Gray, radius 1.8 |
| Property damage dot | `#aaaaaa` | 0.2 | Light gray, radius 1.2 |
| Marker outline | `#333333` | — | Dark outline on all request markers |
| CB5 boundary | — | — | GeoJSON polygon, semi-transparent |

### 1.6 Rules

1. **QCB5 is ALWAYS navy blue (`#2C5F8B`).** Never use goldenrod, gray, or any other color for QCB5/Queens data.
2. **Citywide is ALWAYS dark goldenrod (`#B8860B`).** This includes: comparison bars, comparison trend lines, citywide average reference lines.
3. **Denied is ALWAYS muted red (`#B44040`).** Approved is ALWAYS muted green (`#4A7C59`).
4. **Never use denied red for non-denial elements** (e.g., average lines, borders, neutral data).
5. **The categorical palette reuses semantic colors** where the category aligns (Traffic Signal = navy, etc.). This keeps visual language consistent even in stacked charts.

---

## 2. Typography

### 2.1 Charts (Matplotlib)

- **Font family**: System default (DejaVu Sans / Helvetica) — clean and readable at print DPI
- **Suptitle**: 14pt, bold
- **Panel titles**: 12pt, bold
- **Axis labels**: bold (default size)
- **Source citations**: 9pt, italic, color `#333333`
- **Data labels on bars**: 9pt, bold

### 2.2 Maps (Folium/Leaflet)

- **Font family**: `'Times New Roman', Georgia, serif` — applied via injected CSS to all Leaflet elements
- **Popup body**: 12px, line-height 1.5
- **Popup section dividers**: `<hr>` with `border-top: 1px solid #ccc`
- **Dynamic title**: Injected via JavaScript, Times New Roman

---

## 3. Chart Conventions

### 3.1 Titles

Every chart title **must** include:

1. **Specific year range** as `YYYY–YYYY` (en-dash, not hyphen)
2. **Sample size** as `n=X,XXX` (with comma formatting)
3. **QCB5** shorthand (never "CB5", "Queens CB5", or "Queens Community Board 5" in titles)

**Format**: `Chart Description (QCB5, n=XXX, YYYY–YYYY)` or `(Excl. APS, QCB5 n=XXX, YYYY–YYYY)`

### 3.2 Date Ranges

- **Main charts** (01–12): Filter to **2020–2025** only
- **Z-series charts** (01z, 03z, etc.): Use **actual year range from data** (e.g., 1999–2025), hard-capped at 2025
- **Never** use "Full History", "All Years", or any vague date language
- All dynamic year computations must be capped: `min(computed_year, 2025)`

### 3.3 APS Exclusion

Accessible Pedestrian Signals are **always excluded** from approval/denial rate calculations. When excluded, title must include `Excl. APS`. When shown in bar charts, use gray with `///` hatch pattern.

### 3.4 Source Citations

Every chart includes a bottom-left source citation:

```
Source: NYC Open Data - Signal Studies (w76s-c5u4), SRTS (9n6h-pt9g)
```

Format: 9pt italic, color `#333333`, positioned at `fig.text(0.01, -0.02, ...)`.

### 3.5 Grid & Layout

- Axes grid: ON, alpha 0.3, dashed
- X-axis grid: OFF for bar charts (vertical gridlines not useful for discrete bars)
- DPI: 150 for display, 300 for saved PNGs
- Background: white (`facecolor='white'`)

---

## 4. Map Conventions

### 4.1 Base Map

- Tiles: CartoDB Positron No Labels (`light_nolabels`) — clean, minimal, print-friendly
- Center: `[40.714, -73.889]` (CB5 center)
- Default zoom: 14
- Scale control: enabled

### 4.2 Layers (7 total)

| # | Layer | Default | Marker Style |
|---|-------|---------|-------------|
| 1 | Injury Crashes (2020–2025) | ON | Dot density — size/color by severity |
| 2 | Denied Signal Studies | ON | CircleMarker, r=6, denied red fill |
| 3 | Approved Signal Studies | ON | CircleMarker, r=6, approved green fill |
| 4 | Denied Speed Bumps | ON | CircleMarker, r=4, denied red fill |
| 5 | Approved Speed Bumps | ON | CircleMarker, r=4, approved green fill |
| 6 | DOT Effectiveness (Installed) | OFF | CircleMarker, r=7–14 (scaled by data), green/amber/gray fill |
| 7 | Top 15 Denied Spotlight | OFF | CircleMarker r=9 + 150m dashed circle + rank DivIcon |

### 4.3 Popup Content Standards

Every clickable marker must include **complete context**. Minimum fields by layer:

**Crash dots:**
- Location (streets), date, time
- Severity tag (FATAL / INJURY / Property damage)
- Pedestrian / cyclist / motorist injury breakdown
- Contributing factor, vehicle type
- Collision ID

**Signal studies (denied/approved):**
- Location, reference number
- Request type, outcome (color-coded)
- Date requested, status date, status description
- School name (if applicable), Vision Zero flag, findings
- Nearby crash metrics: crashes, injuries, ped. injuries, fatalities within 150m

**Speed bumps / SRTS (denied/approved):**
- Street segment (on/from/to), project code
- Outcome (color-coded), request date, project status
- Denial reason (if denied), install date (if installed)
- Traffic direction
- Nearby crash metrics within 150m

**DOT Effectiveness (installed):**
- Location, reference number
- Request type, date requested, install date
- Before-after crash and injury comparison with % change
- Analysis window (months)

**Top 15 Denied Spotlight:**
- Rank, location, dataset, request type
- Full crash metrics within 150m (crashes, injuries, ped. injuries, fatalities)

### 4.4 Tooltips (Hover)

Tooltips are brief summaries shown on hover (before clicking):
- Crash dots: `"Location — Date"`
- Signal studies: `"Location — Type (DENIED/APPROVED)"`
- Speed bumps: `"Street (From to To) — DENIED/APPROVED"`
- Effectiveness: `"Location — X% fewer/more crashes"`
- Top 15: `"#Rank: Location (X crashes)"`

### 4.5 Dynamic Title

Map title updates via JavaScript MutationObserver based on active layer checkboxes. Priority conditions (first match wins):
1. Top 15 Spotlight active → "Top 15 Denied Locations..."
2. Effectiveness active → "DOT Effectiveness..."
3. Denied + Crashes active → "Crash-Denial Overlay..."
4. Only Denied active → "Denied Requests..."
5. Default → "QCB5 Safety Infrastructure..."

---

## 5. Naming Conventions

| Term | Standard Form | Never Use |
|------|--------------|-----------|
| Community Board | QCB5 | CB5, Queens CB5, Queens Community Board 5 |
| Year ranges | 2020–2025 (en-dash) | 2020-2025 (hyphen), "Full History", "All Years" |
| Approval | Approved | Feasible (except raw SRTS field names) |
| Denial | Denied | Not Feasible (except raw SRTS field names) |
| Speed bumps | Speed Bumps / SRTS | Speed reducers, humps |

---

## 6. File Naming

- Charts: `chart_XX_descriptive_name.png` (main), `chart_XXz_descriptive_name.png` (z-series)
- Maps: `map_01_crash_denial_overlay.html` (consolidated)
- Data tables: `table_XX_descriptive_name.csv`
- Cache: `geocode_cache_signal_studies.csv`

---

## 7. Quick Reference: Color Hex Codes

```python
COLORS = {
    'primary':       '#2C5F8B',   # Navy blue — QCB5 / local subject
    'citywide':      '#B8860B',   # Dark goldenrod — citywide comparison
    'denied':        '#B44040',   # Muted red — denied requests
    'approved':      '#4A7C59',   # Muted green — approved requests
    'crash':         '#996633',   # Warm brown — crash data
    'crash_alt':     '#CC9966',   # Light brown — injury data
    'avg_line':      '#B8860B',   # Goldenrod dashed — citywide average reference
    'cb5_highlight': '#1B3F5E',   # Dark navy — QCB5 highlight in ranked lists
    'secondary':     '#666666',   # Gray — secondary/muted elements
}

DENIAL_SHADES = ['#8B2020', '#B44040', '#C46060', '#D48080', '#DDA0A0', '#E6B8B8', '#EED0D0']

CATEGORY_PALETTE = ['#2C5F8B', '#B8860B', '#4A7C59', '#B44040', '#999999', '#D4D4D4']

# Map crash dots
CRASH_FATAL   = '#1a1a1a'  # opacity 0.8, r=3.5
CRASH_INJURY  = '#888888'  # opacity 0.35, r=1.8
CRASH_OTHER   = '#aaaaaa'  # opacity 0.2, r=1.2

# Before-after effectiveness
EFFECTIVE_IMPROVED  = '#2d7d46'
EFFECTIVE_WORSE     = '#cc8400'
EFFECTIVE_NOCHANGE  = '#777777'
```
