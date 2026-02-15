"""
Map Generation & Crash-Denial Correlation Analysis for CB5
==========================================================
Part 2: Correlates crash locations with denied/approved safety request
locations. Produces interactive HTML maps (folium) and static charts
(matplotlib).

Usage:
    python generate_maps.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import folium
from folium.plugins import HeatMap  # kept for fallback; primary map uses dot density
from shapely.geometry import shape, Point
from shapely.prepared import prep
import json
import warnings
import os
import math

warnings.filterwarnings('ignore')

# === CONFIGURATION ===
DATA_DIR = "data_raw"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

GEOCODE_CACHE_PATH = f"{OUTPUT_DIR}/geocode_cache_signal_studies.csv"
CB5_BOUNDARY_PATH = f"{DATA_DIR}/cb5_boundary.geojson"
CB5_BOUNDARY_URL = "https://raw.githubusercontent.com/nycehs/NYC_geography/master/CD.geo.json"

# Proximity analysis radius in meters
PROXIMITY_RADIUS_M = 150

# CB5 center for map defaults
CB5_CENTER = [40.714, -73.889]
CB5_ZOOM = 14

# Color scheme — muted academic tones for print readability
COLORS = {
    'primary': '#2C5F8B',
    'citywide': '#B8860B',
    'denied': '#B44040',
    'approved': '#4A7C59',
    'crash': '#996633',
    'crash_alt': '#CC9966',
}

# Muted heatmap gradient — warm parchment tones for print
HEATMAP_GRADIENT = {
    0.2: '#f5f0e1', 0.4: '#e0cda9', 0.6: '#c9a96e',
    0.8: '#a07850', 1.0: '#7a4a2a',
}

# Global CSS for Times New Roman on all Leaflet UI elements
MAP_FONT_CSS = """
<style>
  .leaflet-popup-content, .leaflet-control-layers,
  .leaflet-tooltip, .map-legend, .map-title {
      font-family: 'Times New Roman', 'Liberation Serif', Georgia, serif !important;
  }
  .leaflet-popup-content { font-size: 12px; line-height: 1.5; }
  .leaflet-popup-content b { font-size: 13px; }
  .leaflet-control-layers-list { font-size: 12px; }
