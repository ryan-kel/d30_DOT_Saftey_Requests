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
from folium.plugins import HeatMap
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
        <div id="map-dynamic-title" style="font-size:15px;font-weight:bold;">Safety Request Outcomes: Queens Community Board 5</div>
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
            var spotlight = layers['Top 15 Denied Spotlight'] || false;
            var signals = (layers['Denied Signal Studies'] || false) || (layers['Approved Signal Studies'] || false);
            var srts = (layers['Denied Speed Bumps'] || false) || (layers['Approved Speed Bumps'] || false);
            if (spotlight) {
                titleEl.textContent = 'Top 15 Denied Locations by Nearby Crash Count';
                subtitleEl.textContent = '150m Analysis Radius, Queens CB5';
            } else if (signals && srts) {
                titleEl.textContent = 'Safety Request Outcomes: Queens Community Board 5';
                subtitleEl.textContent = 'Signal Studies & Speed Bumps vs. Injury Crashes (2020\u20132025)';
            } else if (signals) {
                titleEl.textContent = 'Signal Study Outcomes: Queens CB5';
                subtitleEl.textContent = 'Traffic Signal & Stop Sign Requests vs. Crash Data';
            } else if (srts) {
                titleEl.textContent = 'Speed Bump Requests & Injury Crashes';
                subtitleEl.textContent = 'SRTS Program, Queens Community Board 5';
            } else {
                titleEl.textContent = 'Safety Infrastructure Data: Queens CB5';
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
    no_coords = df[~has_coords]
    with_coords = df[has_coords]

    inside = with_coords.apply(
        lambda r: prepared.contains(Point(r[lon_col], r[lat_col])), axis=1
    )
    filtered = pd.concat([with_coords[inside], no_coords], ignore_index=False)
    n_excluded = (~inside).sum()
    return filtered, n_excluded


def load_and_prepare_data():
    """Load all datasets and apply standard filtering."""
    print("Loading datasets...")

    signal_studies = pd.read_csv(f'{DATA_DIR}/signal_studies_citywide.csv', low_memory=False)
    srts = pd.read_csv(f'{DATA_DIR}/srts_citywide.csv', low_memory=False)
    crashes = pd.read_csv(f'{DATA_DIR}/crashes_queens_2020plus.csv', low_memory=False)
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

    # CB5 boundary exclusion filter (same as generate_charts.py)
    excluded_cross = ['51 ROAD', '51 STREET', '52 AVENUE', '52 DRIVE', '52 ROAD', '52 COURT',
                      '53 AVENUE', '53 DRIVE', '53 ROAD', 'CALAMUS AVENUE', 'QUEENS BOULEVARD']
    excluded_main = ['MAURICE AVENUE']

    def _is_outside_cb5(row):
        cross1 = str(row.get('crossstreet1', '')).upper().strip()
        cross2 = str(row.get('crossstreet2', '')).upper().strip()
        main = str(row.get('onstreet', '')).upper().strip()
        for e in excluded_cross:
            if e in cross1 or e in cross2:
                return True
        for e in excluded_main:
            if e in main:
                return True
        if 'WOODSIDE' in cross1 or 'WOODSIDE' in cross2 or 'WOODSIDE' in main:
            return True
        return False

    cb5_excluded = cb5_srts_raw.apply(_is_outside_cb5, axis=1)
    cb5_srts = cb5_srts_raw[~cb5_excluded].copy()
    cb5_srts['outcome'] = cb5_srts['segmentstatusdescription'].map({
        'Not Feasible': 'denied', 'Feasible': 'approved'
    })
    print(f"  CB5 SRTS: {len(cb5_srts_raw):,} raw -> {len(cb5_srts):,} after cross-street filter")

    # Polygon filter: SRTS
    cb5_srts['fromlatitude'] = pd.to_numeric(cb5_srts['fromlatitude'], errors='coerce')
    cb5_srts['fromlongitude'] = pd.to_numeric(cb5_srts['fromlongitude'], errors='coerce')
    cb5_srts, n_srts_excluded = _filter_points_in_cb5(
        cb5_srts, lat_col='fromlatitude', lon_col='fromlongitude')
    print(f"  CB5 SRTS: -> {len(cb5_srts):,} after polygon filter ({n_srts_excluded} excluded)")

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
                  'statusdescription', 'outcome', 'year', 'latitude', 'longitude',
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
        },
        tooltip='Queens Community Board 5',
    ).add_to(m)


