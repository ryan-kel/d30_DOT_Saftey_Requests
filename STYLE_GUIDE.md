# Electoral Analytics — Visual Style Guide

This document defines the visual language for all charts, maps, and data visualizations produced by Electoral Analytics. **All projects must follow these conventions.** When in doubt, reference the hex codes and rules below — do not improvise.

---

## 1. Color Palette

### 1.1 Core Semantic Colors

These colors have fixed meanings across all projects. Never swap them or repurpose them.

| Role | Hex | Swatch | Usage |
|------|-----|--------|-------|
| **Primary / Local subject** | `#2C5F8B` | Navy blue | The main subject of analysis (e.g., a specific district, neighborhood, agency) |
| **Comparison / Baseline** | `#B8860B` | Dark goldenrod | Citywide averages, comparison groups, reference lines |
| **Negative outcome** | `#B44040` | Muted red | Denials, failures, declines, unfavorable outcomes |
| **Positive outcome** | `#4A7C59` | Muted green | Approvals, successes, improvements, favorable outcomes |
| **Neutral data (primary)** | `#996633` | Warm brown | Raw counts, volume metrics (e.g., crash counts) |
| **Neutral data (secondary)** | `#CC9966` | Light warm brown | Secondary metrics, injury overlays |

### 1.2 Extended Palette

| Role | Hex | Usage |
|------|-----|-------|
| **Subject highlight** | `#1B3F5E` | Darker navy — highlight the primary subject in ranked lists |
| **Improved (before-after)** | `#2d7d46` | Strong green — outcome improved after intervention |
| **Worsened (before-after)** | `#cc8400` | Amber — outcome worsened after intervention |
| **No change** | `#777777` | Neutral gray — no measurable change |
| **Muted / secondary text** | `#666666` | Gray — secondary labels, annotations |
| **Excluded / not applicable** | `#999999` | Gray with `///` hatch — excluded categories (e.g., court-mandated items) |

### 1.3 Gradient Shades

For ranked bars (darkest = highest value, lightest = lowest):

**Negative outcome gradient:**
```
'#8B2020', '#B44040', '#C46060', '#D48080', '#DDA0A0', '#E6B8B8', '#EED0D0'
```

### 1.4 Categorical Palette

For multi-category stacked/grouped bars, assign in this order. Where a category aligns with a semantic role, reuse its semantic color.

```
'#2C5F8B', '#B8860B', '#4A7C59', '#B44040', '#999999', '#D4D4D4'
  Navy      Goldenrod   Green      Red       Gray     Light gray
```

### 1.5 Injury-Type Palette

For victim/person-type breakdowns (pedestrian, cyclist, motorist):

| Category | Hex | Rationale |
|----------|-----|-----------|
| Pedestrians | `#B44040` | Red — highest policy priority |
| Cyclists | `#B8860B` | Goldenrod |
| Motorists | `#CC9966` | Tan |

### 1.6 Map-Specific Colors

| Element | Hex | Opacity | Size |
|---------|-----|---------|------|
| Fatal incident | `#1a1a1a` | 0.8 | r=3.5 |
| Injury incident | `#888888` | 0.35 | r=1.8 |
| Property damage / minor | `#aaaaaa` | 0.2 | r=1.2 |
| Marker outline | `#333333` | — | weight=2 |
| Spotlight radius circle | Same as dot | 0.08 fill | 150m, dashed stroke `5 3` |

### 1.7 Color Rules

1. **Primary subject is ALWAYS navy (`#2C5F8B`).** Never use goldenrod or gray for the primary subject.
2. **Comparison/baseline is ALWAYS goldenrod (`#B8860B`).** This includes: comparison bars, comparison trend lines, average reference lines.
3. **Negative = red (`#B44040`), Positive = green (`#4A7C59`).** No exceptions.
4. **Never use negative red for non-negative elements** (e.g., average lines, borders, neutral data).
5. **The categorical palette reuses semantic colors** where the category aligns. This keeps visual language consistent even in stacked charts.

---

## 2. Typography

### 2.1 Charts (Matplotlib)