</style>
"""


def _inject_map_css(m):
    """Inject Times New Roman CSS into a folium map."""
    m.get_root().html.add_child(folium.Element(MAP_FONT_CSS))


def _add_dynamic_title(m):
    """Add a dynamic title that updates based on which layer checkboxes are active."""
    html = '''<div class="map-title" id="map-title-container" style="position:fixed;top:10px;left:50%;
        transform:translateX(-50%);z-index:1000;background:rgba(255,255,255,0.92);
        padding:8px 20px;border:1px solid #666;
        font-family:'Times New Roman',Georgia,serif;text-align:center;">
        <div id="map-dynamic-title" style="font-size:15px;font-weight:bold;">Safety Request Outcomes: QCB5 (Queens Community Board 5)</div>
        <div id="map-dynamic-subtitle" style="font-size:11px;color:#555;margin-top:2px;">Signal Studies &amp; Speed Bumps vs. Injury Crashes (2020\u20132025)</div>
    </div>
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        function updateTitle() {
            var checkboxes = document.querySelectorAll('.leaflet-control-layers-overlays label');
            var layers = {};
            checkboxes.forEach(function(label) {
                var cb = label.querySelector('input');
                var name = label.textContent.trim();
                layers[name] = cb && cb.checked;
            });
            var titleEl = document.getElementById('map-dynamic-title');
            var subtitleEl = document.getElementById('map-dynamic-subtitle');
            // Match layer names by prefix (names now include n= and year suffixes)
            function isActive(prefix) {
                for (var key in layers) {
                    if (key.indexOf(prefix) === 0 && layers[key]) return true;
                }
                return false;
            }
            var spotlight = isActive('Top 15 Denied');
            var effectiveness = isActive('DOT Effectiveness');
            var signals = isActive('Denied Signal') || isActive('Approved Signal');
            var srts = isActive('Denied Speed') || isActive('Approved Speed');
            if (effectiveness) {
                titleEl.textContent = 'DOT Effectiveness: Crash Outcomes After Installation';
                subtitleEl.textContent = 'Before-After Analysis, Confirmed Installations, QCB5';
            } else if (spotlight) {
                titleEl.textContent = 'Top 15 Denied Locations by Nearby Crash Count';
                subtitleEl.textContent = '150m Analysis Radius, QCB5';
            } else if (signals && srts) {
                titleEl.textContent = 'Safety Request Outcomes: QCB5';
                subtitleEl.textContent = 'Signal Studies & Speed Bumps vs. Injury Crashes (2020\u20132025)';
            } else if (signals) {
                titleEl.textContent = 'Signal Study Outcomes: QCB5';
                subtitleEl.textContent = 'Traffic Signal & Stop Sign Requests vs. Crash Data';
            } else if (srts) {
                titleEl.textContent = 'Speed Bump Requests & Injury Crashes';
                subtitleEl.textContent = 'SRTS Program, QCB5';
            } else {
                titleEl.textContent = 'Safety Infrastructure Data: QCB5';
                subtitleEl.textContent = 'Use layer controls to explore';
            }
        }
        // Wait for Leaflet layer control to render, then attach listeners
        var observer = new MutationObserver(function(mutations, obs) {
            var overlays = document.querySelector('.leaflet-control-layers-overlays');
            if (overlays) {
                obs.disconnect();
                overlays.addEventListener('change', updateTitle);
                updateTitle();
            }
        });
        observer.observe(document.body, {childList: true, subtree: true});
    });
    </script>'''
    m.get_root().html.add_child(folium.Element(html))

# Academic styling — matches generate_charts.py
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif', 'Liberation Serif'],
    'font.size': 11,
    'axes.titlesize': 13,
    'axes.titleweight': 'bold',
    'axes.labelsize': 11,
    'axes.labelweight': 'bold',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linestyle': '--'
})


# ============================================================
# Data Loading & Preparation (mirrors generate_charts.py)
# ============================================================

def _classify_outcome(status):
    if pd.isna(status):
        return 'unknown'
    s = status.lower()
    if 'denial' in s or ('engineering study completed' in s and 'approval' not in s):
        return 'denied'
    if 'approval' in s or 'approved' in s or 'aps installed' in s or 'aps ranking' in s or 'aps design' in s:
        return 'approved'
    return 'pending'


def _normalize_street_name(name):
    """Normalize street names for matching: uppercase, expand abbreviations."""
    if pd.isna(name) or str(name).strip() == '':
        return ''
    s = str(name).strip().upper()
    # Remove extra whitespace
    s = ' '.join(s.split())
    # Expand common abbreviations at end of string
    abbrevs = {
        ' AVE': ' AVENUE', ' BLVD': ' BOULEVARD', ' RD': ' ROAD',
        ' ST': ' STREET', ' PL': ' PLACE', ' DR': ' DRIVE',
        ' LN': ' LANE', ' CT': ' COURT', ' PKWY': ' PARKWAY',
        ' TPKE': ' TURNPIKE', ' EXPWY': ' EXPRESSWAY',
    }
    for abbr, full in abbrevs.items():
        if s.endswith(abbr):
            s = s[:-len(abbr)] + full
    return s


def _load_cb5_polygon():
    """Load the CB5 boundary as a shapely polygon for point-in-polygon tests.

    Downloads the GeoJSON from NYC geography GitHub repo if not cached locally.
    """
    geojson = _load_cb5_boundary()
    return shape(geojson['features'][0]['geometry'])


def _filter_points_in_cb5(df, lat_col='latitude', lon_col='longitude'):
    """Filter a DataFrame to only rows whose coordinates fall inside the CB5 polygon.

    Returns (filtered_df, n_excluded).
    """
    poly = _load_cb5_polygon()
    prepared = prep(poly)

    has_coords = df[lat_col].notna() & df[lon_col].notna()
    with_coords = df[has_coords]
    n_no_coords = (~has_coords).sum()

    inside = with_coords.apply(
        lambda r: prepared.contains(Point(r[lon_col], r[lat_col])), axis=1
    )
    filtered = with_coords[inside]
    n_excluded = (~inside).sum() + n_no_coords
    if n_no_coords > 0:
        print(f"    ({n_no_coords:,} rows without coordinates excluded)")
    return filtered, n_excluded


def _load_cb5_srts_full():
    """Load CB5 SRTS data with full filtering pipeline (all years).

    Applies: cb=405 → polygon filter (CB5 boundary polygon is sole authority).
    Returns all CB5 records (all statuses) with outcome column added
    (denied/approved for resolved, NaN for pending/other).
    """
    srts = pd.read_csv(f'{DATA_DIR}/srts_citywide.csv', low_memory=False)
    srts['cb_num'] = pd.to_numeric(srts['cb'], errors='coerce')
    srts['requestdate'] = pd.to_datetime(srts['requestdate'], errors='coerce')
    srts['year'] = srts['requestdate'].dt.year

    cb5_raw = srts[srts['cb_num'] == 405].copy()

    # Polygon filter: the CB5 boundary polygon is the sole authority.
    cb5_raw['fromlatitude'] = pd.to_numeric(cb5_raw['fromlatitude'], errors='coerce')
    cb5_raw['fromlongitude'] = pd.to_numeric(cb5_raw['fromlongitude'], errors='coerce')
    cb5, _ = _filter_points_in_cb5(cb5_raw, lat_col='fromlatitude', lon_col='fromlongitude')

    cb5['outcome'] = cb5['segmentstatusdescription'].map({
        'Not Feasible': 'denied', 'Feasible': 'approved'
    })
    return cb5


def load_and_prepare_data():
    """Load all datasets and apply standard filtering."""
    print("Loading datasets...")

    signal_studies = pd.read_csv(f'{DATA_DIR}/signal_studies_citywide.csv', low_memory=False)
    srts = pd.read_csv(f'{DATA_DIR}/srts_citywide.csv', low_memory=False)
    crashes = pd.read_csv(f'{DATA_DIR}/crashes_queens_2020plus.csv', low_memory=False)
    # Pre-filtered CB5 signal studies: Queens borough records filtered to CB5 boundary streets.
    # Curated input — not auto-generated — because signal studies lack a community board field.
    cb5_studies = pd.read_csv(f'{OUTPUT_DIR}/data_cb5_signal_studies.csv', low_memory=False)

    print(f"  Signal Studies: {len(signal_studies):,}")
    print(f"  SRTS: {len(srts):,}")
    print(f"  Crashes: {len(crashes):,}")
    print(f"  CB5 Studies: {len(cb5_studies):,}")

    # --- Signal studies ---
    cb5_studies['outcome'] = cb5_studies['statusdescription'].apply(_classify_outcome)
    cb5_studies['daterequested'] = pd.to_datetime(cb5_studies['daterequested'], errors='coerce')
    cb5_studies['year'] = cb5_studies['daterequested'].dt.year
    cb5_resolved = cb5_studies[cb5_studies['outcome'].isin(['denied', 'approved'])]
    cb5_no_aps = cb5_resolved[cb5_resolved['requesttype'] != 'Accessible Pedestrian Signal']

    # --- SRTS ---
    srts['cb_num'] = pd.to_numeric(srts['cb'], errors='coerce')
    srts['requestdate'] = pd.to_datetime(srts['requestdate'], errors='coerce')
    srts['year'] = srts['requestdate'].dt.year
    srts_resolved = srts[srts['segmentstatusdescription'].isin(['Not Feasible', 'Feasible'])]
    cb5_srts_raw = srts_resolved[srts_resolved['cb_num'] == 405]

    # Polygon filter: the CB5 boundary polygon is the sole authority for geographic filtering.
    cb5_srts = cb5_srts_raw.copy()
    cb5_srts['outcome'] = cb5_srts['segmentstatusdescription'].map({
        'Not Feasible': 'denied', 'Feasible': 'approved'
    })
    cb5_srts['fromlatitude'] = pd.to_numeric(cb5_srts['fromlatitude'], errors='coerce')
    cb5_srts['fromlongitude'] = pd.to_numeric(cb5_srts['fromlongitude'], errors='coerce')
    cb5_srts, n_srts_excluded = _filter_points_in_cb5(
        cb5_srts, lat_col='fromlatitude', lon_col='fromlongitude')
    print(f"  CB5 SRTS: {len(cb5_srts_raw):,} raw -> {len(cb5_srts):,} after polygon filter ({n_srts_excluded} excluded)")

    # Filter SRTS to 2020–2025 for consistency with signal studies and crashes
    n_before_year = len(cb5_srts)
    cb5_srts = cb5_srts[cb5_srts['year'].between(2020, 2025)].copy()
    print(f"  CB5 SRTS: -> {len(cb5_srts):,} after 2020–2025 filter ({n_before_year - len(cb5_srts)} excluded)")

    # --- Crashes ---
    crashes['crash_date'] = pd.to_datetime(crashes['crash_date'], errors='coerce')
    crashes['year'] = crashes['crash_date'].dt.year
    crashes = crashes[crashes['year'].between(2020, 2025)]
    crashes['latitude'] = pd.to_numeric(crashes['latitude'], errors='coerce')
    crashes['longitude'] = pd.to_numeric(crashes['longitude'], errors='coerce')
    crashes['number_of_persons_injured'] = pd.to_numeric(crashes['number_of_persons_injured'], errors='coerce').fillna(0)
    crashes['number_of_pedestrians_injured'] = pd.to_numeric(crashes['number_of_pedestrians_injured'], errors='coerce').fillna(0)
    crashes['number_of_persons_killed'] = pd.to_numeric(crashes['number_of_persons_killed'], errors='coerce').fillna(0)

    # Polygon filter: Crashes — use actual CB5 boundary, not bounding box
    cb5_crashes, n_crash_excluded = _filter_points_in_cb5(crashes)
    print(f"  CB5 Crashes: {len(cb5_crashes):,} (polygon filter, {n_crash_excluded} Queens crashes excluded)")

    return {
        'signal_studies': signal_studies,
        'cb5_studies': cb5_studies,
        'cb5_no_aps': cb5_no_aps,
        'srts': srts,
        'cb5_srts': cb5_srts,
        'crashes': crashes,
        'cb5_crashes': cb5_crashes,
    }


# ============================================================
# Step 1: Geocode Signal Study Intersections
# ============================================================

def _build_crash_location_lookup(crashes):
    """Build (street1, street2) -> (lat, lon) lookup from crash data.

    Crashes use on_street_name + off_street_name for intersection crashes.
    """
    df = crashes[
        crashes['on_street_name'].notna() &
        crashes['off_street_name'].notna() &
        crashes['latitude'].notna() &
        crashes['longitude'].notna()
    ].copy()

    df['street_a'] = df['on_street_name'].apply(_normalize_street_name)
    df['street_b'] = df['off_street_name'].apply(_normalize_street_name)
    df = df[(df['street_a'] != '') & (df['street_b'] != '')]

    # Canonical key: sorted pair
    def _sort_pair(row):
        a, b = sorted([row['street_a'], row['street_b']])
        return pd.Series({'key_a': a, 'key_b': b})

    keys = df.apply(_sort_pair, axis=1)
    df['key_a'] = keys['key_a']
    df['key_b'] = keys['key_b']

    lookup = df.groupby(['key_a', 'key_b']).agg(
        lat=('latitude', 'median'),
        lon=('longitude', 'median'),
        n=('latitude', 'count')
    ).reset_index()
    lookup.rename(columns={'key_a': 'street_a', 'key_b': 'street_b'}, inplace=True)
    return lookup


def _build_srts_location_lookup(srts):
    """Build (street1, street2) -> (lat, lon) lookup from SRTS data."""
    df = srts[
        srts['fromlatitude'].notna() &
        srts['fromlongitude'].notna()
    ].copy()

    df['fromlatitude'] = pd.to_numeric(df['fromlatitude'], errors='coerce')
    df['fromlongitude'] = pd.to_numeric(df['fromlongitude'], errors='coerce')
    df = df[df['fromlatitude'].notna() & df['fromlongitude'].notna()]

    results = {}
    for _, row in df.iterrows():
        main = _normalize_street_name(row.get('onstreet', ''))
        from_st = _normalize_street_name(row.get('fromstreet', ''))
        to_st = _normalize_street_name(row.get('tostreet', ''))
        lat = row['fromlatitude']
        lon = row['fromlongitude']

        if main and from_st:
            key = tuple(sorted([main, from_st]))
            if key not in results:
                results[key] = (lat, lon)
        if main and to_st:
            key = tuple(sorted([main, to_st]))
            if key not in results:
                results[key] = (lat, lon)
    return results


def _build_street_lines(crash_lookup, srts_lookup):
    """Build per-street linear regression lines from all known points.

    Returns dict: street_name -> (slope, intercept) for lat=f(lon).
    """
    street_points = {}

    # From crash lookup
    for _, row in crash_lookup.iterrows():
        for street in [row['street_a'], row['street_b']]:
            if street not in street_points:
                street_points[street] = []
            street_points[street].append((row['lon'], row['lat']))

    # From SRTS lookup
    for (s1, s2), (lat, lon) in srts_lookup.items():
        for street in [s1, s2]:
            if street not in street_points:
                street_points[street] = []
            street_points[street].append((lon, lat))

    street_lines = {}
    for street, points in street_points.items():
        if len(points) < 2:
            continue
        lons = np.array([p[0] for p in points])
        lats = np.array([p[1] for p in points])

        # Simple linear regression: lat = slope * lon + intercept
        if np.std(lons) < 1e-8:
            continue  # vertical line, skip
        slope, intercept = np.polyfit(lons, lats, 1)
        street_lines[street] = (slope, intercept)

    return street_lines


def _intersect_lines(line1, line2):
    """Find intersection of two lines: lat = slope * lon + intercept.

    Returns (lat, lon) or None if parallel.
    """
    s1, i1 = line1
    s2, i2 = line2
    if abs(s1 - s2) < 1e-10:
        return None  # parallel
    lon = (i2 - i1) / (s1 - s2)
    lat = s1 * lon + i1
    return (lat, lon)


def geocode_signal_studies(data):
    """Geocode CB5 signal study intersections using local data.

    Three tiers:
    1. Crash data intersection matching
    2. SRTS data matching
    3. Street-line intersection estimation
    """
    cb5_no_aps = data['cb5_no_aps'].copy()
    cb5_poly = _load_cb5_polygon()
    prepared_poly = prep(cb5_poly)

    def _in_cb5(lat, lon):
        return prepared_poly.contains(Point(lon, lat))

    # Check cache — but re-validate against polygon
    if os.path.exists(GEOCODE_CACHE_PATH):
        print("  Loading geocode cache...")
        cache = pd.read_csv(GEOCODE_CACHE_PATH)
        # Re-filter cached results against polygon (cache may predate polygon fix)
        has_coords = cache['latitude'].notna() & cache['longitude'].notna()
        if has_coords.any():
            inside = cache[has_coords].apply(
                lambda r: _in_cb5(r['latitude'], r['longitude']), axis=1)
            n_outside = (~inside).sum()
            if n_outside > 0:
                print(f"  Removing {n_outside} cached points outside CB5 polygon")
                cache.loc[has_coords & ~inside.reindex(cache.index, fill_value=True), ['latitude', 'longitude']] = np.nan
                cache.loc[has_coords & ~inside.reindex(cache.index, fill_value=True), 'geocode_tier'] = ''
                cache.to_csv(GEOCODE_CACHE_PATH, index=False)
        geocoded = cache['latitude'].notna().sum()
        print(f"  Cache: {len(cache)} records, {geocoded} geocoded ({geocoded/len(cache)*100:.0f}%)")
        return cache

    print("  Geocoding signal study intersections...")

    # Normalize signal study street names
    cb5_no_aps['main_norm'] = cb5_no_aps['mainstreet'].apply(_normalize_street_name)
    cb5_no_aps['cross_norm'] = cb5_no_aps['crossstreet1'].apply(_normalize_street_name)

    # Build lookups
    print("    Building crash location lookup...")
    crash_lookup = _build_crash_location_lookup(data['crashes'])
    print(f"    Crash lookup: {len(crash_lookup)} unique intersection pairs")

    print("    Building SRTS location lookup...")
    srts_lookup = _build_srts_location_lookup(data['srts'])
    print(f"    SRTS lookup: {len(srts_lookup)} unique intersection pairs")

    # Results arrays
    lats = np.full(len(cb5_no_aps), np.nan)
    lons = np.full(len(cb5_no_aps), np.nan)
    geo_tier = np.full(len(cb5_no_aps), '', dtype=object)

    # Tier 1: Crash data matching
    crash_keys = {}
    for idx, row in crash_lookup.iterrows():
        key = tuple(sorted([row['street_a'], row['street_b']]))
        crash_keys[key] = (row['lat'], row['lon'])

    tier1_count = 0
    for i, (_, row) in enumerate(cb5_no_aps.iterrows()):
        main = row['main_norm']
        cross = row['cross_norm']
        if not main or not cross:
            continue

        key = tuple(sorted([main, cross]))
        if key in crash_keys:
            lat, lon = crash_keys[key]
            if _in_cb5(lat, lon):
                lats[i] = lat
                lons[i] = lon
                geo_tier[i] = 'crash'
                tier1_count += 1

    print(f"    Tier 1 (crash match): {tier1_count}/{len(cb5_no_aps)} "
          f"({tier1_count/len(cb5_no_aps)*100:.0f}%)")

    # Tier 2: SRTS matching
    tier2_count = 0
    for i, (_, row) in enumerate(cb5_no_aps.iterrows()):
        if not np.isnan(lats[i]):
            continue
        main = row['main_norm']
        cross = row['cross_norm']
        if not main or not cross:
            continue

        key = tuple(sorted([main, cross]))
        if key in srts_lookup:
            lat, lon = srts_lookup[key]
            if _in_cb5(lat, lon):
                lats[i] = lat
                lons[i] = lon
                geo_tier[i] = 'srts'
                tier2_count += 1

    print(f"    Tier 2 (SRTS match): {tier2_count}/{len(cb5_no_aps)} "
          f"({tier2_count/len(cb5_no_aps)*100:.0f}%)")

    # Tier 3: Street-line intersection
    print("    Building street regression lines...")
    street_lines = _build_street_lines(crash_lookup, srts_lookup)
    print(f"    Street lines: {len(street_lines)} streets with regression lines")

    tier3_count = 0
    for i, (_, row) in enumerate(cb5_no_aps.iterrows()):
        if not np.isnan(lats[i]):
            continue
        main = row['main_norm']
        cross = row['cross_norm']
        if not main or not cross:
            continue
        if main not in street_lines or cross not in street_lines:
            continue

        result = _intersect_lines(street_lines[main], street_lines[cross])
        if result is None:
            continue
        lat, lon = result
        if _in_cb5(lat, lon):
            lats[i] = lat
            lons[i] = lon
            geo_tier[i] = 'street_line'
            tier3_count += 1

    print(f"    Tier 3 (street-line): {tier3_count}/{len(cb5_no_aps)} "
          f"({tier3_count/len(cb5_no_aps)*100:.0f}%)")

    total_geocoded = tier1_count + tier2_count + tier3_count
    print(f"    Total geocoded: {total_geocoded}/{len(cb5_no_aps)} "
          f"({total_geocoded/len(cb5_no_aps)*100:.0f}%)")

    # Build result DataFrame
    cb5_no_aps = cb5_no_aps.copy()
    cb5_no_aps['latitude'] = lats
    cb5_no_aps['longitude'] = lons
    cb5_no_aps['geocode_tier'] = geo_tier

    # Save cache
    cache_cols = ['referencenumber', 'mainstreet', 'crossstreet1', 'requesttype',
                  'statusdescription', 'outcome', 'year',
                  'daterequested', 'statusdate',
                  'latitude', 'longitude',
                  'geocode_tier', 'main_norm', 'cross_norm']
    cache_df = cb5_no_aps[[c for c in cache_cols if c in cb5_no_aps.columns]].copy()
    cache_df.to_csv(GEOCODE_CACHE_PATH, index=False)
    print(f"    Cache saved to {GEOCODE_CACHE_PATH}")

    return cache_df


# ============================================================
# Step 2: Proximity Analysis (Haversine)
# ============================================================

def _haversine_m(lat1, lon1, lat2, lon2):
    """Haversine distance in meters between two points."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _haversine_vectorized(lat1, lon1, lat2_arr, lon2_arr):
    """Haversine distance from one point to arrays of points. Returns meters."""
    R = 6371000
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2_arr)
    dphi = np.radians(lat2_arr - lat1)
    dlam = np.radians(lon2_arr - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def compute_proximity(locations_df, crashes_df, radius_m=PROXIMITY_RADIUS_M):
    """For each location, count crashes/injuries within radius.

    locations_df must have 'latitude', 'longitude' columns.
    Returns DataFrame with added columns: crashes_150m, injuries_150m,
    ped_injuries_150m, fatalities_150m.
    """
    crash_lats = crashes_df['latitude'].values
    crash_lons = crashes_df['longitude'].values
    crash_injuries = crashes_df['number_of_persons_injured'].values
    crash_ped_injuries = crashes_df['number_of_pedestrians_injured'].values
    crash_fatalities = crashes_df['number_of_persons_killed'].values

    results = {
        'crashes_150m': [],
        'injuries_150m': [],
        'ped_injuries_150m': [],
        'fatalities_150m': [],
    }

    for _, row in locations_df.iterrows():
        lat = row['latitude']
        lon = row['longitude']

        if pd.isna(lat) or pd.isna(lon):
            for key in results:
                results[key].append(np.nan)
            continue

        dists = _haversine_vectorized(lat, lon, crash_lats, crash_lons)
        mask = dists <= radius_m

        results['crashes_150m'].append(mask.sum())
        results['injuries_150m'].append(crash_injuries[mask].sum())
        results['ped_injuries_150m'].append(crash_ped_injuries[mask].sum())
        results['fatalities_150m'].append(crash_fatalities[mask].sum())

    for key, vals in results.items():
        locations_df = locations_df.copy()
        locations_df[key] = vals

    return locations_df


def _mann_whitney_u(x, y):
    """Manual Mann-Whitney U test (no scipy dependency).

    Returns (U statistic, approximate two-sided p-value).
    """
    x = np.array(x, dtype=float)
    y = np.array(y, dtype=float)
    x = x[~np.isnan(x)]
    y = y[~np.isnan(y)]

    n1 = len(x)
    n2 = len(y)
    if n1 == 0 or n2 == 0:
        return np.nan, np.nan

    # Rank all values together
    combined = np.concatenate([x, y])
    order = np.argsort(combined)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(combined) + 1, dtype=float)

    # Handle ties: average ranks for tied values
    sorted_combined = combined[order]
    i = 0
    while i < len(sorted_combined):
        j = i + 1
        while j < len(sorted_combined) and sorted_combined[j] == sorted_combined[i]:
            j += 1
        if j > i + 1:
            avg_rank = np.mean(ranks[order[i:j]])
            for k in range(i, j):
                ranks[order[k]] = avg_rank
        i = j

    R1 = ranks[:n1].sum()
    U1 = R1 - n1 * (n1 + 1) / 2

    # Normal approximation for p-value
    mu = n1 * n2 / 2
    sigma = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    if sigma == 0:
        return U1, 1.0

    z = (U1 - mu) / sigma
    # Two-sided p-value via normal CDF approximation (Abramowitz & Stegun)
    az = abs(z)
    # Simple CDF approximation
    t = 1.0 / (1.0 + 0.2316419 * az)
    d = 0.3989422804014327  # 1/sqrt(2*pi)
    p_one = d * math.exp(-0.5 * az * az) * (
        t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    )
    p_two = 2 * p_one

    return U1, min(p_two, 1.0)