def map_consolidated(signal_prox, srts_prox, cb5_crashes):
    """Consolidated map: all layers from former Maps 01-03 with dynamic title."""
    print("  Generating consolidated map...")

    m = folium.Map(location=CB5_CENTER, zoom_start=CB5_ZOOM,
                   tiles='cartodbpositron', control_scale=True)

    _add_cb5_boundary(m)

    _popup_style = "font-family:'Times New Roman',Georgia,serif;font-size:12px;line-height:1.5;"
    _hr = "<hr style='border:0;border-top:1px solid #ccc;margin:4px 0;'>"

    # --- Layer 1: Crash Heatmap (default on) ---
    heat_data = cb5_crashes[cb5_crashes['latitude'].notna()][
        ['latitude', 'longitude', 'number_of_persons_injured']
    ].values.tolist()

    heatmap_layer = folium.FeatureGroup(name='Crash Heatmap', show=True)
    HeatMap(heat_data, radius=12, blur=15, max_zoom=16,
            gradient=HEATMAP_GRADIENT).add_to(heatmap_layer)
    heatmap_layer.add_to(m)

    # --- Layer 2: Denied Signal Studies (default on) ---
    denied_signals = folium.FeatureGroup(name='Denied Signal Studies', show=True)
    for _, row in signal_prox[signal_prox['outcome'] == 'denied'].iterrows():
        if pd.isna(row['latitude']):
            continue
        popup_html = (
            f"<div style=\"{_popup_style}\">"
            f"<b>{row.get('mainstreet', '')} & {row.get('crossstreet1', '')}</b><br>"
            f"Type: {row.get('requesttype', 'N/A')}<br>"
            f"Outcome: <span style='color:{COLORS['denied']};font-weight:bold;'>DENIED</span>"
            f"{_hr}"
            f"Crashes within 150m: {int(row.get('crashes_150m', 0))}<br>"
            f"Injuries within 150m: {int(row.get('injuries_150m', 0))}<br>"
            f"Ped. injuries: {int(row.get('ped_injuries_150m', 0))}"
            f"</div>"
        )
        folium.CircleMarker(
            [row['latitude'], row['longitude']], radius=6,
            color=COLORS['denied'], fill=True, fill_color=COLORS['denied'],
            fill_opacity=0.7, weight=1.5, popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{row.get('mainstreet', '')} & {row.get('crossstreet1', '')} (DENIED)"
        ).add_to(denied_signals)
    denied_signals.add_to(m)

    # --- Layer 3: Approved Signal Studies (default on) ---
    approved_signals = folium.FeatureGroup(name='Approved Signal Studies', show=True)
    for _, row in signal_prox[signal_prox['outcome'] == 'approved'].iterrows():
        if pd.isna(row['latitude']):
            continue
        popup_html = (
            f"<div style=\"{_popup_style}\">"
            f"<b>{row.get('mainstreet', '')} & {row.get('crossstreet1', '')}</b><br>"
            f"Type: {row.get('requesttype', 'N/A')}<br>"
            f"Outcome: <span style='color:{COLORS['approved']};font-weight:bold;'>APPROVED</span>"
            f"{_hr}"
            f"Crashes within 150m: {int(row.get('crashes_150m', 0))}<br>"
            f"Injuries within 150m: {int(row.get('injuries_150m', 0))}"
            f"</div>"
        )
        folium.CircleMarker(
            [row['latitude'], row['longitude']], radius=6,
            color=COLORS['approved'], fill=True, fill_color=COLORS['approved'],
            fill_opacity=0.7, weight=1.5, popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{row.get('mainstreet', '')} & {row.get('crossstreet1', '')} (APPROVED)"
        ).add_to(approved_signals)
    approved_signals.add_to(m)

    # --- Layer 4: Denied Speed Bumps (default on) ---
    denied_srts = folium.FeatureGroup(name='Denied Speed Bumps', show=True)
    for _, row in srts_prox[srts_prox['outcome'] == 'denied'].iterrows():
        if pd.isna(row['latitude']):
            continue
        popup_html = (
            f"<div style=\"{_popup_style}\">"
            f"<b>{row.get('onstreet', '')}</b> ({row.get('fromstreet', '')} to {row.get('tostreet', '')})<br>"
            f"Outcome: <span style='color:{COLORS['denied']};font-weight:bold;'>DENIED</span><br>"
            f"Reason: {row.get('denialreason', 'N/A')}"
            f"{_hr}"
            f"Crashes within 150m: {int(row.get('crashes_150m', 0))}<br>"
            f"Injuries within 150m: {int(row.get('injuries_150m', 0))}"
            f"</div>"
        )
        folium.CircleMarker(
            [row['latitude'], row['longitude']], radius=4,
            color=COLORS['denied'], fill=True, fill_color=COLORS['denied'],
            fill_opacity=0.55, weight=1, popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{row.get('onstreet', '')} (DENIED)"
        ).add_to(denied_srts)
    denied_srts.add_to(m)

    # --- Layer 5: Approved Speed Bumps (default on) ---
    approved_srts = folium.FeatureGroup(name='Approved Speed Bumps', show=True)
    for _, row in srts_prox[srts_prox['outcome'] == 'approved'].iterrows():
        if pd.isna(row['latitude']):
            continue
        popup_html = (
            f"<div style=\"{_popup_style}\">"
            f"<b>{row.get('onstreet', '')}</b> ({row.get('fromstreet', '')} to {row.get('tostreet', '')})<br>"
            f"Outcome: <span style='color:{COLORS['approved']};font-weight:bold;'>APPROVED</span>"
            f"{_hr}"
            f"Crashes within 150m: {int(row.get('crashes_150m', 0))}<br>"
            f"Injuries within 150m: {int(row.get('injuries_150m', 0))}"
            f"</div>"
        )
        folium.CircleMarker(
            [row['latitude'], row['longitude']], radius=4,
            color=COLORS['approved'], fill=True, fill_color=COLORS['approved'],
            fill_opacity=0.55, weight=1, popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{row.get('onstreet', '')} (APPROVED)"
        ).add_to(approved_srts)
    approved_srts.add_to(m)

    # --- Layer 6: Crashes Near Top 15 (default OFF) ---
    # Build top-15 denied list
    sig_denied = signal_prox[
        (signal_prox['outcome'] == 'denied') & signal_prox['latitude'].notna()
    ].copy()
    sig_denied['location_name'] = sig_denied['mainstreet'].fillna('') + ' & ' + sig_denied['crossstreet1'].fillna('')
    sig_denied['dataset'] = 'Signal Study'
    sig_denied['request_info'] = sig_denied['requesttype']

    srts_denied = srts_prox[
        (srts_prox['outcome'] == 'denied') & srts_prox['latitude'].notna()
    ].copy()
    srts_denied['location_name'] = srts_denied['onstreet'].fillna('') + ' (' + srts_denied['fromstreet'].fillna('') + ' to ' + srts_denied['tostreet'].fillna('') + ')'
    srts_denied['dataset'] = 'SRTS'
    srts_denied['request_info'] = 'Speed Bump'

    common_cols = ['location_name', 'dataset', 'request_info', 'latitude', 'longitude',
                   'crashes_150m', 'injuries_150m', 'ped_injuries_150m', 'fatalities_150m']
    combined = pd.concat([
        sig_denied[common_cols],
        srts_denied[common_cols]
    ], ignore_index=True)
    top15 = combined.nlargest(15, 'crashes_150m')

    crash_fg = folium.FeatureGroup(name='Crashes Near Top 15', show=False)
    crash_lats = cb5_crashes['latitude'].values
    crash_lons = cb5_crashes['longitude'].values

    shown_crashes = set()
    for _, loc in top15.iterrows():
        dists = _haversine_vectorized(loc['latitude'], loc['longitude'], crash_lats, crash_lons)
        nearby_idx = np.where(dists <= PROXIMITY_RADIUS_M)[0]
        for ci in nearby_idx:
            if ci not in shown_crashes:
                shown_crashes.add(ci)
                crow = cb5_crashes.iloc[ci]
                folium.CircleMarker(
                    [crow['latitude'], crow['longitude']], radius=2,
                    color='#666666', fill=True, fill_color='#999999',
                    fill_opacity=0.35, weight=0.5,
                ).add_to(crash_fg)
    crash_fg.add_to(m)

    # --- Layer 7: Top 15 Denied Spotlight (default OFF) ---
    spotlight_fg = folium.FeatureGroup(name='Top 15 Denied Spotlight', show=False)
    for rank, (_, row) in enumerate(top15.iterrows(), 1):
        # 150m radius circle
        folium.Circle(
            [row['latitude'], row['longitude']],
            radius=PROXIMITY_RADIUS_M,
            color=COLORS['denied'], fill=True, fill_color=COLORS['denied'],
            fill_opacity=0.1, weight=1.5, dash_array='5 3',
        ).add_to(spotlight_fg)

        # Main marker
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
            color=COLORS['denied'], fill=True, fill_color=COLORS['denied'],
            fill_opacity=0.8, weight=1.5,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"#{rank}: {row['location_name']} ({int(row['crashes_150m'])} crashes)"
        ).add_to(spotlight_fg)

        # Rank label
        folium.Marker(
            [row['latitude'], row['longitude']],
            icon=folium.DivIcon(
                html=f"<div style=\"font-family:'Times New Roman',Georgia,serif;font-size:10px;font-weight:bold;color:white;text-align:center;margin-top:-5px;\">{rank}</div>",
                icon_size=(20, 20), icon_anchor=(10, 10))
        ).add_to(spotlight_fg)

    spotlight_fg.add_to(m)

    # --- Legend ---
    legend_html = _make_legend_html([
        (COLORS['denied'], 'Denied request'),
        (COLORS['approved'], 'Approved request'),
        (HEATMAP_GRADIENT[0.6], 'Crash heatmap (injury-weighted)'),
        ('#999999', 'Individual crash (Top 15 layer)'),
    ])
    m.get_root().html.add_child(folium.Element(legend_html))

    # --- CSS + dynamic title ---
    _inject_map_css(m)
    _add_dynamic_title(m)

    # --- Layer control ---
    folium.LayerControl(collapsed=False).add_to(m)

    m.save(f'{OUTPUT_DIR}/map_01_crash_denial_overlay.html')
    print("    Consolidated map saved to map_01_crash_denial_overlay.html")


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
        (signal_prox, 'Signal Studies'),
        (srts_prox, 'Speed Bumps (SRTS)')
    ]):
        denied = df[df['outcome'] == 'denied']
        approved = df[df['outcome'] == 'approved']

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
        axes[ax_idx].set_title(f'{title_prefix}\nMedian Crash Metrics Near Denied vs Approved',
                               fontweight='bold', fontsize=12)
        axes[ax_idx].legend(loc='upper right')
        axes[ax_idx].xaxis.grid(False)

        # Statistical test for crashes_150m
        denied_crashes = denied['crashes_150m'].dropna()
        approved_crashes = approved['crashes_150m'].dropna()
        if len(denied_crashes) > 0 and len(approved_crashes) > 0:
            U, p = _mann_whitney_u(denied_crashes, approved_crashes)
            sig_text = f'p={p:.4f}' if p >= 0.0001 else 'p<0.0001'
            if p < 0.05:
                sig_text += ' *'
            axes[ax_idx].annotate(
                f'Mann-Whitney U ({sig_text})',
                xy=(0.5, 0.02), xycoords='axes fraction',
                ha='center', fontsize=9, style='italic',
                bbox=dict(boxstyle='round', facecolor='lightyellow', edgecolor='gray', alpha=0.9)
            )

    fig.suptitle('Crash Proximity: Denied vs Approved Safety Request Locations',
                 fontweight='bold', fontsize=14, y=1.02)
    fig.text(0.01, -0.03,
             f'Source: NYC Open Data | 150m radius (~1.5 blocks, Vision Zero standard)\n'
             f'Crash data: Queens injury crashes 2020-2025 (h9gi-nx95)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_09_crash_proximity_analysis.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print("    Chart 09 saved.")


def chart_09b_top_denied_ranking(signal_prox, srts_prox):
    """Chart 09b: Top 15 Denied Locations Ranked by Crash Severity."""
    print("  Generating Chart 09b: Denied Locations Crash Ranking...")

    # Combine denied from both datasets
    sig_denied = signal_prox[
        (signal_prox['outcome'] == 'denied') & signal_prox['latitude'].notna()
    ].copy()
    sig_denied['location_name'] = (
        sig_denied['mainstreet'].fillna('') + ' & ' + sig_denied['crossstreet1'].fillna('')
    ).str.title()
    sig_denied['dataset'] = 'Signal'

    srts_denied = srts_prox[
        (srts_prox['outcome'] == 'denied') & srts_prox['latitude'].notna()
    ].copy()
    srts_denied['location_name'] = srts_denied['onstreet'].fillna('').str.title()
    srts_denied['dataset'] = 'SRTS'

    common_cols = ['location_name', 'dataset', 'crashes_150m', 'injuries_150m',
                   'ped_injuries_150m', 'fatalities_150m']
    combined = pd.concat([
        sig_denied[common_cols],
        srts_denied[common_cols]
    ], ignore_index=True)

    top15 = combined.nlargest(15, 'crashes_150m').reset_index(drop=True)

    # Truncate long names
    top15['label'] = top15.apply(
        lambda r: f"{r['location_name'][:35]} [{r['dataset']}]", axis=1)

    fig, ax = plt.subplots(figsize=(12, 8))

    y = np.arange(len(top15))
    bars = ax.barh(y, top15['crashes_150m'], color=COLORS['denied'],
                   edgecolor='black', zorder=3)

    # Overlay injury count as lighter bars
    ax.barh(y, top15['injuries_150m'], color=COLORS['crash_alt'],
            edgecolor='none', zorder=4, alpha=0.6, height=0.4)

    for i, row in top15.iterrows():
        ax.text(row['crashes_150m'] + 0.5, i,
                f"{int(row['crashes_150m'])} crashes / {int(row['injuries_150m'])} injuries",
                va='center', ha='left', fontsize=9)

    ax.set_yticks(y)
    ax.set_yticklabels(top15['label'], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel('Count within 150m', fontweight='bold')
    ax.set_title('Top 15 Denied Locations by Nearby Crash Count\n(CB5, 150m radius, 2020-2025)',
                 fontweight='bold', fontsize=12)
    ax.yaxis.grid(False)

    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(facecolor=COLORS['denied'], edgecolor='black', label='Total crashes'),
        Patch(facecolor=COLORS['crash_alt'], alpha=0.6, label='Injuries'),
    ], loc='lower right')

    fig.text(0.01, -0.03,
             'Source: NYC Open Data | Signal Studies (w76s-c5u4), SRTS (9n6h-pt9g), Crashes (h9gi-nx95)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_09b_denied_locations_crash_ranking.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print("    Chart 09b saved.")


# ============================================================
# Step 5: Data Tables
# ============================================================

def save_data_tables(signal_prox, srts_prox):
    """Save CSV data tables for all Part 2 outputs."""
    print("  Saving data tables...")

    # Table 09: Per-location crash proximity
    sig_rows = signal_prox[signal_prox['latitude'].notna()].copy()
    sig_rows['location_name'] = (
        sig_rows['mainstreet'].fillna('') + ' & ' + sig_rows['crossstreet1'].fillna('')
    ).str.title()
    sig_rows['dataset'] = 'Signal Study'

    srts_rows = srts_prox[srts_prox['latitude'].notna()].copy()
    srts_rows['location_name'] = srts_rows['onstreet'].fillna('').str.title()
    srts_rows['dataset'] = 'SRTS'

    common_cols = ['location_name', 'dataset', 'outcome', 'latitude', 'longitude',
                   'crashes_150m', 'injuries_150m', 'ped_injuries_150m', 'fatalities_150m']
    table_09 = pd.concat([
        sig_rows[[c for c in common_cols if c in sig_rows.columns]],
        srts_rows[[c for c in common_cols if c in srts_rows.columns]]
    ], ignore_index=True)
    table_09 = table_09.sort_values('crashes_150m', ascending=False)
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

    table_09b.to_csv(f'{OUTPUT_DIR}/table_09b_aggregate_comparison.csv', index=False)

    # Table 09c: Top denied by crashes (ranked list for article)
    sig_denied = signal_prox[
        (signal_prox['outcome'] == 'denied') & signal_prox['latitude'].notna()
    ].copy()
    sig_denied['location_name'] = (
        sig_denied['mainstreet'].fillna('') + ' & ' + sig_denied['crossstreet1'].fillna('')
    ).str.title()
    sig_denied['dataset'] = 'Signal Study'
    sig_denied['request_type'] = sig_denied.get('requesttype', 'N/A')

    srts_denied = srts_prox[
        (srts_prox['outcome'] == 'denied') & srts_prox['latitude'].notna()
    ].copy()
    srts_denied['location_name'] = (
        srts_denied['onstreet'].fillna('') + ' (' +
        srts_denied['fromstreet'].fillna('') + ' to ' +
        srts_denied['tostreet'].fillna('') + ')'
    ).str.title()
    srts_denied['dataset'] = 'SRTS'
    srts_denied['request_type'] = 'Speed Bump'

    common_cols_c = ['location_name', 'dataset', 'request_type', 'latitude', 'longitude',
                     'crashes_150m', 'injuries_150m', 'ped_injuries_150m', 'fatalities_150m']
    combined = pd.concat([
        sig_denied[[c for c in common_cols_c if c in sig_denied.columns]],
        srts_denied[[c for c in common_cols_c if c in srts_denied.columns]]
    ], ignore_index=True)
    table_09c = combined.nlargest(25, 'crashes_150m').reset_index(drop=True)
    table_09c.index = table_09c.index + 1
    table_09c.index.name = 'Rank'
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
    map_consolidated(signal_prox, srts_prox, data['cb5_crashes'])
    print("  Note: map_02_*.html and map_03_*.html are no longer generated (can be deleted).")

    # Step 4: Static charts
    print("\nStep 4: Generating charts...")
    chart_09_crash_proximity(signal_prox, srts_prox)
    chart_09b_top_denied_ranking(signal_prox, srts_prox)

    # Step 5: Data tables
    print("\nStep 5: Saving data tables...")
    save_data_tables(signal_prox, srts_prox)

    print("\n" + "=" * 60)
    print("All Part 2 outputs saved to output/")
    print("=" * 60)


if __name__ == "__main__":
    main()