| Element | Size | Weight | Color |
|---------|------|--------|-------|
| Suptitle | 14pt | Bold | Black |
| Panel titles | 12pt | Bold | Black |
| Axis labels | Default | Bold | Black |
| Data labels on bars | 9pt | Bold | Black |
| Source citation | 9pt | Italic | `#333333` |

- **Font family**: System default (DejaVu Sans / Helvetica)
- **Background**: White (`facecolor='white'`)
- **DPI**: 150 for screen, 300 for saved PNGs

### 2.2 Maps (Folium / Leaflet)

| Element | Size | Notes |
|---------|------|-------|
| All UI text | — | `'Times New Roman', Georgia, serif` via injected CSS |
| Popup body | 12px | line-height 1.5 |
| Popup bold headers | 13px | Bold |
| Layer control | 12px | |
| Dynamic title | 15px | Bold, centered, white background at 92% opacity |
| Dynamic subtitle | 11px | Color `#555` |
| Legend header | 13px | Bold, bottom border |
| Legend items | 12px | line-height 1.8 |

### 2.3 Mobile (< 600px)

| Element | Adjustment |
|---------|-----------|
| Legend | 10px font, 6px 8px padding, max-width 160px |
| Legend header | 11px |
| Legend dots | 9px |
| Title | 13px, 5px 12px padding |
| Subtitle | 9px |

---

## 3. Chart Conventions

### 3.1 Titles

Every chart title **must** include:

1. **Year range** as `YYYY–YYYY` (en-dash `–`, not hyphen `-`)
2. **Sample size** as `n=X,XXX` (comma-formatted)
3. **Subject identifier** in the main title line (e.g., QCB5, Borough name)

**Format**: Subject name **always in the main title**, never in a parenthetical subtitle. Parentheses contain only data qualifiers (n=, dates, exclusion notes).

```
Correct:  QCB5 Signal Study Requests by Type\n(n=499, 2020–2025)
Correct:  Citywide Requests by Borough\n(n=17,824, 2020–2025)
Wrong:    Signal Study Requests by Type\n(QCB5, n=499, 2020–2025)
```

### 3.2 Date Ranges

- **Main charts**: Filter to the project's primary analysis window (e.g., 2020–2025)
- **Extended charts**: Use actual year range from data, hard-capped at the current year
- **Never** use "Full History", "All Years", "vs", or vague date language
- All dynamic year computations: `min(computed_year, CURRENT_YEAR)`

### 3.3 Source Citations

Every chart includes a bottom-left source citation:

```
Source: NYC Open Data — Dataset Name [endpoint_id]
```

Rules:
- Em dash `—` after the data provider name
- Dataset endpoint IDs in **square brackets** `[xxxx-xxxx]`
- Spell out full dataset names (no abbreviations in source lines)
- Format: 9pt italic, color `#333333`, positioned at `fig.text(0.01, -0.02, ...)`

### 3.4 Grid & Layout

- Y-axis grid: ON, alpha 0.3, dashed
- X-axis grid: OFF for bar charts
- Background: white
- Tight layout with padding for source citation

---

## 4. Map Conventions

### 4.1 Base Map

- **Tiles**: CartoDB Positron — split into two layers:
  - `light_nolabels` — base (non-interactive)
  - `light_only_labels` — overlay, opacity 0.55 (tames label repetition)
- **Scale control**: enabled
- **Layer control**: expanded (not collapsed)

### 4.2 Marker Styles

| Type | Marker | Size | Fill Opacity |
|------|--------|------|-------------|
| Request (denied/approved) | CircleMarker | r=4–6 | 0.85 |
| Incident dot | CircleMarker | r=1.2–3.5 by severity | 0.2–0.8 |
| Spotlight / ranked | CircleMarker r=9 + 150m dashed Circle + rank DivIcon | — | 0.85 dot, 0.08 radius |
| Before-after | CircleMarker r=7–14 (scaled by data volume) + 150m dashed Circle | — | 0.8 |

### 4.3 Overlapping Points

When many data points share the same coordinates (e.g., crashes at an intersection):
- **Default**: Apply small coordinate jitter (~5m / 0.00005°, seeded RNG) so dots spread apart and are individually clickable
- **Optional analysis layer**: MarkerCluster (off by default) with custom gray cluster icons, spiderfy on max zoom, `maxClusterRadius: 25`

### 4.4 Legend