def run_proximity_analysis(signal_geo, srts_df, cb5_crashes):
    """Run proximity analysis for both signal studies and SRTS."""
    print("\n  Computing proximity for signal studies...")
    signal_with_coords = signal_geo[signal_geo['latitude'].notna()].copy()
    signal_prox = compute_proximity(signal_with_coords, cb5_crashes)

    print("  Computing proximity for SRTS...")
    srts_with_coords = srts_df.copy()
    srts_with_coords['latitude'] = pd.to_numeric(srts_with_coords['fromlatitude'], errors='coerce')
    srts_with_coords['longitude'] = pd.to_numeric(srts_with_coords['fromlongitude'], errors='coerce')
    srts_with_coords = srts_with_coords[srts_with_coords['latitude'].notna()].copy()
    srts_prox = compute_proximity(srts_with_coords, cb5_crashes)

    return signal_prox, srts_prox


# ============================================================
# Step 3: Maps (Folium)
# ============================================================

def _make_legend_html(items):
    """Generate HTML for a simple map legend — academic style."""
    html = ('<div class="map-legend" style="position:fixed;bottom:30px;left:30px;z-index:1000;'
            'background:white;padding:10px 14px;border:1px solid #666;'
            "font-family:'Times New Roman',Georgia,serif;font-size:12px;line-height:1.8;\">")
    html += ('<span style="font-size:13px;font-weight:bold;border-bottom:1px solid #999;'
             'display:block;margin-bottom:4px;padding-bottom:2px;">Legend</span>')
    for color, label in items:
        html += (f'<span style="display:inline-block;width:12px;height:12px;background:{color};'
                 f'border:1px solid #999;border-radius:50%;margin-right:6px;'
                 f'vertical-align:middle;"></span>{label}<br>')
    html += '</div>'
    return html


def _load_cb5_boundary():
    """Load CB5 boundary GeoJSON, downloading if needed."""
    if os.path.exists(CB5_BOUNDARY_PATH):
        with open(CB5_BOUNDARY_PATH) as f:
            return json.load(f)

    # Download from NYC geography GitHub repo
    print("    Downloading CB5 boundary GeoJSON...")
    import requests
    resp = requests.get(CB5_BOUNDARY_URL, timeout=30)
    resp.raise_for_status()
    all_districts = resp.json()

    # Extract Queens CB5 (GEOCODE=405)
    for feature in all_districts.get('features', []):
        if feature.get('properties', {}).get('GEOCODE') == 405:
            cb5_geojson = {"type": "FeatureCollection", "features": [feature]}
            with open(CB5_BOUNDARY_PATH, 'w') as f:
                json.dump(cb5_geojson, f)
            print(f"    Saved CB5 boundary to {CB5_BOUNDARY_PATH}")
            return cb5_geojson

    raise ValueError("Could not find GEOCODE=405 in community districts GeoJSON")


def _add_cb5_boundary(m):
    """Add real CB5 community district boundary to a folium map."""
    geojson = _load_cb5_boundary()
    folium.GeoJson(
        geojson,
        name='CB5 Boundary',
        style_function=lambda x: {
            'color': '#555555',
            'weight': 2,
            'opacity': 0.6,
            'fillColor': '#555555',
            'fillOpacity': 0.02,
            'dashArray': '6 3',
            'interactive': False,
        },
    ).add_to(m)


def _compute_before_after(data):
    """Compute before-after crash analysis for installed signal study locations.

    Only includes locations with confirmed installation dates
    (aw_installdate or signalinstalldate populated).

    Returns DataFrame with before/after crash counts and change metrics.
    """
    print("    Computing before-after analysis for installed locations...")

    cb5_studies_full = pd.read_csv(f'{OUTPUT_DIR}/data_cb5_signal_studies.csv', low_memory=False)
    cb5_studies_full['outcome'] = cb5_studies_full['statusdescription'].apply(_classify_outcome)
    approved = cb5_studies_full[
        (cb5_studies_full['outcome'] == 'approved') &
        (cb5_studies_full['requesttype'] != 'Accessible Pedestrian Signal')
    ]

    # Only truly installed: must have an install date
    installed = approved[
        approved['aw_installdate'].notna() | approved['signalinstalldate'].notna()
    ].copy()
    installed['install_date'] = pd.to_datetime(
        installed['aw_installdate'].fillna(installed['signalinstalldate']), errors='coerce')
    installed = installed.drop_duplicates(subset='referencenumber')

    # Merge coordinates from geocode cache
    cache = pd.read_csv(GEOCODE_CACHE_PATH, low_memory=False)
    installed = installed.merge(
        cache[['referencenumber', 'latitude', 'longitude']].drop_duplicates('referencenumber'),
        on='referencenumber', how='left', suffixes=('_orig', ''))
    installed = installed[installed['latitude'].notna() & installed['longitude'].notna()].copy()

    # Crash arrays for vectorized computation
    cb5_crashes = data['cb5_crashes']
    crash_lats = cb5_crashes['latitude'].values
    crash_lons = cb5_crashes['longitude'].values
    crash_dates = cb5_crashes['crash_date'].values
    crash_injured = cb5_crashes['number_of_persons_injured'].values
    crash_ped_inj = cb5_crashes['number_of_pedestrians_injured'].values

    DATA_START = pd.Timestamp('2020-01-01')
    DATA_END = cb5_crashes['crash_date'].max()
    if pd.isna(DATA_END):
        DATA_END = pd.Timestamp('2025-12-31')

    results = []
    for _, row in installed.iterrows():
        lat, lon = row['latitude'], row['longitude']
        install_dt = row['install_date']

        dists = _haversine_vectorized(lat, lon, crash_lats, crash_lons)
        within_150m = dists <= PROXIMITY_RADIUS_M

        # Equal time windows before and after, capped at 24 months
        months_before = (install_dt - DATA_START).days / 30.44
        months_after = (DATA_END - install_dt).days / 30.44
        window_months = min(months_before, months_after, 24)
        window_days = int(window_months * 30.44)

        before_start = install_dt - pd.Timedelta(days=window_days)
        after_end = install_dt + pd.Timedelta(days=window_days)

        before_mask = (within_150m &
                       (crash_dates >= np.datetime64(before_start)) &
                       (crash_dates < np.datetime64(install_dt)))
        after_mask = (within_150m &
                      (crash_dates >= np.datetime64(install_dt)) &
                      (crash_dates <= np.datetime64(after_end)))

        before_crashes = int(before_mask.sum())
        after_crashes = int(after_mask.sum())
        before_inj = int(crash_injured[before_mask].sum())
        after_inj = int(crash_injured[after_mask].sum())

        if before_crashes > 0:
            pct_change = ((after_crashes - before_crashes) / before_crashes) * 100
        elif after_crashes > 0:
            pct_change = 100.0
        else:
            pct_change = 0.0

        results.append({
            'referencenumber': row['referencenumber'],
            'requesttype': row['requesttype'],
            'mainstreet': row['mainstreet'],
            'crossstreet1': row['crossstreet1'],
            'daterequested': row.get('daterequested', None),
            'install_date': install_dt,
            'window_months': round(window_months, 1),
            'before_crashes': before_crashes,
            'after_crashes': after_crashes,
            'crash_change': after_crashes - before_crashes,
            'pct_change': round(pct_change, 1),
            'before_injuries': before_inj,
            'after_injuries': after_inj,
            'latitude': lat,
            'longitude': lon,
        })

    rdf = pd.DataFrame(results)
    decreased = (rdf['crash_change'] < 0).sum()
    increased = (rdf['crash_change'] > 0).sum()
    print(f"    Installed locations: {len(rdf)} "
          f"(crashes decreased: {decreased}, increased: {increased}, "
          f"no change: {len(rdf) - decreased - increased})")
    print(f"    Aggregate: {rdf['before_crashes'].sum()} before -> "
          f"{rdf['after_crashes'].sum()} after | "
          f"Injuries: {rdf['before_injuries'].sum()} -> {rdf['after_injuries'].sum()}")
    return rdf


def map_consolidated(signal_prox, srts_prox, cb5_crashes, data=None):
    """Consolidated map — print-ready editorial style.

    Base: CartoDB Positron No Labels (clean, minimal, print-friendly).
    Crash data: dot density (one dot per crash) instead of heatmap.
    Layers: denied/approved markers, DOT effectiveness (before-after),
    top-15 spotlight.
    """
    print("  Generating consolidated map (print style)...")

    # --- Base map: no-label tiles for print clarity ---
    m = folium.Map(
        location=CB5_CENTER, zoom_start=CB5_ZOOM,
        tiles=None,
        control_scale=True,
    )
    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png',
        attr='&copy; OpenStreetMap contributors &copy; CARTO',
        name='Base Map',
    ).add_to(m)

    _add_cb5_boundary(m)

    _popup_style = "font-family:'Times New Roman',Georgia,serif;font-size:12px;line-height:1.5;"
    _hr = "<hr style='border:0;border-top:1px solid #ccc;margin:4px 0;'>"

    def _fmt_date(val):
        """Format a date value to 'Mon DD, YYYY' or return 'N/A'."""
        if pd.isna(val):
            return 'N/A'
        try:
            return pd.to_datetime(val).strftime('%b %d, %Y')
        except Exception:
            return str(val)[:10]

    # --- Enrich signal_prox with dates from full CB5 studies data ---
    # The geocode cache may lack daterequested/statusdate (older caches).
    # Merge them from the full studies data so popups and exports have dates.
    if data is not None and 'cb5_no_aps' in data:
        _date_source = data['cb5_no_aps'][['referencenumber', 'daterequested', 'statusdate']].drop_duplicates('referencenumber')
        for col in ['daterequested', 'statusdate']:
            if col not in signal_prox.columns or signal_prox[col].isna().all():
                signal_prox = signal_prox.drop(columns=[col], errors='ignore')
                signal_prox = signal_prox.merge(
                    _date_source[['referencenumber', col]], on='referencenumber', how='left')

    # --- Precompute layer subsets for names and CSV export ---
    _sig_denied = signal_prox[signal_prox['outcome'] == 'denied']
    _sig_approved = signal_prox[signal_prox['outcome'] == 'approved']
    _srts_denied = srts_prox[srts_prox['outcome'] == 'denied']
    _srts_approved = srts_prox[srts_prox['outcome'] == 'approved']
    n_sig_denied = _sig_denied['latitude'].notna().sum()
    n_sig_approved = _sig_approved['latitude'].notna().sum()
    n_srts_denied = _srts_denied['latitude'].notna().sum()
    n_srts_approved = _srts_approved['latitude'].notna().sum()

    # --- Layer 1: Crash Dot Density (replaces heatmap) ---
    crash_with_coords = cb5_crashes[cb5_crashes['latitude'].notna()].copy()
    crash_dots = folium.FeatureGroup(
        name=f'Injury Crashes (n={len(crash_with_coords):,}, 2020–2025)', show=True)
    for _, crow in crash_with_coords.iterrows():
        injured = int(crow.get('number_of_persons_injured', 0))
        killed = int(crow.get('number_of_persons_killed', 0))
        # Size by severity: fatal=4, injury=2, other=1.5
        if killed > 0:
            r, color, opacity = 3.5, '#1a1a1a', 0.8
        elif injured > 0:
            r, color, opacity = 1.8, '#888888', 0.35
        else:
            r, color, opacity = 1.2, '#aaaaaa', 0.2

        # --- Crash popup/tooltip ---
        c_date = _fmt_date(crow.get('crash_date'))
        c_time = str(crow.get('crash_time', '')).strip()
        _on_raw = crow.get('on_street_name')
        _off_raw = crow.get('off_street_name')
        _cross_raw = crow.get('cross_street_name')
        c_on = '' if pd.isna(_on_raw) else str(_on_raw).strip()
        c_off = '' if pd.isna(_off_raw) else str(_off_raw).strip()
        c_cross = '' if pd.isna(_cross_raw) else str(_cross_raw).strip()
        if c_on and c_off:
            c_loc = f"{c_on} & {c_off}"
        elif c_on or c_off:
            c_loc = c_on or c_off
        elif c_cross:
            c_loc = f"Near {c_cross}"
        else:
            c_loc = 'Location on map'
        c_factor = str(crow.get('contributing_factor_vehicle_1', '') or '').strip()
        c_veh1 = str(crow.get('vehicle_type_code1', '') or '').strip()
        ped_inj = int(crow.get('number_of_pedestrians_injured', 0))
        ped_k = int(crow.get('number_of_pedestrians_killed', 0))
        cyc_inj = int(crow.get('number_of_cyclist_injured', 0))
        cyc_k = int(crow.get('number_of_cyclist_killed', 0))
        mot_inj = int(crow.get('number_of_motorist_injured', 0))
        mot_k = int(crow.get('number_of_motorist_killed', 0))

        severity_tag = ('<span style="color:#B44040;font-weight:bold;">FATAL</span>'
                        if killed > 0 else
                        '<span style="color:#cc8400;font-weight:bold;">INJURY</span>'
                        if injured > 0 else 'Property damage')

        crash_popup = (
            f"<div style=\"{_popup_style}\">"
            f"<b>{c_loc}</b><br>"
            f"{c_date} at {c_time}<br>"
            f"Severity: {severity_tag}"
            f"{_hr}"
            f"Pedestrians: {ped_inj} injured, {ped_k} killed<br>"
            f"Cyclists: {cyc_inj} injured, {cyc_k} killed<br>"
            f"Motorists: {mot_inj} injured, {mot_k} killed"
            f"{_hr}"
            f"Factor: {c_factor or 'N/A'}<br>"
            f"Vehicle: {c_veh1 or 'N/A'}<br>"
            f"<span style='color:#666;font-size:10px;'>Collision ID: {crow.get('collision_id', 'N/A')}</span>"
            f"</div>"
        )
        _sev = 'Fatal' if killed > 0 else f'{injured} injured' if injured > 0 else 'Crash'
        crash_tooltip = f"{c_loc} — {_sev}, {c_date}"

        folium.CircleMarker(
            [crow['latitude'], crow['longitude']], radius=r,
            color=color, fill=True, fill_color=color,
            fill_opacity=opacity, weight=0.3,
            popup=folium.Popup(crash_popup, max_width=320),
            tooltip=crash_tooltip,
        ).add_to(crash_dots)
    crash_dots.add_to(m)

    # --- Helper: build signal study popup ---
    def _signal_popup(row, outcome_label, outcome_color):
        ref = row.get('referencenumber', 'N/A')
        req_date = _fmt_date(row.get('daterequested'))
        status_date = _fmt_date(row.get('statusdate'))
        req_type = row.get('requesttype', 'N/A')
        status_desc = str(row.get('statusdescription', '') or '').strip()
        findings = str(row.get('findings', '') or '').strip()
        fatalities = int(row.get('fatalities_150m', 0))
        ped_inj = int(row.get('ped_injuries_150m', 0))
        school = str(row.get('schoolname', '') or '').strip()
        vz = 'Yes' if row.get('visionzero') == 'Yes' else ''
        loc = f"{row.get('mainstreet', '')} & {row.get('crossstreet1', '')}"

        extras = ''
        if school:
            extras += f"School: {school}<br>"
        if vz:
            extras += f"Vision Zero priority: Yes<br>"
        if findings:
            extras += f"Findings: {findings}<br>"

        return (
            f"<div style=\"{_popup_style}\">"
            f"<b>{loc}</b><br>"
            f"<span style='color:#666;font-size:10px;'>{ref}</span><br>"
            f"Type: {req_type}<br>"
            f"Outcome: <span style='color:{outcome_color};font-weight:bold;'>{outcome_label}</span>"
            f"{_hr}"
            f"Requested: {req_date}<br>"
            f"Status date: {status_date}<br>"
            f"Status: {status_desc}"
            f"{_hr}"
            f"{extras}"
            f"<b>Within 150m (2020–2025):</b><br>"
            f"Crashes: {int(row.get('crashes_150m', 0))}<br>"
            f"Injuries: {int(row.get('injuries_150m', 0))}<br>"
            f"Ped. injuries: {ped_inj}<br>"
            f"Fatalities: {fatalities}"
            f"</div>"
        )

    # --- Layer 2: Denied Signal Studies ---
    denied_signals = folium.FeatureGroup(
        name=f'Denied Signal Studies (n={n_sig_denied:,}, 2020–2025)', show=True)
    for _, row in signal_prox[signal_prox['outcome'] == 'denied'].iterrows():
        if pd.isna(row['latitude']):
            continue
        popup_html = _signal_popup(row, 'DENIED', COLORS['denied'])
        folium.CircleMarker(
            [row['latitude'], row['longitude']], radius=6,
            color='#333333', fill=True, fill_color=COLORS['denied'],
            fill_opacity=0.75, weight=1.5,
            popup=folium.Popup(popup_html, max_width=340),
            tooltip=f"{row.get('mainstreet', '')} & {row.get('crossstreet1', '')} — {row.get('requesttype', '')} (DENIED)"
        ).add_to(denied_signals)
    denied_signals.add_to(m)

    # --- Layer 3: Approved Signal Studies ---
    approved_signals = folium.FeatureGroup(
        name=f'Approved Signal Studies (n={n_sig_approved:,}, 2020–2025)', show=True)
    for _, row in signal_prox[signal_prox['outcome'] == 'approved'].iterrows():
        if pd.isna(row['latitude']):
            continue
        popup_html = _signal_popup(row, 'APPROVED', COLORS['approved'])
        folium.CircleMarker(
            [row['latitude'], row['longitude']], radius=6,
            color='#333333', fill=True, fill_color=COLORS['approved'],
            fill_opacity=0.75, weight=1.5,
            popup=folium.Popup(popup_html, max_width=340),
            tooltip=f"{row.get('mainstreet', '')} & {row.get('crossstreet1', '')} — {row.get('requesttype', '')} (APPROVED)"
        ).add_to(approved_signals)
    approved_signals.add_to(m)

    # --- Helper: build SRTS popup ---
    def _srts_popup(row, outcome_label, outcome_color):
        on_st = row.get('onstreet', '')
        from_st = row.get('fromstreet', '')
        to_st = row.get('tostreet', '')
        req_date = _fmt_date(row.get('requestdate'))
        closed_date = _fmt_date(row.get('closeddate'))
        proj_status = str(row.get('projectstatus', '') or '').strip()
        denial = str(row.get('denialreason', '') or '').strip()
        install_date = _fmt_date(row.get('installationdate'))
        proj_code = str(row.get('projectcode', '') or '').strip()
        fatalities = int(row.get('fatalities_150m', 0))
        ped_inj = int(row.get('ped_injuries_150m', 0))
        direction = str(row.get('trafficdirectiondesc', '') or '').strip()

        extras = ''
        if denial:
            extras += f"Denial reason: {denial}<br>"
        if install_date != 'N/A':
            extras += f"Installed: {install_date}<br>"
        if direction:
            extras += f"Traffic: {direction}<br>"

        return (
            f"<div style=\"{_popup_style}\">"
            f"<b>{on_st}</b> ({from_st} to {to_st})<br>"
            f"<span style='color:#666;font-size:10px;'>{proj_code}</span><br>"
            f"Outcome: <span style='color:{outcome_color};font-weight:bold;'>{outcome_label}</span>"
            f"{_hr}"
            f"Requested: {req_date}<br>"
            f"Decision date: {closed_date}<br>"
            f"Project status: {proj_status}"
            f"{_hr}"
            f"{extras}"
            f"<b>Within 150m (2020–2025):</b><br>"
            f"Crashes: {int(row.get('crashes_150m', 0))}<br>"
            f"Injuries: {int(row.get('injuries_150m', 0))}<br>"
            f"Ped. injuries: {ped_inj}<br>"
            f"Fatalities: {fatalities}"
            f"</div>"
        )

    # --- Layer 4: Denied Speed Bumps ---
    denied_srts = folium.FeatureGroup(
        name=f'Denied Speed Bumps (n={n_srts_denied:,}, 2020–2025)', show=True)
    for _, row in srts_prox[srts_prox['outcome'] == 'denied'].iterrows():
        if pd.isna(row['latitude']):
            continue
        popup_html = _srts_popup(row, 'DENIED', COLORS['denied'])
        folium.CircleMarker(
            [row['latitude'], row['longitude']], radius=4,
            color='#333333', fill=True, fill_color=COLORS['denied'],
            fill_opacity=0.6, weight=1,
            popup=folium.Popup(popup_html, max_width=340),
            tooltip=f"{row.get('onstreet', '')} ({row.get('fromstreet', '')} to {row.get('tostreet', '')}) — DENIED"
        ).add_to(denied_srts)
    denied_srts.add_to(m)

    # --- Layer 5: Approved Speed Bumps ---
    approved_srts = folium.FeatureGroup(
        name=f'Approved Speed Bumps (n={n_srts_approved:,}, 2020–2025)', show=True)
    for _, row in srts_prox[srts_prox['outcome'] == 'approved'].iterrows():
        if pd.isna(row['latitude']):
            continue
        popup_html = _srts_popup(row, 'APPROVED', COLORS['approved'])
        folium.CircleMarker(
            [row['latitude'], row['longitude']], radius=4,
            color='#333333', fill=True, fill_color=COLORS['approved'],
            fill_opacity=0.6, weight=1,
            popup=folium.Popup(popup_html, max_width=340),
            tooltip=f"{row.get('onstreet', '')} ({row.get('fromstreet', '')} to {row.get('tostreet', '')}) — APPROVED"
        ).add_to(approved_srts)
    approved_srts.add_to(m)

    # --- Layer 6: DOT Effectiveness — before-after for installed locations ---
    before_after_df = None
    if data is not None:
        before_after_df = _compute_before_after(data)
        effectiveness_fg = folium.FeatureGroup(
            name=f'DOT Effectiveness (n={len(before_after_df)}, Installed, 2020–2025)', show=False)

        for _, ba in before_after_df.iterrows():
            change = ba['crash_change']
            pct = ba['pct_change']

            # Color by outcome: green = decreased, gray = no change, amber = increased
            if change < 0:
                fill_color = '#2d7d46'  # strong green — crashes went down
                outline = '#1a5c2e'
                label = f"{abs(int(pct))}% fewer crashes"
            elif change == 0:
                fill_color = '#777777'  # neutral gray
                outline = '#555555'
                label = "No change"
            else:
                fill_color = '#cc8400'  # amber — crashes went up
                outline = '#996300'
                label = f"{int(pct)}% more crashes"

            install_str = ba['install_date'].strftime('%b %d, %Y')
            ref = ba.get('referencenumber', 'N/A')
            req_date = _fmt_date(ba.get('daterequested'))
            inj_change = ba['after_injuries'] - ba['before_injuries']
            inj_pct = (inj_change / ba['before_injuries'] * 100) if ba['before_injuries'] > 0 else 0
            inj_label = (f"{abs(int(inj_pct))}% fewer" if inj_change < 0
                         else f"{int(inj_pct)}% more" if inj_change > 0
                         else "No change")
            popup_html = (
                f"<div style=\"{_popup_style}\">"
                f"<b>{ba['mainstreet']} & {ba['crossstreet1']}</b><br>"
                f"<span style='color:#666;font-size:10px;'>{ref}</span><br>"
                f"Type: {ba['requesttype']}<br>"
                f"Requested: {req_date}<br>"
                f"Installed: {install_str}"
                f"{_hr}"
                f"<b>Before-After Analysis</b> ({ba['window_months']:.0f}-mo. windows, 150m):<br>"
                f"Crashes: {ba['before_crashes']} &rarr; {ba['after_crashes']} "
                f"(<b style='color:{fill_color};'>{label}</b>)<br>"
                f"Injuries: {ba['before_injuries']} &rarr; {ba['after_injuries']} ({inj_label})"
                f"</div>"
            )

            # Marker size scaled by absolute crash volume (bigger = more data = more reliable)
            marker_r = max(7, min(14, 5 + ba['before_crashes']))

            folium.CircleMarker(
                [ba['latitude'], ba['longitude']], radius=marker_r,
                color=outline, fill=True, fill_color=fill_color,
                fill_opacity=0.8, weight=2,
                popup=folium.Popup(popup_html, max_width=320),
                tooltip=f"{ba['mainstreet']} & {ba['crossstreet1']} — {label}"
            ).add_to(effectiveness_fg)

        effectiveness_fg.add_to(m)

    # --- Layer 7: Top 15 Denied Signal Study Spotlight (default OFF) ---
    # Signal studies only — intersection-level precision. SRTS excluded due to
    # segment-based coordinates creating methodological issues with 150m overlap.
    sig_denied = signal_prox[
        (signal_prox['outcome'] == 'denied') & signal_prox['latitude'].notna()
    ].copy()
    sig_denied['location_name'] = sig_denied.apply(
        lambda r: _normalize_intersection(r['mainstreet'], r['crossstreet1']), axis=1)
    sig_denied['dataset'] = 'Signal Study'
    sig_denied['request_info'] = sig_denied['requesttype']

    common_cols = ['location_name', 'dataset', 'request_info', 'latitude', 'longitude',
                   'crashes_150m', 'injuries_150m', 'ped_injuries_150m', 'fatalities_150m']
    spotlight_data = sig_denied[common_cols].copy()
    # De-duplicate: name-based then spatial
    spotlight_data = spotlight_data.sort_values('crashes_150m', ascending=False).drop_duplicates(
        subset=['location_name'], keep='first')
    spotlight_data = _spatial_dedup(spotlight_data, radius_m=150)
    top15 = spotlight_data.nlargest(15, 'crashes_150m')

    spotlight_fg = folium.FeatureGroup(name='Top 15 Denied Spotlight (2020–2025)', show=False)
    for rank, (_, row) in enumerate(top15.iterrows(), 1):
        # 150m radius circle
        folium.Circle(
            [row['latitude'], row['longitude']],
            radius=PROXIMITY_RADIUS_M,
            color=COLORS['denied'], fill=True, fill_color=COLORS['denied'],
            fill_opacity=0.08, weight=1.5, dash_array='5 3',
            interactive=False,
        ).add_to(spotlight_fg)

        popup_html = (
            f"<div style=\"{_popup_style}\">"
            f"<b>#{rank}: {row['location_name']}</b><br>"
            f"Dataset: {row['dataset']}<br>"
            f"Request: {row['request_info']}"
            f"{_hr}"
            f"<b>Within 150m:</b><br>"
            f"Crashes: {int(row['crashes_150m'])}<br>"
            f"Injuries: {int(row['injuries_150m'])}<br>"
            f"Ped. injuries: {int(row['ped_injuries_150m'])}<br>"
            f"Fatalities: {int(row['fatalities_150m'])}"
            f"</div>"
        )
        folium.CircleMarker(
            [row['latitude'], row['longitude']], radius=9,
            color='#333333', fill=True, fill_color=COLORS['denied'],
            fill_opacity=0.85, weight=2,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"#{rank}: {row['location_name']} ({int(row['crashes_150m'])} crashes)"
        ).add_to(spotlight_fg)

        # Rank label
        folium.Marker(
            [row['latitude'], row['longitude']],
            icon=folium.DivIcon(
                html=(f"<div style=\"font-family:'Times New Roman',Georgia,serif;"
                      f"font-size:10px;font-weight:bold;color:white;"
                      f"text-align:center;margin-top:-5px;\">{rank}</div>"),
                icon_size=(20, 20), icon_anchor=(10, 10))
        ).add_to(spotlight_fg)

    spotlight_fg.add_to(m)

    # --- Legend (print-ready, no heatmap entry) ---
    legend_items = [
        (COLORS['denied'], 'Denied request'),
        (COLORS['approved'], 'Approved request'),
        ('#888888', 'Injury crash (dot = 1 crash)'),
        ('#1a1a1a', 'Fatal crash'),
    ]
    if before_after_df is not None:
        legend_items.extend([
            ('#2d7d46', 'Installed \u2014 crashes decreased'),
            ('#cc8400', 'Installed \u2014 crashes increased'),
        ])
    legend_html = _make_legend_html(legend_items)
    m.get_root().html.add_child(folium.Element(legend_html))

    # --- CSS + dynamic title ---
    _inject_map_css(m)
    _add_dynamic_title(m)

    # --- Layer control ---
    folium.LayerControl(collapsed=False).add_to(m)

    m.save(f'{OUTPUT_DIR}/map_01_crash_denial_overlay.html')
    print("    Consolidated map saved to map_01_crash_denial_overlay.html")

    # --- Export layer data as CSV spreadsheets ---
    print("    Exporting map layer spreadsheets...")

    # Layer 1: Crashes
    crash_cols = ['crash_date', 'crash_time', 'on_street_name', 'off_street_name',
                  'number_of_persons_injured', 'number_of_persons_killed',
                  'number_of_pedestrians_injured', 'number_of_pedestrians_killed',
                  'number_of_cyclist_injured', 'number_of_cyclist_killed',
                  'number_of_motorist_injured', 'number_of_motorist_killed',
                  'contributing_factor_vehicle_1', 'vehicle_type_code1',
                  'collision_id', 'latitude', 'longitude']
    _crash_export = crash_with_coords[[c for c in crash_cols if c in crash_with_coords.columns]].copy()
    _crash_export['Source Dataset'] = 'Motor Vehicle Collisions [h9gi-nx95]'
    _crash_export.to_csv(f'{OUTPUT_DIR}/map_layer_crashes.csv', index=False)

    # Layer 2-3: Signal Studies (denied + approved)
    # Enrich with fields from original data not carried through geocode cache
    _sig_full = data['cb5_no_aps'] if data is not None else pd.DataFrame()
    _sig_enrich_cols = ['referencenumber', 'daterequested', 'statusdate', 'findings',
                        'schoolname', 'visionzero']
    _sig_enrich = _sig_full[[c for c in _sig_enrich_cols if c in _sig_full.columns]].drop_duplicates('referencenumber')
    sig_cols = ['referencenumber', 'mainstreet', 'crossstreet1', 'requesttype',
                'outcome', 'daterequested', 'statusdate', 'statusdescription',
                'findings', 'schoolname', 'visionzero',
                'crashes_150m', 'injuries_150m', 'ped_injuries_150m', 'fatalities_150m',
                'latitude', 'longitude']
    for outcome_label, subset in [('denied', _sig_denied), ('approved', _sig_approved)]:
        _exp = subset[subset['latitude'].notna()].copy()
        if len(_sig_enrich) > 0:
            _exp = _exp.merge(_sig_enrich, on='referencenumber', how='left', suffixes=('', '_orig'))
        _exp = _exp[[c for c in sig_cols if c in _exp.columns]]
        _exp['Source File'] = 'data_cb5_signal_studies.csv'
        _exp.to_csv(f'{OUTPUT_DIR}/map_layer_{outcome_label}_signals.csv', index=False)

    # Layer 4-5: Speed Bumps (denied + approved)
    srts_cols = ['projectcode', 'onstreet', 'fromstreet', 'tostreet',
                 'outcome', 'requestdate', 'closeddate', 'projectstatus', 'denialreason',
                 'installationdate', 'trafficdirectiondesc',
                 'crashes_150m', 'injuries_150m', 'ped_injuries_150m', 'fatalities_150m',
                 'latitude', 'longitude']
    for outcome_label, subset in [('denied', _srts_denied), ('approved', _srts_approved)]:
        _exp = subset[[c for c in srts_cols if c in subset.columns]].copy()
        _exp = _exp[_exp['latitude'].notna()]
        _exp['Source File'] = 'srts_citywide.csv'
        _exp.to_csv(f'{OUTPUT_DIR}/map_layer_{outcome_label}_speed_bumps.csv', index=False)

    # Layer 7: Top 15 Spotlight
    _top15_export = top15.copy()
    _top15_export['Source File'] = 'data_cb5_signal_studies.csv'
    _top15_export.to_csv(f'{OUTPUT_DIR}/map_layer_top15_denied.csv', index=False)

    print(f"      map_layer_crashes.csv ({len(_crash_export):,} rows)")
    print(f"      map_layer_denied_signals.csv ({n_sig_denied:,} rows)")
    print(f"      map_layer_approved_signals.csv ({n_sig_approved:,} rows)")
    print(f"      map_layer_denied_speed_bumps.csv ({n_srts_denied:,} rows)")
    print(f"      map_layer_approved_speed_bumps.csv ({n_srts_approved:,} rows)")
    print(f"      map_layer_top15_denied.csv (15 rows)")

    return before_after_df