- **Position**: fixed, bottom-left (30px from edges)
- **Dynamic**: Items show/hide based on active layer checkboxes via JavaScript
- **Entire legend hides** when no matching layers are active
- **Icon styles**:
  - `dot` — filled circle (12px) with 1px solid `#999` border
  - `spotlight` — 16px dashed-border circle with 6px filled dot centered inside
- **Mobile**: scales down per Section 2.3

### 4.5 Dynamic Title

Title bar updates via JavaScript MutationObserver + change/click listeners on the layer control. Shows context-appropriate title based on which layers are active. Falls back to a generic title when no specific combination matches.

### 4.6 Popups

Every clickable marker must include **complete context**:
- Location (streets/intersection)
- Date and identifier (reference number, collision ID, etc.)
- Outcome or severity (color-coded inline)
- Key metrics with clear labels
- Section dividers: `<hr>` with `border-top: 1px solid #ccc`

### 4.7 Tooltips (Hover)

Brief one-line summaries: `"Location — Key metric, Date"`

---

## 5. Naming Conventions

| Concept | Standard Form | Avoid |
|---------|--------------|-------|
| Year ranges | 2020–2025 (en-dash) | Hyphens, "Full History", "All Years" |
| Comparisons | "and" | "vs", "vs." |
| Positive outcome | Approved | Feasible (unless raw field name) |
| Negative outcome | Denied | Not Feasible (unless raw field name) |
| Community boards | QCB5, QCB1, etc. | CB5, Queens CB5 |

---

## 6. File Naming

| Type | Pattern | Example |
|------|---------|---------|
| Charts (main) | `chart_XX_descriptive_name.png` | `chart_01_request_volume.png` |
| Charts (extended) | `chart_XXz_descriptive_name.png` | `chart_01z_request_volume_full.png` |
| Maps | `map_XX_descriptive_name.html` | `map_01_crash_denial_overlay.html` |
| Data tables | `table_XX_descriptive_name.csv` | `table_09_crash_proximity.csv` |
| Map layer exports | `map_layer_descriptive_name.csv` | `map_layer_denied_signals.csv` |
| Data bundles | `data_bundle_vX.X.zip` | `data_bundle_v1.0.zip` |

---

## 7. Quick Reference: All Hex Codes

```python
# === Core semantic colors ===
COLORS = {
    'primary':       '#2C5F8B',   # Navy — primary subject
    'citywide':      '#B8860B',   # Goldenrod — comparison / baseline
    'denied':        '#B44040',   # Red — negative outcome
    'approved':      '#4A7C59',   # Green — positive outcome
    'crash':         '#996633',   # Brown — neutral data (primary)
    'crash_alt':     '#CC9966',   # Tan — neutral data (secondary)
}

# === Extended palette ===
HIGHLIGHT       = '#1B3F5E'   # Dark navy — subject highlight in ranked lists
IMPROVED        = '#2d7d46'   # Green — outcome improved
WORSENED        = '#cc8400'   # Amber — outcome worsened
NO_CHANGE       = '#777777'   # Gray — no change
SECONDARY_TEXT  = '#666666'   # Gray — muted labels
EXCLUDED        = '#999999'   # Gray + /// hatch — excluded categories

# === Gradients ===
NEGATIVE_SHADES = ['#8B2020', '#B44040', '#C46060', '#D48080', '#DDA0A0', '#E6B8B8', '#EED0D0']
CATEGORY_ORDER  = ['#2C5F8B', '#B8860B', '#4A7C59', '#B44040', '#999999', '#D4D4D4']

# === Injury-type palette ===
PEDESTRIAN = '#B44040'
CYCLIST    = '#B8860B'
MOTORIST   = '#CC9966'

# === Map incident dots ===
FATAL    = '#1a1a1a'   # opacity 0.8,  r=3.5
INJURY   = '#888888'   # opacity 0.35, r=1.8
MINOR    = '#aaaaaa'   # opacity 0.2,  r=1.2
OUTLINE  = '#333333'   # marker outlines

# === Before-after markers ===
EFFECTIVE_IMPROVED  = '#2d7d46'
EFFECTIVE_WORSENED  = '#cc8400'
EFFECTIVE_NOCHANGE  = '#777777'
```