# ============================================================
# Step 4: Static Charts (Matplotlib)
# ============================================================

def chart_09_crash_proximity(signal_prox, srts_prox):
    """Chart 09: Crash Proximity Comparison — denied vs approved."""
    print("  Generating Chart 09: Crash Proximity Analysis...")

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    metrics = ['crashes_150m', 'injuries_150m', 'ped_injuries_150m']
    metric_labels = ['Crashes', 'Injuries', 'Ped. Injuries']

    for ax_idx, (df, title_prefix) in enumerate([
        (signal_prox, 'QCB5 Signal Studies'),
        (srts_prox, 'QCB5 Speed Bumps')
    ]):
        # Only count rows with coordinates — non-geocoded rows have no proximity data
        geocoded = df[df['latitude'].notna()]
        denied = geocoded[geocoded['outcome'] == 'denied']
        approved = geocoded[geocoded['outcome'] == 'approved']

        x = np.arange(len(metrics))
        width = 0.35

        denied_medians = [denied[m].median() for m in metrics]
        approved_medians = [approved[m].median() for m in metrics]

        bars1 = axes[ax_idx].bar(x - width/2, denied_medians, width,
                                  label=f'Denied (n={len(denied)})',
                                  color=COLORS['denied'], edgecolor='black', zorder=3)
        bars2 = axes[ax_idx].bar(x + width/2, approved_medians, width,
                                  label=f'Approved (n={len(approved)})',
                                  color=COLORS['approved'], edgecolor='black', zorder=3)

        for bars in [bars1, bars2]:
            for bar in bars:
                val = bar.get_height()
                axes[ax_idx].text(bar.get_x() + bar.get_width()/2, val + 0.2,
                                  f'{val:.1f}', ha='center', va='bottom',
                                  fontsize=9, fontweight='bold')

        axes[ax_idx].set_xticks(x)
        axes[ax_idx].set_xticklabels(metric_labels, fontsize=10)
        axes[ax_idx].set_ylabel('Median Count within 150m', fontweight='bold')
        axes[ax_idx].set_title(f'{title_prefix}\n(n={len(denied)+len(approved):,}, Median Crash Metrics, 2020–2025)',
                               fontweight='bold', fontsize=12)
        axes[ax_idx].legend(loc='upper right')
        axes[ax_idx].xaxis.grid(False)

        # Statistical test for crashes_150m — placed below legend
        denied_crashes = denied['crashes_150m'].dropna()
        approved_crashes = approved['crashes_150m'].dropna()
        if len(denied_crashes) > 0 and len(approved_crashes) > 0:
            U, p = _mann_whitney_u(denied_crashes, approved_crashes)
            sig_text = f'p={p:.4f}' if p >= 0.0001 else 'p<0.0001'
            if p < 0.05:
                sig_text += ' *'
            axes[ax_idx].annotate(
                f'Mann-Whitney U ({sig_text})',
                xy=(0.98, 0.82), xycoords='axes fraction',
                ha='right', fontsize=9, style='italic',
                bbox=dict(boxstyle='round', facecolor='lightyellow', edgecolor='gray', alpha=0.9)
            )

    fig.suptitle('QCB5 Crash Proximity: Denied vs Approved Locations\n(2020–2025)',
                 fontweight='bold', fontsize=14, y=1.02)
    fig.text(0.01, -0.03,
             f'Source: NYC Open Data — 150m radius (~1.5 blocks, Vision Zero standard)\n'
             f'Crash data: Queens injury crashes [2020–2025], Motor Vehicle Collisions [h9gi-nx95]',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_09_crash_proximity_analysis.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print("    Chart 09 saved.")


def _normalize_intersection(street_a, street_b):
    """Normalize intersection name by sorting streets alphabetically.

    Ensures 'Cooper Ave & Cypress Ave' == 'Cypress Ave & Cooper Ave'.
    """
    a = str(street_a).strip().title() if pd.notna(street_a) else ''
    b = str(street_b).strip().title() if pd.notna(street_b) else ''
    parts = sorted([a, b])
    return f'{parts[0]} & {parts[1]}'


def _spatial_dedup(df, radius_m=100):
    """Spatially de-duplicate locations: if two entries are within radius_m,
    keep only the one with the highest crash count.

    Uses greedy approach: sort descending, skip any row within radius of
    an already-selected row.
    """
    if len(df) == 0:
        return df
    sorted_df = df.sort_values('crashes_150m', ascending=False).reset_index(drop=True)
    selected_idx = []
    selected_coords = []

    for i, row in sorted_df.iterrows():
        lat, lon = row['latitude'], row['longitude']
        too_close = False
        for slat, slon in selected_coords:
            # Approximate distance in meters
            dlat = (lat - slat) * 111_320
            dlon = (lon - slon) * 111_320 * math.cos(math.radians(lat))
            dist = math.sqrt(dlat**2 + dlon**2)
            if dist < radius_m:
                too_close = True
                break
        if not too_close:
            selected_idx.append(i)
            selected_coords.append((lat, lon))

    return sorted_df.loc[selected_idx].reset_index(drop=True)


def chart_09b_top_denied_ranking(signal_prox):
    """Chart 09b: Top 15 Denied Signal Study Intersections by Crash Severity.

    Signal studies only — SRTS excluded because segment-based coordinates
    (no cross street) create methodological issues with 150m radius overlap.
    SRTS crash proximity is shown on the map where spatial context is clear.
    """
    print("  Generating Chart 09b: Denied Signal Study Crash Ranking...")

    # Signal studies only — intersection-level precision with geocoded coordinates
    sig_denied = signal_prox[
        (signal_prox['outcome'] == 'denied') & signal_prox['latitude'].notna()
    ].copy()
    sig_denied['location_name'] = sig_denied.apply(
        lambda r: _normalize_intersection(r['mainstreet'], r['crossstreet1']), axis=1)

    common_cols = ['location_name', 'latitude', 'longitude',
                   'crashes_150m', 'injuries_150m', 'ped_injuries_150m', 'fatalities_150m']
    denied = sig_denied[common_cols].copy()

    # De-duplicate: name-based then spatial
    deduped = denied.sort_values('crashes_150m', ascending=False).drop_duplicates(
        subset=['location_name'], keep='first')
    deduped = _spatial_dedup(deduped, radius_m=150)
    n_unique = len(deduped)

    top15 = deduped.nlargest(15, 'crashes_150m').reset_index(drop=True)
    top15['other_injuries'] = (top15['injuries_150m'] - top15['ped_injuries_150m']).clip(lower=0)

    # Abbreviate street names for readability
    def _abbrev_street(name):
        return (name
                .replace(' Avenue', ' Ave')
                .replace(' Street', ' St')
                .replace(' Road', ' Rd')
                .replace(' Boulevard', ' Blvd')
                .replace(' Turnpike', ' Tpke')
                .replace(' Place', ' Pl')
                .replace(' Lane', ' Ln')
                .replace(' Drive', ' Dr'))

    top15['label'] = top15['location_name'].apply(
        lambda n: _abbrev_street(n[:45]))

    fig, axes = plt.subplots(1, 2, figsize=(14, 8))

    # --- Left panel: Top 15 by crash count ---
    top15_rev = top15.iloc[::-1].reset_index(drop=True)
    y = np.arange(len(top15_rev))

    bars = axes[0].barh(y, top15_rev['crashes_150m'], color=COLORS['denied'],
                        edgecolor='black', zorder=3)
    for i, val in enumerate(top15_rev['crashes_150m'].astype(int)):
        axes[0].text(val + 0.5, i, str(val),
                     va='center', ha='left', fontsize=9, fontweight='bold')

    axes[0].set_yticks(y)
    axes[0].set_yticklabels(top15_rev['label'], fontsize=9)
    axes[0].set_xlabel('Crashes within 150m', fontweight='bold')
    axes[0].set_title('Top 15 by Crash Count', fontweight='bold', fontsize=12)
    axes[0].yaxis.grid(False)

    # --- Right panel: Top 15 by injury count (independently sorted) ---
    top15_inj = deduped.nlargest(15, 'injuries_150m').reset_index(drop=True)
    top15_inj['other_injuries'] = (top15_inj['injuries_150m'] - top15_inj['ped_injuries_150m']).clip(lower=0)
    top15_inj['label'] = top15_inj['location_name'].apply(
        lambda n: _abbrev_street(n[:45]))
    top15_inj_rev = top15_inj.iloc[::-1].reset_index(drop=True)
    y_inj = np.arange(len(top15_inj_rev))

    ped_vals = top15_inj_rev['ped_injuries_150m'].astype(int).values
    other_vals = top15_inj_rev['other_injuries'].astype(int).values

    from matplotlib.patches import Patch

    axes[1].barh(y_inj, ped_vals, color=COLORS['denied'],
                 edgecolor='black', linewidth=0.5, zorder=3, label='Pedestrian Injuries')
    axes[1].barh(y_inj, other_vals, left=ped_vals, color=COLORS['crash_alt'],
                 edgecolor='black', linewidth=0.5, zorder=3, label='Other Injuries')

    for i, (p, o) in enumerate(zip(ped_vals, other_vals)):
        total = p + o
        axes[1].text(total + 0.5, i, str(total),
                     va='center', ha='left', fontsize=9, fontweight='bold')

    axes[1].set_yticks(y_inj)
    axes[1].set_yticklabels(top15_inj_rev['label'], fontsize=9)
    axes[1].set_xlabel('Persons Injured within 150m', fontweight='bold')
    axes[1].set_title('Top 15 by Persons Injured', fontweight='bold', fontsize=12)
    axes[1].yaxis.grid(False)
    axes[1].legend(loc='lower right', fontsize=8, framealpha=0.9)

    fig.suptitle(f'QCB5 Top 15 Denied Signal Study Intersections by Nearby Crashes\n(150m Radius, n={n_unique:,} unique denied intersections, 2020–2025)',
                 fontweight='bold', fontsize=14, y=1.02)

    fig.text(0.01, -0.03,
             'Source: NYC Open Data — Signal Studies [w76s-c5u4], Motor Vehicle Collisions [h9gi-nx95]',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_09b_denied_locations_crash_ranking.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print("    Chart 09b saved.")


def chart_13_approval_vs_installation():
    """Chart 13: DOT Outcomes — Denied vs Approved."""
    print("  Generating Chart 13: DOT Outcomes...")

    # --- Signal Studies ---
    sig = pd.read_csv(f'{OUTPUT_DIR}/data_cb5_signal_studies.csv', low_memory=False)
    sig['outcome'] = sig['statusdescription'].apply(_classify_outcome)
    sig_resolved = sig[sig['outcome'].isin(['denied', 'approved'])]
    sig_no_aps = sig_resolved[sig_resolved['requesttype'] != 'Accessible Pedestrian Signal']

    sig_denied = (sig_no_aps['outcome'] == 'denied').sum()
    sig_approved = (sig_no_aps['outcome'] == 'approved').sum()

    # --- SRTS (full pipeline: cb=405 + cross-street exclusion + polygon filter) ---
    cb5_srts = _load_cb5_srts_full()
    srts_resolved = cb5_srts[cb5_srts['segmentstatusdescription'].isin(['Not Feasible', 'Feasible'])]
    srts_denied = (srts_resolved['segmentstatusdescription'] == 'Not Feasible').sum()
    srts_feasible = (srts_resolved['segmentstatusdescription'] == 'Feasible').sum()

    fig, axes = plt.subplots(1, 2, figsize=(13, 6))

    # Panel 1: Signal Studies
    categories = ['Denied', 'Approved']
    sig_vals = [sig_denied, sig_approved]
    sig_colors = [COLORS['denied'], COLORS['approved']]
    bars = axes[0].bar(categories, sig_vals, color=sig_colors, edgecolor='black', zorder=3)
    for bar, val in zip(bars, sig_vals):
        axes[0].text(bar.get_x() + bar.get_width()/2, val + 2,
                     str(val), ha='center', va='bottom', fontweight='bold', fontsize=11)
    sig_approval_rate = sig_approved / (sig_denied + sig_approved) * 100
    axes[0].set_title(f'QCB5 Signal Studies\n(Excl. APS, n={len(sig_no_aps):,}, 2020–2025)', fontweight='bold', fontsize=12)
    axes[0].set_ylabel('Number of Requests', fontweight='bold')
    axes[0].xaxis.grid(False)
    axes[0].annotate(
        f'Approval rate: {sig_approval_rate:.1f}%',
        xy=(0.98, 0.95), xycoords='axes fraction', ha='right', va='top',
        fontsize=10, bbox=dict(boxstyle='round', facecolor='lightyellow', edgecolor='gray', alpha=0.9))

    # Panel 2: SRTS
    srts_vals = [srts_denied, srts_feasible]
    bars2 = axes[1].bar(categories, srts_vals, color=sig_colors, edgecolor='black', zorder=3)
    for bar, val in zip(bars2, srts_vals):
        axes[1].text(bar.get_x() + bar.get_width()/2, val + 15,
                     str(val), ha='center', va='bottom', fontweight='bold', fontsize=11)
    srts_approval_rate = srts_feasible / (srts_denied + srts_feasible) * 100
    _rd = pd.to_datetime(cb5_srts['requestdate'], errors='coerce')
    srts_min_yr = int(_rd.dt.year.min())
    srts_max_yr = min(int(_rd.dt.year.max()), 2025)
    axes[1].set_title(f'QCB5 Speed Bumps\n(n={len(srts_resolved):,}, {srts_min_yr}–{srts_max_yr})', fontweight='bold', fontsize=12)
    axes[1].set_ylabel('Number of Requests', fontweight='bold')
    axes[1].xaxis.grid(False)
    axes[1].annotate(
        f'Approval rate: {srts_approval_rate:.1f}%',
        xy=(0.98, 0.95), xycoords='axes fraction', ha='right', va='top',
        fontsize=10, bbox=dict(boxstyle='round', facecolor='lightyellow', edgecolor='gray', alpha=0.9))

    fig.suptitle(f'QCB5 DOT Request Outcomes: Denied vs Approved',
                 fontweight='bold', fontsize=14, y=1.02)
    fig.text(0.01, -0.03,
             'Source: NYC Open Data — Signal Studies [w76s-c5u4], Speed Reducer Tracking System [9n6h-pt9g]',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_13_approval_vs_installation.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Save accompanying CSV
    table_13 = pd.DataFrame([
        {'Dataset': 'Signal Studies', 'Source File': 'data_cb5_signal_studies.csv',
         'Denied': sig_denied, 'Approved': sig_approved,
         'Approval Rate (%)': round(sig_approval_rate, 1)},
        {'Dataset': 'Speed Bumps', 'Source File': 'srts_citywide.csv',
         'Denied': srts_denied, 'Approved': srts_feasible,
         'Approval Rate (%)': round(srts_approval_rate, 1)},
    ])
    table_13.to_csv(f'{OUTPUT_DIR}/table_13_approval_vs_installation.csv', index=False)
    print("    Chart 13 saved.")


def chart_15_srts_funnel():
    """Chart 15: SRTS Approval Funnel — what happens after DOT approves a speed bump."""
    print("  Generating Chart 15: SRTS Approval Funnel...")

    # Full CB5 pipeline: cb=405 + cross-street exclusion + polygon filter
    cb5 = _load_cb5_srts_full()
    cb5['requestdate'] = pd.to_datetime(cb5['requestdate'], errors='coerce')
    feasible = cb5[cb5['segmentstatusdescription'] == 'Feasible'].copy()

    min_yr = int(feasible['requestdate'].dt.year.min())
    max_yr = min(int(feasible['requestdate'].dt.year.max()), 2025)

    feasible['install_dt'] = pd.to_datetime(feasible['installationdate'], errors='coerce')

    # Categorize outcomes (mutually exclusive, must sum to total)
    installed = feasible[
        feasible['install_dt'].notna() &
        ~feasible['projectstatus'].str.contains('Cancel|Reject|denied', case=False, na=False)
    ]
    cancelled = feasible[
        feasible['projectstatus'].str.contains('Cancel|Reject|denied', case=False, na=False)
    ]
    still_open = feasible[
        feasible['install_dt'].isna() &
        ~feasible['projectstatus'].str.contains('Cancel|Reject|denied|Closed', case=False, na=False)
    ]
    # "Closed" without install date and without Cancel/Reject — administrative closures
    closed_other = feasible[
        feasible['install_dt'].isna() &
        feasible['projectstatus'].str.contains('Closed', case=False, na=False) &
        ~feasible['projectstatus'].str.contains('Cancel|Reject|denied', case=False, na=False)
    ]

    n_total = len(feasible)
    n_installed = len(installed)
    n_cancelled = len(cancelled)
    n_waiting = len(still_open)
    n_closed = len(closed_other)

    # --- Two-panel layout ---
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), gridspec_kw={'width_ratios': [1, 2]})

    # Left panel: total approved as a single reference bar
    axes[0].bar(['Approved\nby DOT'], [n_total], color=COLORS['approved'],
                edgecolor='black', zorder=3, width=0.5)
    axes[0].text(0, n_total + 5, str(n_total), ha='center', va='bottom',
                 fontweight='bold', fontsize=14)
    axes[0].set_ylabel('Number of Requests', fontweight='bold')
    axes[0].set_title(f'Total Approved\n({min_yr}–{max_yr})', fontweight='bold', fontsize=12)
    axes[0].set_ylim(0, n_total * 1.15)
    axes[0].xaxis.grid(False)

    # Right panel: what happened to them (only include Closed if any exist)
    categories = ['Confirmed\nInstalled', 'Cancelled /\nRejected']
    values = [n_installed, n_cancelled]
    bar_colors = ['#2d7d46', '#cc8400']
    if n_closed > 0:
        categories.append('Closed\n(No Install)')
        values.append(n_closed)
        bar_colors.append('#b0b0b0')
    categories.append('Still\nWaiting')
    values.append(n_waiting)
    bar_colors.append('#888888')

    bars = axes[1].bar(categories, values, color=bar_colors, edgecolor='black', zorder=3, width=0.6)

    for bar, val in zip(bars, values):
        pct = val / n_total * 100
        pct_str = f'{pct:.1f}%' if pct < 1 else f'{pct:.0f}%'
        axes[1].text(bar.get_x() + bar.get_width()/2, val + 3,
                     f'{val}\n({pct_str})', ha='center', va='bottom',
                     fontweight='bold', fontsize=11)

    axes[1].set_ylabel('Number of Requests', fontweight='bold')
    axes[1].set_title(f'Outcome of {n_total} Approved Requests', fontweight='bold', fontsize=12)
    axes[1].set_ylim(0, max(values) * 1.25)
    axes[1].xaxis.grid(False)

    # Median wait annotation — position on the "Still Waiting" bar (last bar)
    still_open_dt = pd.to_datetime(still_open['requestdate'], errors='coerce')
    waiting_bar_idx = len(categories) - 1
    if len(still_open_dt.dropna()) > 0:
        median_years = (pd.Timestamp.now() - still_open_dt).dt.days.median() / 365.25
        axes[1].annotate(f'Median wait: {median_years:.1f} years',
                         xy=(waiting_bar_idx, n_waiting * 0.5), ha='center', fontsize=9,
                         style='italic', fontweight='bold',
                         bbox=dict(boxstyle='round', facecolor='lightyellow',
                                   edgecolor='gray', alpha=0.9))

    fig.suptitle(f'QCB5 DOT-Approved Speed Bumps: Post-Approval Outcomes\n(n={n_total:,}, {min_yr}–{max_yr})',
                 fontweight='bold', fontsize=14, y=1.02)
    fig.text(0.01, -0.03,
             'Source: NYC Open Data — Speed Reducer Tracking System [9n6h-pt9g] | "Feasible" = DOT engineering approval\n'
             'Cancelled/Rejected and Closed per DOT projectstatus field',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_15_srts_funnel.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Save accompanying CSV
    rows_15 = [
        {'Category': 'Total Approved (Feasible)', 'Count': n_total, 'Percent': 100.0},
        {'Category': 'Confirmed Installed', 'Count': n_installed, 'Percent': round(n_installed / n_total * 100, 1)},
        {'Category': 'Cancelled / Rejected', 'Count': n_cancelled, 'Percent': round(n_cancelled / n_total * 100, 1)},
    ]
    if n_closed > 0:
        rows_15.append({'Category': 'Closed (No Install)', 'Count': n_closed, 'Percent': round(n_closed / n_total * 100, 1)})
    rows_15.append({'Category': 'Still Waiting', 'Count': n_waiting, 'Percent': round(n_waiting / n_total * 100, 1)})
    table_15 = pd.DataFrame(rows_15)
    table_15['Source File'] = 'srts_citywide.csv'
    table_15.to_csv(f'{OUTPUT_DIR}/table_15_srts_funnel.csv', index=False)
    print("    Chart 15 saved.")


# ============================================================
# Step 5: Data Tables
# ============================================================

def save_data_tables(signal_prox, srts_prox):
    """Save CSV data tables for all Part 2 outputs."""
    print("  Saving data tables...")

    # Table 09: Per-location crash proximity (with reference numbers for traceability)
    sig_rows = signal_prox[signal_prox['latitude'].notna()].copy()
    sig_rows['location_name'] = (
        sig_rows['mainstreet'].fillna('') + ' & ' + sig_rows['crossstreet1'].fillna('')
    ).str.title()
    sig_rows['dataset'] = 'Signal Study'
    sig_rows['reference_id'] = sig_rows['referencenumber']
    sig_rows['request_year'] = sig_rows['year']
    sig_rows['request_type'] = sig_rows['requesttype']
    sig_rows['source_file'] = 'data_cb5_signal_studies.csv'

    srts_rows = srts_prox[srts_prox['latitude'].notna()].copy()
    srts_rows['location_name'] = srts_rows['onstreet'].fillna('').str.title()
    srts_rows['dataset'] = 'SRTS'
    srts_rows['reference_id'] = srts_rows['projectcode']
    srts_rows['request_year'] = srts_rows['year']
    srts_rows['request_type'] = 'Speed Bump'
    srts_rows['source_file'] = 'srts_citywide.csv'

    common_cols = ['reference_id', 'location_name', 'dataset', 'request_type', 'outcome',
                   'request_year', 'source_file', 'latitude', 'longitude',
                   'crashes_150m', 'injuries_150m', 'ped_injuries_150m', 'fatalities_150m']
    table_09 = pd.concat([
        sig_rows[[c for c in common_cols if c in sig_rows.columns]],
        srts_rows[[c for c in common_cols if c in srts_rows.columns]]
    ], ignore_index=True)
    table_09 = table_09.sort_values('crashes_150m', ascending=False)
    table_09 = table_09.rename(columns={'source_file': 'Source File'})
    table_09.to_csv(f'{OUTPUT_DIR}/table_09_crash_proximity_by_location.csv', index=False)

    # Table 09b: Aggregate comparison — denied vs approved
    rows = []
    for dataset_label, df in [('Signal Studies', signal_prox), ('SRTS', srts_prox)]:
        for outcome in ['denied', 'approved']:
            subset = df[(df['outcome'] == outcome) & df['crashes_150m'].notna()]
            if len(subset) == 0:
                continue
            rows.append({
                'Dataset': dataset_label,
                'Outcome': outcome,
                'N': len(subset),
                'Mean Crashes 150m': round(subset['crashes_150m'].mean(), 1),
                'Median Crashes 150m': round(subset['crashes_150m'].median(), 1),
                'Mean Injuries 150m': round(subset['injuries_150m'].mean(), 1),
                'Median Injuries 150m': round(subset['injuries_150m'].median(), 1),
                'Mean Ped Injuries 150m': round(subset['ped_injuries_150m'].mean(), 1),
                'Median Ped Injuries 150m': round(subset['ped_injuries_150m'].median(), 1),
            })

    table_09b = pd.DataFrame(rows)

    # Add p-values
    for dataset_label, df in [('Signal Studies', signal_prox), ('SRTS', srts_prox)]:
        denied = df[(df['outcome'] == 'denied') & df['crashes_150m'].notna()]['crashes_150m']
        approved = df[(df['outcome'] == 'approved') & df['crashes_150m'].notna()]['crashes_150m']
        if len(denied) > 0 and len(approved) > 0:
            _, p = _mann_whitney_u(denied, approved)
            mask = table_09b['Dataset'] == dataset_label
            table_09b.loc[mask, 'Mann-Whitney p-value (crashes)'] = round(p, 6)

    table_09b['Source Dataset'] = table_09b['Dataset'].apply(
        lambda d: 'data_cb5_signal_studies.csv' if d == 'Signal Studies'
        else 'srts_citywide.csv')
    table_09b.to_csv(f'{OUTPUT_DIR}/table_09b_aggregate_comparison.csv', index=False)

    # Table 09c: Top denied signal study intersections by crashes (ranked list for article)
    # Signal studies only — intersection-level precision. SRTS excluded due to
    # segment-based coordinates creating methodological issues with 150m overlap.
    sig_denied = signal_prox[
        (signal_prox['outcome'] == 'denied') & signal_prox['latitude'].notna()
    ].copy()
    sig_denied['location_name'] = sig_denied.apply(
        lambda r: _normalize_intersection(r['mainstreet'], r['crossstreet1']), axis=1)
    sig_denied['dataset'] = 'Signal Study'
    sig_denied['request_type'] = sig_denied.get('requesttype', 'N/A')
    sig_denied['reference_id'] = sig_denied['referencenumber']
    sig_denied['request_year'] = sig_denied['year']
    sig_denied['source_file'] = 'data_cb5_signal_studies.csv'

    common_cols_c = ['reference_id', 'location_name', 'dataset', 'request_type',
                     'request_year', 'source_file', 'latitude', 'longitude',
                     'crashes_150m', 'injuries_150m', 'ped_injuries_150m', 'fatalities_150m']
    combined = sig_denied[[c for c in common_cols_c if c in sig_denied.columns]].copy()
    # De-duplicate: name-based then spatial
    combined = combined.sort_values('crashes_150m', ascending=False).drop_duplicates(
        subset=['location_name'], keep='first')
    combined = _spatial_dedup(combined, radius_m=150)
    table_09c = combined.nlargest(25, 'crashes_150m').reset_index(drop=True)
    table_09c.index = table_09c.index + 1
    table_09c.index.name = 'Rank'
    table_09c = table_09c.rename(columns={'source_file': 'Source File'})
    table_09c.to_csv(f'{OUTPUT_DIR}/table_09c_top_denied_by_crashes.csv')

    print(f"    table_09: {len(table_09)} locations")
    print(f"    table_09b: aggregate comparison")
    print(f"    table_09c: top {len(table_09c)} denied locations")


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("CB5 SAFETY ANALYSIS - MAP & CORRELATION GENERATION (Part 2)")
    print("=" * 60)

    # Load data
    data = load_and_prepare_data()

    # Step 1: Geocode signal studies
    print("\nStep 1: Geocoding signal study intersections...")
    signal_geo = geocode_signal_studies(data)

    # Step 2: Proximity analysis
    print("\nStep 2: Proximity analysis (150m radius)...")
    signal_prox, srts_prox = run_proximity_analysis(
        signal_geo, data['cb5_srts'], data['cb5_crashes'])

    # Print summary stats
    for label, df in [('Signal Studies', signal_prox), ('SRTS', srts_prox)]:
        denied = df[df['outcome'] == 'denied']
        approved = df[df['outcome'] == 'approved']
        print(f"\n  {label}:")
        print(f"    Denied:   median {denied['crashes_150m'].median():.0f} crashes, "
              f"{denied['injuries_150m'].median():.0f} injuries within 150m (n={len(denied)})")
        print(f"    Approved: median {approved['crashes_150m'].median():.0f} crashes, "
              f"{approved['injuries_150m'].median():.0f} injuries within 150m (n={len(approved)})")
        U, p = _mann_whitney_u(denied['crashes_150m'].dropna(), approved['crashes_150m'].dropna())
        print(f"    Mann-Whitney U: p={p:.6f}" + (" *" if p < 0.05 else ""))

    # Step 3: Consolidated map (replaces former Maps 01-03)
    print("\nStep 3: Generating consolidated map...")
    before_after_df = map_consolidated(signal_prox, srts_prox, data['cb5_crashes'], data=data)
    print("  Note: map_02_*.html and map_03_*.html are no longer generated (can be deleted).")

    # Save before-after analysis table
    if before_after_df is not None and len(before_after_df) > 0:
        ba_out = before_after_df.copy()
        ba_out['install_date'] = ba_out['install_date'].dt.strftime('%Y-%m-%d')
        ba_out['Source File'] = 'data_cb5_signal_studies.csv'
        ba_out.to_csv(f'{OUTPUT_DIR}/table_before_after_installed.csv', index=False)
        print(f"  Before-after table saved ({len(ba_out)} installed locations).")

    # Step 4: Static charts
    print("\nStep 4: Generating charts...")
    chart_09_crash_proximity(signal_prox, srts_prox)
    chart_09b_top_denied_ranking(signal_prox)
    chart_13_approval_vs_installation()
    chart_15_srts_funnel()

    # Step 5: Data tables
    print("\nStep 5: Saving data tables...")
    save_data_tables(signal_prox, srts_prox)

    print("\n" + "=" * 60)
    print("All Part 2 outputs saved to output/")
    print("=" * 60)


if __name__ == "__main__":
    main()
