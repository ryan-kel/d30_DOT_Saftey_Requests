"""
Chart Generation for CB5 Safety Infrastructure Analysis
========================================================
Generates all charts and saves to output/ directory.

Usage:
    python generate_charts.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from shapely.geometry import shape, Point
from shapely.prepared import prep
import json
import warnings
import os

warnings.filterwarnings('ignore')

# === CONFIGURATION ===
DATA_DIR = "data_raw"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

CB5_BOUNDARY_PATH = f"{DATA_DIR}/cb5_boundary.geojson"
CB5_BOUNDARY_URL = "https://raw.githubusercontent.com/nycehs/NYC_geography/master/CD.geo.json"

# Academic styling - Times New Roman, formal appearance
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

# Color scheme — unified palette
COLORS = {
    'primary': '#2C5F8B',      # Navy blue — CB5 / main data
    'secondary': '#666666',     # Gray — citywide lines in trend charts
    'citywide': '#B8860B',     # Dark goldenrod — citywide comparison bars
    'cb5_highlight': '#1a1a1a', # Black — CB5 bar in ranked comparisons
    'denied': '#B44040',       # Muted red — denial-themed bars (unified w/ maps)
    'approved': '#4A7C59',     # Muted green — approval-themed bars (unified w/ maps)
    'avg_line': '#B8860B',     # Dark goldenrod dashed — citywide average reference lines
    'crash': '#996633',        # Warm brown — crash data (unified w/ maps)
    'crash_alt': '#CC9966',    # Lighter warm brown — injury data (unified w/ maps)
}

# Denial-reason gradient (darkest to lightest, for ranked horizontal bars)
DENIAL_SHADES = ['#8B2020', '#B44040', '#C46060', '#D48080', '#DDA0A0', '#E6B8B8', '#EED0D0']

# Categorical palette (for pie charts, multi-line series, etc.)
CATEGORY_PALETTE = ['#2C5F8B', '#B8860B', '#8B0000', '#006400', '#7B5EA7', '#4A7C6F', '#666666']


def _load_cb5_boundary():
    """Load CB5 boundary GeoJSON, downloading if needed."""
    if os.path.exists(CB5_BOUNDARY_PATH):
        with open(CB5_BOUNDARY_PATH) as f:
            return json.load(f)

    print("  Downloading CB5 boundary GeoJSON...")
    import requests
    resp = requests.get(CB5_BOUNDARY_URL, timeout=30)
    resp.raise_for_status()
    all_districts = resp.json()

    for feature in all_districts.get('features', []):
        if feature.get('properties', {}).get('GEOCODE') == 405:
            cb5_geojson = {"type": "FeatureCollection", "features": [feature]}
            with open(CB5_BOUNDARY_PATH, 'w') as f:
                json.dump(cb5_geojson, f)
            return cb5_geojson

    raise ValueError("Could not find GEOCODE=405 in community districts GeoJSON")


def _load_cb5_polygon():
    """Load the CB5 boundary as a shapely polygon."""
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


def load_data():
    """Load all datasets."""
    print("Loading datasets...")

    signal_studies = pd.read_csv(f'{DATA_DIR}/signal_studies_citywide.csv', low_memory=False)
    srts = pd.read_csv(f'{DATA_DIR}/srts_citywide.csv', low_memory=False)
    crashes = pd.read_csv(f'{DATA_DIR}/crashes_queens_2020plus.csv', low_memory=False)
    cb5_studies = pd.read_csv(f'{OUTPUT_DIR}/data_cb5_signal_studies.csv', low_memory=False)

    print(f"  Signal Studies: {len(signal_studies):,}")
    print(f"  Speed Bumps (SRTS): {len(srts):,}")
    print(f"  Crashes: {len(crashes):,}")
    print(f"  CB5 Studies: {len(cb5_studies):,}")

    return signal_studies, srts, crashes, cb5_studies


def prepare_data(signal_studies, srts, crashes, cb5_studies):
    """Prepare and filter datasets."""

    def classify_outcome(status):
        if pd.isna(status): return 'unknown'
        s = status.lower()
        if 'denial' in s or ('engineering study completed' in s and 'approval' not in s): return 'denied'
        if 'approval' in s or 'approved' in s or 'aps installed' in s or 'aps ranking' in s or 'aps design' in s: return 'approved'
        return 'pending'

    # Process signal studies
    signal_studies['outcome'] = signal_studies['statusdescription'].apply(classify_outcome)
    signal_studies['daterequested'] = pd.to_datetime(signal_studies['daterequested'], errors='coerce')
    signal_studies['year'] = signal_studies['daterequested'].dt.year

    cb5_studies['outcome'] = cb5_studies['statusdescription'].apply(classify_outcome)
    cb5_studies['daterequested'] = pd.to_datetime(cb5_studies['daterequested'], errors='coerce')
    cb5_studies['year'] = cb5_studies['daterequested'].dt.year

    # Process SRTS
    srts['cb_num'] = pd.to_numeric(srts['cb'], errors='coerce')
    srts['requestdate'] = pd.to_datetime(srts['requestdate'], errors='coerce')
    srts['year'] = srts['requestdate'].dt.year

    # Filter to resolved, exclude APS
    signal_resolved = signal_studies[signal_studies['outcome'].isin(['denied', 'approved'])]
    signal_no_aps = signal_resolved[signal_resolved['requesttype'] != 'Accessible Pedestrian Signal']

    cb5_resolved = cb5_studies[cb5_studies['outcome'].isin(['denied', 'approved'])]
    cb5_no_aps = cb5_resolved[cb5_resolved['requesttype'] != 'Accessible Pedestrian Signal']

    srts_resolved = srts[srts['segmentstatusdescription'].isin(['Not Feasible', 'Feasible'])]
    cb5_srts_raw = srts_resolved[srts_resolved['cb_num'] == 405]

    # Apply CB5 cross-street exclusion filter (see REFERENCE_cb5_boundaries.md)
    # Records labeled cb=405 are excluded if cross streets indicate locations north of the LIE
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
    print(f"  CB5 SRTS: {len(cb5_srts_raw):,} raw -> {len(cb5_srts):,} after cross-street filter ({cb5_excluded.sum()} excluded)")

    # Polygon filter: remove any SRTS records with coords outside the actual CB5 boundary
    cb5_srts['fromlatitude'] = pd.to_numeric(cb5_srts['fromlatitude'], errors='coerce')
    cb5_srts['fromlongitude'] = pd.to_numeric(cb5_srts['fromlongitude'], errors='coerce')
    cb5_srts, n_srts_poly = _filter_points_in_cb5(cb5_srts, lat_col='fromlatitude', lon_col='fromlongitude')
    print(f"  CB5 SRTS: -> {len(cb5_srts):,} after polygon filter ({n_srts_poly} excluded)")

    # Process crashes
    crashes['crash_date'] = pd.to_datetime(crashes['crash_date'], errors='coerce')
    crashes['latitude'] = pd.to_numeric(crashes['latitude'], errors='coerce')
    crashes['longitude'] = pd.to_numeric(crashes['longitude'], errors='coerce')
    crashes['number_of_persons_injured'] = pd.to_numeric(crashes['number_of_persons_injured'], errors='coerce').fillna(0)
    crashes['number_of_pedestrians_injured'] = pd.to_numeric(crashes['number_of_pedestrians_injured'], errors='coerce').fillna(0)
    # Polygon filter: crashes — use actual CB5 community district boundary
    cb5_crashes, n_crash_poly = _filter_points_in_cb5(crashes)
    print(f"  CB5 Crashes: {len(cb5_crashes):,} (polygon filter, {n_crash_poly} excluded)")

    return {
        'signal_studies': signal_studies,
        'signal_no_aps': signal_no_aps,
        'cb5_studies': cb5_studies,
        'cb5_no_aps': cb5_no_aps,
        'srts': srts,
        'srts_resolved': srts_resolved,
        'cb5_srts': cb5_srts,
        'crashes': crashes,
        'cb5_crashes': cb5_crashes,
    }


def chart_01_request_volume(data):
    """Chart 1: Request Volume by Borough."""
    signal_studies = data['signal_studies']
    cb5_studies = data['cb5_studies']

    # Filter to 2020–2025 (match CB5 data range)
    signal_capped = signal_studies[signal_studies['year'].between(2020, 2025)].copy()
    cb5_capped = cb5_studies[cb5_studies['year'].between(2020, 2025)].copy()

    def normalize_borough(b):
        if pd.isna(b): return 'Unknown'
        b = str(b).strip()
        if b in ['Queens', 'Brooklyn', 'Manhattan', 'Bronx', 'Staten Island']:
            return b
        return 'Unknown'

    signal_capped['borough_clean'] = signal_capped['borough'].apply(normalize_borough)
    borough_counts = signal_capped['borough_clean'].value_counts().sort_values(ascending=True)

    # CB5 request types
    cb5_types = cb5_capped['requesttype'].value_counts()
    top_types = cb5_types.head(5)
    other_count = cb5_types[5:].sum()
    if other_count > 0:
        top_types = pd.concat([top_types, pd.Series({'Other': other_count})])
    top_types = top_types.sort_values(ascending=True)

    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Left panel
    bars1 = axes[0].barh(borough_counts.index, borough_counts.values,
                         color=COLORS['primary'], edgecolor='black', zorder=3)
    for bar, val in zip(bars1, borough_counts.values):
        axes[0].text(val + 200, bar.get_y() + bar.get_height()/2, f'{val:,}', va='center', fontsize=10)

    axes[0].set_xlabel('Number of Requests', fontweight='bold')
    axes[0].set_title(f'Signal Study Requests by Borough\n(Citywide, n={len(signal_capped):,}, 2020–2025)', fontweight='bold', fontsize=12)
    axes[0].set_xlim(0, borough_counts.max() * 1.15)

    # Right panel — hatch APS bar to flag court-mandated status
    bar_colors = [COLORS['secondary'] if label == 'Accessible Pedestrian Signal' else COLORS['primary']
                  for label in top_types.index]
    bars2 = axes[1].barh(top_types.index, top_types.values,
                         color=bar_colors, edgecolor='black', zorder=3)
    for bar, label in zip(bars2, top_types.index):
        if label == 'Accessible Pedestrian Signal':
            bar.set_hatch('///')
            bar.set_edgecolor('black')

    for bar, val in zip(bars2, top_types.values):
        axes[1].text(val + 2, bar.get_y() + bar.get_height()/2, f'{val:,}', va='center', fontsize=10)

    # APS annotation
    from matplotlib.patches import Patch
    aps_legend = Patch(facecolor=COLORS['secondary'], edgecolor='black', hatch='///',
                       label='Court-mandated (excl. from denial rates)')
    axes[1].legend(handles=[aps_legend], loc='lower right', fontsize=8, framealpha=0.9)

    axes[1].set_xlabel('Number of Requests', fontweight='bold')
    cb5_min_year = int(cb5_capped['year'].min())
    cb5_max_year = min(int(cb5_capped['year'].max()), 2025)
    axes[1].set_title(f'QCB5 Requests by Type\n(n={len(cb5_capped):,}, {cb5_min_year}–{cb5_max_year})', fontweight='bold', fontsize=12)
    axes[1].set_xlim(0, top_types.max() * 1.2)

    fig.suptitle('DOT Signal Study Request Volume, 2020–2025', fontweight='bold', fontsize=14, y=1.02)
    fig.text(0.01, -0.02, 'Source: NYC Open Data - Signal Studies (w76s-c5u4)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_01_request_volume_by_borough.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Save underlying data tables
    borough_df = borough_counts.rename_axis('Borough').reset_index(name='Requests')
    borough_df = borough_df.sort_values('Requests', ascending=False)
    borough_df.to_csv(f'{OUTPUT_DIR}/table_01a_requests_by_borough.csv', index=False)

    cb5_type_df = top_types.rename_axis('Request Type').reset_index(name='Requests')
    cb5_type_df = cb5_type_df.sort_values('Requests', ascending=False)
    cb5_type_df.to_csv(f'{OUTPUT_DIR}/table_01b_cb5_requests_by_type.csv', index=False)

    print("  Chart 01 saved.")


def chart_01z_request_volume_full(data):
    """Chart 1z: Request Volume by Borough — full history."""
    signal_studies = data['signal_studies']

    signal_capped = signal_studies[signal_studies['year'] <= 2025].copy()

    def normalize_borough(b):
        if pd.isna(b): return 'Unknown'
        b = str(b).strip()
        if b in ['Queens', 'Brooklyn', 'Manhattan', 'Bronx', 'Staten Island']:
            return b
        return 'Unknown'

    signal_capped['borough_clean'] = signal_capped['borough'].apply(normalize_borough)
    borough_counts = signal_capped['borough_clean'].value_counts().sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.barh(borough_counts.index, borough_counts.values,
                   color=COLORS['primary'], edgecolor='black', zorder=3)
    for bar, val in zip(bars, borough_counts.values):
        ax.text(val + 200, bar.get_y() + bar.get_height()/2, f'{val:,}', va='center', fontsize=10)

    ax.set_xlabel('Number of Requests', fontweight='bold')
    min_yr = int(signal_capped['year'].min())
    ax.set_title(f'Signal Study Requests by Borough\n(Citywide, n={len(signal_capped):,}, {min_yr}–2025)', fontweight='bold', fontsize=12)
    ax.set_xlim(0, borough_counts.max() * 1.15)
    ax.yaxis.grid(False)

    fig.text(0.01, -0.02, 'Source: NYC Open Data - Signal Studies (w76s-c5u4)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_01z_request_volume_full.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    borough_df = borough_counts.rename_axis('Borough').reset_index(name='Requests')
    borough_df = borough_df.sort_values('Requests', ascending=False)
    borough_df.to_csv(f'{OUTPUT_DIR}/table_01z_requests_by_borough_full.csv', index=False)

    print("  Chart 01z saved.")


def chart_01bz_requests_by_year_full(data):
    """Chart 1bz: Request Trends — full history (Citywide + Queens lines)."""
    signal_studies = data['signal_studies']

    cw_yearly = signal_studies[signal_studies['year'].between(1996, 2025)].groupby('year').size()
    queens_yearly = signal_studies[
        (signal_studies['borough'] == 'Queens') & signal_studies['year'].between(1996, 2025)
    ].groupby('year').size()

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(cw_yearly.index, cw_yearly.values, marker='o', markersize=4,
            linewidth=2, color=COLORS['citywide'], label='Citywide', zorder=3)
    ax.plot(queens_yearly.index, queens_yearly.values, marker='s', markersize=4,
            linewidth=2, color=COLORS['primary'], label='Queens', zorder=3)
    ax.set_xlabel('Year', fontweight='bold')
    ax.set_ylabel('Number of Requests', fontweight='bold')
    ax.set_title(f'Signal Study Requests by Year\n(Citywide, n={cw_yearly.sum():,}, 1996–2025)', fontweight='bold', fontsize=12)
    ax.legend(loc='upper left', fontsize=10)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    fig.text(0.01, -0.02, 'Source: NYC Open Data - Signal Studies (w76s-c5u4)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_01bz_requests_by_year_full.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    table = pd.DataFrame({'Year': cw_yearly.index, 'Citywide': cw_yearly.values,
                          'Queens': queens_yearly.reindex(cw_yearly.index, fill_value=0).values})
    table.to_csv(f'{OUTPUT_DIR}/table_01bz_requests_by_year_full.csv', index=False)

    print("  Chart 01bz saved.")


def chart_01b_requests_by_year(data):
    """Chart 1b: Signal Study Requests by Year — Citywide vs CB5 Queens."""
    signal_studies = data['signal_studies']
    cb5_studies = data['cb5_studies']

    # Citywide by year (2020–2025)
    cw_yearly = signal_studies[signal_studies['year'].between(2020, 2025)].groupby('year').size()

    # Queens by year (2020–2025)
    queens_yearly = signal_studies[
        (signal_studies['borough'] == 'Queens') & signal_studies['year'].between(2020, 2025)
    ].groupby('year').size()

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Left panel: Citywide and Queens trends (2020–2025)
    axes[0].plot(cw_yearly.index, cw_yearly.values, marker='o', markersize=5,
                 linewidth=2, color=COLORS['citywide'], label='Citywide', zorder=3)
    axes[0].plot(queens_yearly.index, queens_yearly.values, marker='s', markersize=5,
                 linewidth=2, color=COLORS['primary'], label='Queens', zorder=3)
    axes[0].set_xlabel('Year', fontweight='bold')
    axes[0].set_ylabel('Number of Requests', fontweight='bold')
    axes[0].set_title(f'Signal Study Requests by Year\n(Citywide, n={cw_yearly.sum():,}, 2020–2025)', fontweight='bold', fontsize=12)
    axes[0].legend(loc='upper left', fontsize=10)
    axes[0].xaxis.set_major_locator(MaxNLocator(integer=True))

    # Right panel: CB5 stacked bar by request type (2020–2025)
    cb5_by_type_year = cb5_studies[cb5_studies['year'].between(2020, 2025)].copy()
    type_yearly = cb5_by_type_year.groupby(['year', 'requesttype']).size().unstack(fill_value=0)

    # Stack order: main types bottom-up, APS on top (visually distinct)
    stack_order = ['Traffic Signal', 'All-Way Stop', 'Leading Pedestrian Interval',
                   'Left Turn Arrow/Signal', 'Accessible Pedestrian Signal']
    stack_colors = ['#2C5F8B', '#B8860B', '#4A7C59', '#B44040', '#999999']

    # Aggregate minor types into "Other"
    other_cols = [c for c in type_yearly.columns if c not in stack_order]
    if other_cols:
        type_yearly['Other'] = type_yearly[other_cols].sum(axis=1)
        stack_order.append('Other')
        stack_colors.append('#D4D4D4')

    years = type_yearly.index
    bottom = np.zeros(len(years))

    from matplotlib.patches import Patch
    legend_handles = []

    for rtype, color in zip(stack_order, stack_colors):
        if rtype not in type_yearly.columns:
            continue
        vals = type_yearly[rtype].values
        bars = axes[1].bar(years, vals, bottom=bottom, color=color, edgecolor='black',
                           linewidth=0.5, zorder=3, label=rtype)
        # Hatch APS segment
        if rtype == 'Accessible Pedestrian Signal':
            for bar in bars:
                bar.set_hatch('///')
            legend_handles.append(Patch(facecolor=color, edgecolor='black', hatch='///', label=rtype))
        else:
            legend_handles.append(Patch(facecolor=color, edgecolor='black', label=rtype))
        bottom += vals

    # Total labels on top of each bar
    for i, yr in enumerate(years):
        total = int(bottom[i])
        axes[1].text(yr, total + 1.5, str(total), ha='center', va='bottom', fontsize=9, fontweight='bold')

    axes[1].set_xlabel('Year', fontweight='bold')
    axes[1].set_ylabel('Number of Requests', fontweight='bold')
    axes[1].set_title(f'QCB5 Requests by Type\n(n={len(cb5_by_type_year):,}, 2020–2025)',
                      fontweight='bold', fontsize=12)
    axes[1].legend(handles=legend_handles, loc='upper right', fontsize=8, framealpha=0.9)
    axes[1].xaxis.set_major_locator(MaxNLocator(integer=True))
    axes[1].set_ylim(0, bottom.max() * 1.12)
    axes[1].xaxis.grid(False)  # vertical gridlines not useful for discrete bars

    fig.suptitle('DOT Signal Study Request Trends, 2020–2025', fontweight='bold', fontsize=14, y=1.02)
    fig.text(0.01, -0.02, 'Source: NYC Open Data - Signal Studies (w76s-c5u4)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_01b_requests_by_year.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Save underlying data tables
    left_df = pd.DataFrame({'Year': cw_yearly.index, 'Citywide': cw_yearly.values, 'Queens': queens_yearly.reindex(cw_yearly.index, fill_value=0).values})
    left_df.to_csv(f'{OUTPUT_DIR}/table_01b_left_requests_by_year.csv', index=False)

    right_df = type_yearly[stack_order].copy()
    right_df['Total'] = right_df.sum(axis=1)
    right_df.index.name = 'Year'
    right_df.to_csv(f'{OUTPUT_DIR}/table_01b_right_cb5_by_type_year.csv')

    print("  Chart 01b saved.")


def chart_02_denial_rates_by_borough(data):
    """Chart 2: Denial Rates by Borough."""
    signal_no_aps = data['signal_no_aps']

    # Filter to 2020–2025 for consistency
    signal_recent = signal_no_aps[signal_no_aps['year'].between(2020, 2025)]

    # Calculate denial rates by borough (five boroughs only)
    five_boroughs = ['Bronx', 'Brooklyn', 'Manhattan', 'Queens', 'Staten Island']
    signal_five = signal_recent[signal_recent['borough'].isin(five_boroughs)]
    borough_stats = signal_five.groupby('borough').agg({
        'outcome': ['count', lambda x: (x == 'denied').sum()]
    })
    borough_stats.columns = ['total', 'denied']
    borough_stats['denial_rate'] = borough_stats['denied'] / borough_stats['total'] * 100
    borough_stats = borough_stats.sort_values('denial_rate', ascending=True)

    # Citywide average (2020–2025)
    cw_denial_rate = (signal_recent['outcome'] == 'denied').sum() / len(signal_recent) * 100

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = [COLORS['primary'] if b != 'Queens' else '#1B3F5E' for b in borough_stats.index]
    bars = ax.barh(borough_stats.index, borough_stats['denial_rate'], color=colors, edgecolor='black', zorder=3)

    for bar, rate in zip(bars, borough_stats['denial_rate']):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                f'{rate:.1f}%', va='center', ha='left', fontsize=10)

    ax.axvline(x=cw_denial_rate, color=COLORS['avg_line'], linestyle='--', linewidth=1.5, zorder=4)
    ax.text(cw_denial_rate + 0.5, len(borough_stats) - 0.5, f'Citywide: {cw_denial_rate:.1f}%',
            fontsize=9, color=COLORS['avg_line'])

    ax.set_xlabel('Denial Rate (%)', fontweight='bold')
    ax.set_title(f'Signal Study Denial Rates by Borough\n(Excl. APS, n={len(signal_five):,}, 2020–2025)',
                 fontweight='bold', fontsize=12)
    ax.set_xlim(0, 100)
    ax.yaxis.grid(False)  # horizontal gridlines not useful for categorical axis

    fig.text(0.01, -0.02, 'Source: NYC Open Data - Signal Studies (w76s-c5u4)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_02_denial_rates_by_borough.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Save underlying data table
    table_02 = borough_stats[['total', 'denied', 'denial_rate']].copy()
    table_02.columns = ['Total Resolved', 'Denied', 'Denial Rate (%)']
    table_02 = table_02.sort_values('Denial Rate (%)', ascending=False)
    table_02.loc['Citywide'] = [len(signal_recent), (signal_recent['outcome'] == 'denied').sum(), cw_denial_rate]
    table_02['Total Resolved'] = table_02['Total Resolved'].astype(int)
    table_02['Denied'] = table_02['Denied'].astype(int)
    table_02['Denial Rate (%)'] = table_02['Denial Rate (%)'].round(1)
    table_02.index.name = 'Borough'
    table_02.to_csv(f'{OUTPUT_DIR}/table_02_denial_rates_by_borough.csv')

    print("  Chart 02 saved.")


def _compute_yoy_data(data, year_min, year_max):
    """Shared helper: compute year-over-year stats for signal studies and speed bumps."""
    cb5_no_aps = data['cb5_no_aps']
    signal_no_aps = data['signal_no_aps']
    cb5_srts = data['cb5_srts']
    srts_resolved = data['srts_resolved']

    def _agg_signal(df, lo, hi):
        yearly = df.groupby('year').agg({
            'outcome': ['count', lambda x: (x == 'denied').sum()]
        })
        yearly.columns = ['total', 'denied']
        yearly['denial_rate'] = yearly['denied'] / yearly['total'] * 100
        return yearly[(yearly.index >= lo) & (yearly.index <= hi)]

    def _agg_srts(df, lo, hi):
        yearly = df.groupby('year').agg({
            'projectcode': 'count',
            'segmentstatusdescription': lambda x: (x == 'Not Feasible').sum()
        }).rename(columns={'projectcode': 'total', 'segmentstatusdescription': 'denied'})
        yearly['denial_rate'] = yearly['denied'] / yearly['total'] * 100
        return yearly[(yearly.index >= lo) & (yearly.index <= hi)]

    # For signal studies, CB5 data only exists 2020+
    sig_lo = max(year_min, 2020)
    return {
        'cb5_sig': _agg_signal(cb5_no_aps, sig_lo, year_max),
        'cw_sig': _agg_signal(signal_no_aps, sig_lo, year_max),
        'cb5_srts': _agg_srts(cb5_srts, year_min, year_max),
        'cw_srts': _agg_srts(srts_resolved, year_min, year_max),
    }


def _draw_yoy_chart(yoy, filename, suptitle_suffix, sig_year_label, srts_year_label):
    """Shared helper: draw the 4-panel year-over-year chart."""
    cb5_sig = yoy['cb5_sig']
    cw_sig = yoy['cw_sig']
    cb5_srts = yoy['cb5_srts']
    cw_srts = yoy['cw_srts']

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Top left: CB5 Signal Study Volume
    axes[0, 0].bar(cb5_sig.index, cb5_sig['total'], color=COLORS['primary'], edgecolor='black', zorder=3)
    axes[0, 0].set_title(f'QCB5 Signal Study Requests\n(Excl. APS, n={int(cb5_sig["total"].sum()):,}, {sig_year_label})', fontweight='bold')
    axes[0, 0].set_xlabel('Year')
    axes[0, 0].set_ylabel('Number of Requests')
    axes[0, 0].xaxis.set_major_locator(MaxNLocator(integer=True))
    axes[0, 0].xaxis.grid(False)

    # Top right: Signal Study Denial Rates
    axes[0, 1].plot(cb5_sig.index, cb5_sig['denial_rate'], marker='o', linewidth=2,
                    color=COLORS['primary'], label='QCB5', zorder=3)
    axes[0, 1].plot(cw_sig.index, cw_sig['denial_rate'], marker='s', linewidth=2,
                    color=COLORS['citywide'], linestyle='--', label='Citywide', zorder=3)
    axes[0, 1].set_title(f'Signal Study Denial Rates\n(Excl. APS, QCB5 n={int(cb5_sig["total"].sum()):,}, {sig_year_label})', fontweight='bold')
    axes[0, 1].set_xlabel('Year')
    axes[0, 1].set_ylabel('Denial Rate (%)')
    axes[0, 1].legend(loc='lower right')
    axes[0, 1].set_ylim(60, 105)
    axes[0, 1].xaxis.set_major_locator(MaxNLocator(integer=True))

    # Bottom left: CB5 Speed Bump Volume
    axes[1, 0].bar(cb5_srts.index, cb5_srts['total'], color=COLORS['primary'], edgecolor='black', zorder=3)
    axes[1, 0].set_title(f'QCB5 Speed Bump Requests\n(n={int(cb5_srts["total"].sum()):,}, {srts_year_label})', fontweight='bold')
    axes[1, 0].set_xlabel('Year')
    axes[1, 0].set_ylabel('Number of Requests')
    axes[1, 0].xaxis.set_major_locator(MaxNLocator(integer=True))
    axes[1, 0].xaxis.grid(False)

    # Bottom right: Speed Bump Denial Rates
    axes[1, 1].plot(cb5_srts.index, cb5_srts['denial_rate'], marker='o', linewidth=2,
                    color=COLORS['primary'], label='QCB5', zorder=3)
    axes[1, 1].plot(cw_srts.index, cw_srts['denial_rate'], marker='s', linewidth=2,
                    color=COLORS['citywide'], linestyle='--', label='Citywide', zorder=3)
    axes[1, 1].set_title(f'Speed Bump Denial Rates\n(QCB5 n={int(cb5_srts["total"].sum()):,}, {srts_year_label})', fontweight='bold')
    axes[1, 1].set_xlabel('Year')
    axes[1, 1].set_ylabel('Denial Rate (%)')
    axes[1, 1].legend(loc='lower right')
    axes[1, 1].set_ylim(60, 105)
    axes[1, 1].xaxis.set_major_locator(MaxNLocator(integer=True))

    fig.suptitle(f'Year-over-Year Analysis: QCB5 Safety Infrastructure Requests, {srts_year_label}',
                 fontweight='bold', fontsize=14, y=1.02)
    fig.text(0.01, -0.02, 'Source: NYC Open Data - Signal Studies (w76s-c5u4), SRTS (9n6h-pt9g)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/{filename}.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Save underlying data tables
    sig_table = pd.merge(
        cb5_sig[['total', 'denied', 'denial_rate']].rename(columns={'total': 'CB5 Total', 'denied': 'CB5 Denied', 'denial_rate': 'CB5 Denial Rate (%)'}),
        cw_sig[['total', 'denied', 'denial_rate']].rename(columns={'total': 'CW Total', 'denied': 'CW Denied', 'denial_rate': 'CW Denial Rate (%)'}),
        left_index=True, right_index=True, how='outer'
    )
    sig_table.index.name = 'Year'
    sig_table.to_csv(f'{OUTPUT_DIR}/{filename.replace("chart_", "table_")}_signal.csv')

    srts_table = pd.merge(
        cb5_srts[['total', 'denied', 'denial_rate']].rename(columns={'total': 'CB5 Total', 'denied': 'CB5 Denied', 'denial_rate': 'CB5 Denial Rate (%)'}),
        cw_srts[['total', 'denied', 'denial_rate']].rename(columns={'total': 'CW Total', 'denied': 'CW Denied', 'denial_rate': 'CW Denial Rate (%)'}),
        left_index=True, right_index=True, how='outer'
    )
    srts_table.index.name = 'Year'
    srts_table.to_csv(f'{OUTPUT_DIR}/{filename.replace("chart_", "table_")}_srts.csv')


def chart_03_year_over_year_trends(data):
    """Chart 3: Year-over-Year Trends — focused 2020–2025."""
    yoy = _compute_yoy_data(data, 2020, 2025)
    _draw_yoy_chart(yoy, 'chart_03_year_over_year_trends', '', '2020–2025', '2020–2025')
    print("  Chart 03 saved.")


def chart_03z_year_over_year_full(data):
    """Chart 3z: Year-over-Year Trends — full history."""
    yoy = _compute_yoy_data(data, 1999, 2025)
    _draw_yoy_chart(yoy, 'chart_03z_year_over_year_full', '',
                    '2020–2025', '1999–2025')
    print("  Chart 03z saved.")


def chart_04_denial_rates_by_type(data):
    """Chart 4: Denial Rates by Request Type."""
    cb5_no_aps = data['cb5_no_aps']
    signal_no_aps = data['signal_no_aps']
    cb5_srts = data['cb5_srts']
    srts_resolved = data['srts_resolved']

    # Filter to 2020–2025 for consistency
    cb5_recent = cb5_no_aps[cb5_no_aps['year'].between(2020, 2025)]
    cw_recent = signal_no_aps[signal_no_aps['year'].between(2020, 2025)]
    cb5_srts_recent = cb5_srts[cb5_srts['year'].between(2020, 2025)]
    srts_recent = srts_resolved[srts_resolved['year'].between(2020, 2025)]

    request_types = ['Traffic Signal', 'All-Way Stop', 'Left Turn Arrow/Signal', 'Leading Pedestrian Interval']

    cb5_rates = []
    cw_rates = []
    cb5_ns = []
    cw_ns = []

    for rtype in request_types:
        cb5_subset = cb5_recent[cb5_recent['requesttype'] == rtype]
        cw_subset = cw_recent[cw_recent['requesttype'] == rtype]

        cb5_ns.append(len(cb5_subset))
        cw_ns.append(len(cw_subset))

        cb5_rates.append((cb5_subset['outcome'] == 'denied').sum() / len(cb5_subset) * 100 if len(cb5_subset) > 0 else 0)
        cw_rates.append((cw_subset['outcome'] == 'denied').sum() / len(cw_subset) * 100 if len(cw_subset) > 0 else 0)

    # Add speed bumps
    request_types.append('Speed Bumps')
    cb5_ns.append(len(cb5_srts_recent))
    cw_ns.append(len(srts_recent))
    cb5_rates.append((cb5_srts_recent['segmentstatusdescription'] == 'Not Feasible').sum() / len(cb5_srts_recent) * 100)
    cw_rates.append((srts_recent['segmentstatusdescription'] == 'Not Feasible').sum() / len(srts_recent) * 100)

    fig, ax = plt.subplots(figsize=(12, 6))

    x = np.arange(len(request_types))
    width = 0.35

    bars1 = ax.bar(x - width/2, cb5_rates, width, label='QCB5', color=COLORS['primary'], edgecolor='black', zorder=3)
    bars2 = ax.bar(x + width/2, cw_rates, width, label='Citywide', color=COLORS['citywide'], edgecolor='black', zorder=3)

    for bar, rate in zip(bars1, cb5_rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f'{rate:.0f}%',
                ha='center', va='bottom', fontsize=9, fontweight='bold')
    for bar, rate in zip(bars2, cw_rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f'{rate:.0f}%',
                ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_ylabel('Denial Rate (%)', fontweight='bold')
    n_cb5 = sum(cb5_ns)
    n_cw = sum(cw_ns)
    ax.set_title(f'Denial Rates by Request Type: QCB5 vs. Citywide\n(Excl. APS, QCB5 n={n_cb5:,}, 2020–2025)', fontweight='bold', fontsize=12)
    ax.set_xticks(x)
    xlabels = [f'{t}\n(n={cb5_ns[i]:,} / {cw_ns[i]:,})' for i, t in enumerate(request_types)]
    ax.set_xticklabels(xlabels, fontsize=9)
    ax.legend(loc='upper left')
    ax.set_ylim(0, 112)
    ax.xaxis.grid(False)

    fig.text(0.01, -0.02, 'Source: NYC Open Data - Signal Studies (w76s-c5u4), SRTS (9n6h-pt9g)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_04_denial_rates_by_request_type.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Save underlying data table
    table_04 = pd.DataFrame({
        'Request Type': request_types,
        'CB5 Total': cb5_ns,
        'CB5 Denial Rate (%)': [round(r, 1) for r in cb5_rates],
        'Citywide Total': cw_ns,
        'Citywide Denial Rate (%)': [round(r, 1) for r in cw_rates],
    })
    table_04.to_csv(f'{OUTPUT_DIR}/table_04_denial_rates_by_type.csv', index=False)

    print("  Chart 04 saved.")


def _categorize_srts_denial(reason):
    """Shared helper: categorize speed bump denial reasons."""
    if pd.isna(reason): return 'Not Specified'
    r = str(reason).lower()
    if 'speed' in r and ('below' in r or 'radar' in r): return 'Speed < 30 mph'
    if 'driveway' in r or 'curb cut' in r: return 'Driveways'
    if 'street too short' in r or 'block' in r: return 'Street Too Short'
    if 'stop control' in r: return 'Stop Controls'
    if 'bus' in r: return 'Bus Route'
    if 'camera' in r: return 'Near Speed Camera'
    return 'Other'


def chart_05_speed_bump_analysis(data):
    """Chart 5: Speed Bump (SRTS) Analysis — focused 2020–2025."""
    srts_resolved = data['srts_resolved']
    cb5_srts = data['cb5_srts']

    # Filter to 2020–2025
    srts_recent = srts_resolved[srts_resolved['year'].between(2020, 2025)]
    cb5_recent = cb5_srts[cb5_srts['year'].between(2020, 2025)]

    # Left panel data: Queens CB comparison (2020–2025)
    queens_srts = srts_recent[srts_recent['borough'] == 'Queens'].copy()
    queens_srts['cb_num'] = pd.to_numeric(queens_srts['cb'], errors='coerce')

    cb_stats = queens_srts.groupby('cb_num').agg({
        'projectcode': 'count',
        'segmentstatusdescription': lambda x: (x == 'Not Feasible').sum()
    }).rename(columns={'projectcode': 'total', 'segmentstatusdescription': 'denied'})
    cb_stats['denial_rate'] = cb_stats['denied'] / cb_stats['total'] * 100
    cb_stats = cb_stats[cb_stats['total'] >= 50]
    cb_stats = cb_stats.sort_values('denial_rate', ascending=True)

    queens_denial_rate = (queens_srts['segmentstatusdescription'] == 'Not Feasible').sum() / len(queens_srts) * 100

    # Middle panel data: CB5 denial reasons (2020–2025)
    cb5_denied = cb5_recent[cb5_recent['segmentstatusdescription'] == 'Not Feasible'].copy()
    cb5_denied['reason_cat'] = cb5_denied['denialreason'].apply(_categorize_srts_denial)
    reason_counts = cb5_denied['reason_cat'].value_counts().sort_values(ascending=True)

    # Right panel data: denial reason breakdown by year (2020–2025)
    cb5_all_denied = cb5_srts[cb5_srts['segmentstatusdescription'] == 'Not Feasible'].copy()
    cb5_all_denied['reason_cat'] = cb5_all_denied['denialreason'].apply(_categorize_srts_denial)
    cb5_all_denied_recent = cb5_all_denied[cb5_all_denied['year'].between(2020, 2025)]
    reason_by_year = cb5_all_denied_recent.groupby(['year', 'reason_cat']).size().unstack(fill_value=0)
    # Collapse to "Speed < 30 mph" vs "All Other Reasons"
    speed_col = 'Speed < 30 mph' if 'Speed < 30 mph' in reason_by_year.columns else None
    if speed_col:
        other_cols = [c for c in reason_by_year.columns if c != speed_col]
        reason_simple = pd.DataFrame({
            'Speed < 30 mph': reason_by_year[speed_col],
            'All Other Reasons': reason_by_year[other_cols].sum(axis=1)
        })
    else:
        reason_simple = pd.DataFrame({'All Other Reasons': reason_by_year.sum(axis=1)})

    # Create figure
    fig, axes = plt.subplots(1, 3, figsize=(15, 6))

    # Left panel: Queens CB comparison
    cb_labels = [f'CB{int(cb)-400}' for cb in cb_stats.index]
    colors = [COLORS['primary'] if cb != 405 else '#1B3F5E' for cb in cb_stats.index]

    bars1 = axes[0].barh(cb_labels, cb_stats['denial_rate'], color=colors, edgecolor='black', zorder=2)

    label_x = 101
    for bar, rate in zip(bars1, cb_stats['denial_rate']):
        axes[0].text(label_x, bar.get_y() + bar.get_height()/2,
                     f'{rate:.0f}%', va='center', ha='left', fontsize=9)

    axes[0].axvline(x=queens_denial_rate, color=COLORS['avg_line'], linestyle='--', linewidth=1.5, zorder=4)
    axes[0].text(queens_denial_rate - 1, -0.8, f'Queens Avg {queens_denial_rate:.1f}%',
                 ha='right', fontsize=8, color=COLORS['avg_line'])

    axes[0].set_xlabel('Denial Rate (%)', fontweight='bold')
    axes[0].set_title(f'Speed Bump Denial Rates by Queens CB\n(n={len(queens_srts):,}, 2020–2025)', fontweight='bold', fontsize=12)
    axes[0].set_xlim(0, 112)
    axes[0].yaxis.grid(False)

    # Middle panel: CB5 Denial Reasons
    reason_colors = [COLORS['denied']] * len(reason_counts)
    bars2 = axes[1].barh(reason_counts.index, reason_counts.values,
                         color=reason_colors, edgecolor='black', zorder=3)

    for bar, val in zip(bars2, reason_counts.values):
        pct = val / reason_counts.sum() * 100
        axes[1].text(val + 2, bar.get_y() + bar.get_height()/2, f'{pct:.0f}%', va='center', fontsize=9)

    axes[1].set_xlabel('Number of Denials', fontweight='bold')
    axes[1].set_title(f'QCB5 Speed Bump Denial Reasons\n(n={len(cb5_denied):,}, 2020–2025)', fontweight='bold', fontsize=12)
    axes[1].set_xlim(0, reason_counts.max() * 1.15)
    axes[1].yaxis.grid(False)

    # Right panel: "Speed < 30 mph" vs other reasons by year (stacked bar)
    years = reason_simple.index
    bottom = np.zeros(len(years))
    stack_colors = [DENIAL_SHADES[0], '#BAB0AC']
    from matplotlib.patches import Patch
    legend_handles = []

    for col, color in zip(reason_simple.columns, stack_colors):
        vals = reason_simple[col].values
        axes[2].bar(years, vals, bottom=bottom, color=color, edgecolor='black', linewidth=0.5, zorder=3)
        legend_handles.append(Patch(facecolor=color, edgecolor='black', label=col))
        bottom += vals

    # Total labels
    for i, yr in enumerate(years):
        total = int(bottom[i])
        axes[2].text(yr, total + 1, str(total), ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Percentage annotation for Speed < 30 mph
    if speed_col:
        for i, yr in enumerate(years):
            speed_val = reason_simple.loc[yr, 'Speed < 30 mph']
            total = int(bottom[i])
            if total > 0:
                pct = speed_val / total * 100
                axes[2].text(yr, speed_val / 2, f'{pct:.0f}%', ha='center', va='center',
                             fontsize=8, fontweight='bold', color='white')

    axes[2].set_xlabel('Year', fontweight='bold')
    axes[2].set_ylabel('Number of Denials', fontweight='bold')
    axes[2].set_title(f'QCB5 Denial Reasons by Year\n(n={len(cb5_all_denied_recent):,}, 2020–2025)', fontweight='bold', fontsize=12)
    axes[2].legend(handles=legend_handles, loc='upper left', fontsize=9, framealpha=0.9)
    axes[2].xaxis.set_major_locator(MaxNLocator(integer=True))
    axes[2].set_ylim(0, bottom.max() * 1.12)
    axes[2].xaxis.grid(False)

    fig.suptitle('Speed Bump (SRTS) Analysis, QCB5, 2020–2025', fontweight='bold', fontsize=14, y=1.02)
    fig.text(0.01, -0.02, 'Source: NYC Open Data - Speed Reducer Tracking System (9n6h-pt9g)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_05_speed_bump_analysis.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Save underlying data tables
    cb_table = cb_stats[['total', 'denied', 'denial_rate']].copy()
    cb_table.index = [f'CB{int(cb)-400}' for cb in cb_table.index]
    cb_table.columns = ['Total', 'Denied', 'Denial Rate (%)']
    cb_table['Denial Rate (%)'] = cb_table['Denial Rate (%)'].round(1)
    cb_table = cb_table.sort_values('Denial Rate (%)', ascending=False)
    cb_table.index.name = 'Community Board'
    cb_table.to_csv(f'{OUTPUT_DIR}/table_05a_queens_cb_denial_rates.csv')

    reason_df = reason_counts.rename_axis('Reason').reset_index(name='Count')
    reason_df['Percent'] = (reason_df['Count'] / reason_df['Count'].sum() * 100).round(1)
    reason_df = reason_df.sort_values('Count', ascending=False)
    reason_df.to_csv(f'{OUTPUT_DIR}/table_05b_cb5_denial_reasons.csv', index=False)

    reason_simple.index.name = 'Year'
    reason_simple['Total'] = reason_simple.sum(axis=1)
    reason_simple.to_csv(f'{OUTPUT_DIR}/table_05c_denial_reasons_by_year.csv')

    print("  Chart 05 saved.")


def chart_05z_speed_bump_full(data):
    """Chart 5z: Speed Bump Analysis — full history (capped at 2025)."""
    srts_resolved = data['srts_resolved']
    cb5_srts = data['cb5_srts']

    # Cap everything at 2025
    srts_capped = srts_resolved[srts_resolved['year'] <= 2025]
    cb5_capped = cb5_srts[cb5_srts['year'] <= 2025]

    # Queens CB comparison (through 2025, n>=50)
    queens_srts = srts_capped[srts_capped['borough'] == 'Queens'].copy()
    queens_srts['cb_num'] = pd.to_numeric(queens_srts['cb'], errors='coerce')

    cb_stats = queens_srts.groupby('cb_num').agg({
        'projectcode': 'count',
        'segmentstatusdescription': lambda x: (x == 'Not Feasible').sum()
    }).rename(columns={'projectcode': 'total', 'segmentstatusdescription': 'denied'})
    cb_stats['denial_rate'] = cb_stats['denied'] / cb_stats['total'] * 100
    cb_stats = cb_stats[cb_stats['total'] >= 50]
    cb_stats = cb_stats.sort_values('denial_rate', ascending=True)

    queens_denial_rate = (queens_srts['segmentstatusdescription'] == 'Not Feasible').sum() / len(queens_srts) * 100

    # Denial reasons (through 2025)
    cb5_denied = cb5_capped[cb5_capped['segmentstatusdescription'] == 'Not Feasible'].copy()
    cb5_denied['reason_cat'] = cb5_denied['denialreason'].apply(_categorize_srts_denial)
    reason_counts = cb5_denied['reason_cat'].value_counts().sort_values(ascending=True)

    # Trend lines — full span through 2025, with minimum-n filters
    cb5_yearly = cb5_capped.groupby('year').agg({
        'projectcode': 'count',
        'segmentstatusdescription': lambda x: (x == 'Not Feasible').sum()
    }).rename(columns={'projectcode': 'total', 'segmentstatusdescription': 'denied'})
    cb5_yearly['denial_rate'] = cb5_yearly['denied'] / cb5_yearly['total'] * 100
    cb5_yearly = cb5_yearly[cb5_yearly['total'] >= 5]  # exclude years with n<5

    cw_yearly = srts_capped.groupby('year').agg({
        'projectcode': 'count',
        'segmentstatusdescription': lambda x: (x == 'Not Feasible').sum()
    }).rename(columns={'projectcode': 'total', 'segmentstatusdescription': 'denied'})
    cw_yearly['denial_rate'] = cw_yearly['denied'] / cw_yearly['total'] * 100
    cw_yearly = cw_yearly[cw_yearly['total'] >= 10]  # exclude years with n<10

    fig, axes = plt.subplots(1, 3, figsize=(15, 6))

    # Left: CB comparison
    q_min_yr = int(queens_srts['year'].min())
    cb_labels = [f'CB{int(cb)-400}' for cb in cb_stats.index]
    colors = [COLORS['primary'] if cb != 405 else '#1B3F5E' for cb in cb_stats.index]
    bars1 = axes[0].barh(cb_labels, cb_stats['denial_rate'], color=colors, edgecolor='black', zorder=2)
    label_x = 101
    for bar, rate in zip(bars1, cb_stats['denial_rate']):
        axes[0].text(label_x, bar.get_y() + bar.get_height()/2, f'{rate:.0f}%', va='center', ha='left', fontsize=9)
    axes[0].axvline(x=queens_denial_rate, color=COLORS['avg_line'], linestyle='--', linewidth=1.5, zorder=4)
    axes[0].text(queens_denial_rate - 1, -0.8, f'Queens Avg {queens_denial_rate:.1f}%',
                 ha='right', fontsize=8, color=COLORS['avg_line'])
    axes[0].set_xlabel('Denial Rate (%)', fontweight='bold')
    axes[0].set_title(f'Speed Bump Denial Rates by Queens CB\n(n={len(queens_srts):,}, {q_min_yr}–2025)', fontweight='bold', fontsize=12)
    axes[0].set_xlim(0, 112)
    axes[0].yaxis.grid(False)

    # Middle: Denial Reasons
    cb5_min_yr = int(cb5_capped['year'].min())
    reason_colors = [COLORS['denied']] * len(reason_counts)
    bars2 = axes[1].barh(reason_counts.index, reason_counts.values, color=reason_colors, edgecolor='black', zorder=3)
    for bar, val in zip(bars2, reason_counts.values):
        pct = val / reason_counts.sum() * 100
        axes[1].text(val + 5, bar.get_y() + bar.get_height()/2, f'{pct:.0f}%', va='center', fontsize=9)
    axes[1].set_xlabel('Number of Denials', fontweight='bold')
    axes[1].set_title(f'QCB5 Speed Bump Denial Reasons\n(n={len(cb5_denied):,}, {cb5_min_yr}–2025)', fontweight='bold', fontsize=12)
    axes[1].set_xlim(0, reason_counts.max() * 1.18)
    axes[1].yaxis.grid(False)

    # Right: Trend Lines
    axes[2].plot(cb5_yearly.index, cb5_yearly['denial_rate'], marker='o', linewidth=2, markersize=4,
                 color=COLORS['primary'], label='QCB5', zorder=3)
    axes[2].plot(cw_yearly.index, cw_yearly['denial_rate'], marker='s', linewidth=2, markersize=3,
                 color=COLORS['secondary'], linestyle='--', label='Citywide', zorder=3)
    trend_min = int(min(cb5_yearly.index.min(), cw_yearly.index.min()))
    axes[2].set_xlabel('Year', fontweight='bold')
    axes[2].set_ylabel('Denial Rate (%)', fontweight='bold')
    axes[2].set_title(f'Denial Rate Trends\n(QCB5 n={int(cb5_yearly["total"].sum()):,}, {trend_min}–2025)', fontweight='bold', fontsize=12)
    axes[2].legend(loc='lower right', fontsize=9)
    all_rates = pd.concat([cb5_yearly['denial_rate'], cw_yearly['denial_rate']])
    axes[2].set_ylim(max(0, all_rates.min() - 5), min(108, all_rates.max() + 8))
    # Clean x-axis: ticks every 5 years
    from matplotlib.ticker import MultipleLocator
    axes[2].xaxis.set_major_locator(MultipleLocator(5))
    axes[2].xaxis.set_minor_locator(MultipleLocator(1))

    fig.suptitle(f'Speed Bump (SRTS) Analysis, QCB5, {q_min_yr}–2025', fontweight='bold', fontsize=14, y=1.02)
    fig.text(0.01, -0.02, 'Source: NYC Open Data - Speed Reducer Tracking System (9n6h-pt9g)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_05z_speed_bump_full.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print("  Chart 05z saved.")


def _dedup_signal_studies(df):
    """De-duplicate signal study records that share the same externalreferencenumber.

    Some external requests generate multiple internal tracking records (sequential
    CQ reference numbers with the same DOT external ref).  We collapse these to
    one record per external reference, keeping the most recent status date.
    Records with null or 'INTERNAL REQUEST' external refs are kept as-is.
    """
    ext = df['externalreferencenumber'].fillna('')
    is_dup_candidate = ext.str.startswith('DOT-')
    keep_as_is = df[~is_dup_candidate]
    dedup_pool = df[is_dup_candidate].copy()
    # Keep one record per external reference (latest status date)
    dedup_pool['statusdate'] = pd.to_datetime(dedup_pool['statusdate'], errors='coerce')
    deduped = dedup_pool.sort_values('statusdate', ascending=False).drop_duplicates(
        subset='externalreferencenumber', keep='first')
    return pd.concat([keep_as_is, deduped], ignore_index=True)


def chart_06_most_denied_intersections(data):
    """Chart 6: Most Denied Intersections."""
    cb5_no_aps = data['cb5_no_aps']

    cb5_denied = cb5_no_aps[cb5_no_aps['outcome'] == 'denied'].copy()

    # De-duplicate administrative duplicates (same external reference)
    cb5_denied = _dedup_signal_studies(cb5_denied)

    cb5_denied['location'] = cb5_denied['mainstreet'].fillna('') + ' & ' + cb5_denied['crossstreet1'].fillna('')
    # Title-case for readability
    cb5_denied['location'] = cb5_denied['location'].str.title()

    location_counts = cb5_denied['location'].value_counts().head(10)

    fig, ax = plt.subplots(figsize=(12, 7))

    bars = ax.barh(location_counts.index[::-1], location_counts.values[::-1],
                   color=COLORS['denied'], edgecolor='black', zorder=3)

    for bar, val in zip(bars, location_counts.values[::-1]):
        ax.text(val + 0.1, bar.get_y() + bar.get_height()/2, str(val),
                va='center', ha='left', fontsize=10, fontweight='bold')

    ax.set_xlabel('Number of Denials', fontweight='bold')
    ax.set_title(f'Most Denied Intersections in QCB5\n(Signal Studies, Excl. APS, n={len(cb5_denied):,}, 2020–2025)',
                 fontweight='bold', fontsize=12)
    ax.set_xlim(0, location_counts.max() * 1.2)
    ax.yaxis.grid(False)

    fig.text(0.01, -0.02, 'Source: NYC Open Data - Signal Studies (w76s-c5u4) | De-duplicated by external reference number',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_06_most_denied_intersections.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Save underlying data table
    table_06 = location_counts.rename_axis('Intersection').reset_index(name='Denials')
    table_06.to_csv(f'{OUTPUT_DIR}/table_06_most_denied_intersections.csv', index=False)

    print("  Chart 06 saved.")


def chart_07_most_denied_streets_speed_bumps(data):
    """Chart 7: Most Denied Streets for Speed Bumps (2020-2025)."""
    cb5_srts = data['cb5_srts'].copy()

    # Filter to 2020-2025 for consistency (year column already computed during data loading)
    cb5_srts_recent = cb5_srts[cb5_srts['year'].between(2020, 2025)]

    cb5_srts_denied = cb5_srts_recent[cb5_srts_recent['segmentstatusdescription'] == 'Not Feasible'].copy()
    n_denied = len(cb5_srts_denied)

    # Title-case street names and count top 10
    cb5_srts_denied['street_clean'] = cb5_srts_denied['onstreet'].str.title()
    street_counts = cb5_srts_denied['street_clean'].value_counts().head(10)

    fig, ax = plt.subplots(figsize=(12, 8))

    bars = ax.barh(street_counts.index[::-1], street_counts.values[::-1],
                   color=COLORS['denied'], edgecolor='black', zorder=3)

    max_val = street_counts.max()
    for bar, val in zip(bars, street_counts.values[::-1]):
        ax.text(val + max_val * 0.01, bar.get_y() + bar.get_height()/2, str(val),
                va='center', ha='left', fontsize=10, fontweight='bold')

    ax.set_xlabel('Number of Denials', fontweight='bold')
    ax.set_title(f'Most Denied Streets for Speed Bumps in QCB5, 2020–2025 (n={n_denied:,} denials)',
                 fontweight='bold', fontsize=12)
    ax.set_xlim(0, max_val * 1.15)
    ax.yaxis.grid(False)

    fig.text(0.01, -0.02, 'Source: NYC Open Data - SRTS (9n6h-pt9g) | Each entry counts individual street segments denied',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_07_most_denied_streets_speed_bumps.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Save underlying data table
    table_07 = street_counts.rename_axis('Street').reset_index(name='Denials')
    table_07.to_csv(f'{OUTPUT_DIR}/table_07_most_denied_streets_speed_bumps.csv', index=False)

    print("  Chart 07 saved.")


def _normalize_street_name(name):
    """Normalize street names: strip whitespace, expand abbreviations, title case."""
    if pd.isna(name) or str(name).strip() == '':
        return ''
    s = str(name).strip().upper()
    # Expand common abbreviations (word boundaries)
    abbrevs = {
        ' AVE': ' AVENUE', ' BLVD': ' BOULEVARD', ' RD': ' ROAD',
        ' ST': ' STREET', ' PL': ' PLACE', ' DR': ' DRIVE',
        ' LN': ' LANE', ' CT': ' COURT', ' PKWY': ' PARKWAY',
        ' TPKE': ' TURNPIKE',
    }
    for abbr, full in abbrevs.items():
        if s.endswith(abbr):
            s = s[:-len(abbr)] + full
    return s.title()


def chart_08_crash_hotspots(data):
    """Chart 8: Crash Hotspots — CB5 Queens (2020-2025)."""
    cb5_crashes = data['cb5_crashes'].copy()

    # Filter to 2020-2025 (exclude 2026 data)
    cb5_crashes['year'] = cb5_crashes['crash_date'].dt.year
    cb5_crashes = cb5_crashes[cb5_crashes['year'].between(2020, 2025)]

    # Normalize street names to merge variants (e.g., "METROPOLITAN AVE" + "METROPOLITAN AVENUE")
    cb5_crashes['street_clean'] = cb5_crashes['on_street_name'].apply(_normalize_street_name)

    street_crashes = cb5_crashes[cb5_crashes['street_clean'] != ''].groupby('street_clean').agg({
        'collision_id': 'count',
        'number_of_persons_injured': 'sum',
        'number_of_pedestrians_injured': 'sum'
    }).rename(columns={
        'collision_id': 'crashes',
        'number_of_persons_injured': 'injuries',
        'number_of_pedestrians_injured': 'ped_injuries'
    })

    street_crashes_by_crash = street_crashes.sort_values('crashes', ascending=False).head(10)
    street_crashes_by_injury = street_crashes.sort_values('injuries', ascending=False).head(10)

    n_crashes = len(cb5_crashes)
    n_injuries = int(cb5_crashes['number_of_persons_injured'].sum())

    fig, axes = plt.subplots(1, 2, figsize=(14, 8))

    # Left: Crashes (sorted by crashes)
    bars1 = axes[0].barh(street_crashes_by_crash.index[::-1], street_crashes_by_crash['crashes'].values[::-1],
                         color=COLORS['crash'], edgecolor='black', zorder=3)
    for bar, val in zip(bars1, street_crashes_by_crash['crashes'].values[::-1]):
        axes[0].text(val + 1, bar.get_y() + bar.get_height()/2, str(int(val)),
                     va='center', ha='left', fontsize=9, fontweight='bold')

    axes[0].set_xlabel('Number of Crashes', fontweight='bold')
    axes[0].set_title(f'Total Crashes by Street\n(QCB5, n={n_crashes:,}, 2020–2025)', fontweight='bold', fontsize=12)
    axes[0].yaxis.grid(False)

    # Right: Injuries (sorted by injuries)
    bars2 = axes[1].barh(street_crashes_by_injury.index[::-1], street_crashes_by_injury['injuries'].values[::-1],
                         color=COLORS['crash_alt'], edgecolor='black', zorder=3)
    for bar, val in zip(bars2, street_crashes_by_injury['injuries'].values[::-1]):
        axes[1].text(val + 1, bar.get_y() + bar.get_height()/2, str(int(val)),
                     va='center', ha='left', fontsize=9, fontweight='bold')

    axes[1].set_xlabel('Number of Injuries', fontweight='bold')
    axes[1].set_title(f'Total Injuries by Street\n(QCB5, n={n_injuries:,} injuries, 2020–2025)', fontweight='bold', fontsize=12)
    axes[1].yaxis.grid(False)

    fig.suptitle(f'Crash Hotspots in QCB5 (n={n_crashes:,} crashes), 2020–2025', fontweight='bold', fontsize=14, y=1.02)
    fig.text(0.01, -0.02,
             'Source: NYC Open Data - Motor Vehicle Collisions (h9gi-nx95) | CB5 defined by community district polygon boundary\n'
             'Street names normalized (abbreviations expanded, variants merged)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_08_crash_hotspots_cb5.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Save underlying data tables
    table_08_crashes = street_crashes_by_crash[['crashes', 'injuries', 'ped_injuries']].reset_index()
    table_08_crashes.columns = ['Street', 'Crashes', 'Injuries', 'Pedestrian Injuries']
    table_08_crashes.to_csv(f'{OUTPUT_DIR}/table_08a_crash_hotspots_by_crashes.csv', index=False)

    table_08_injuries = street_crashes_by_injury[['crashes', 'injuries', 'ped_injuries']].reset_index()
    table_08_injuries.columns = ['Street', 'Crashes', 'Injuries', 'Pedestrian Injuries']
    table_08_injuries.to_csv(f'{OUTPUT_DIR}/table_08b_crash_hotspots_by_injuries.csv', index=False)

    print("  Chart 08 saved.")


def chart_10_combined_annual_summary(data):
    """Chart 10: Combined Annual Summary."""
    cb5_no_aps = data['cb5_no_aps']
    cb5_srts = data['cb5_srts']

    # Signal studies by year
    cb5_yearly = cb5_no_aps.groupby('year').agg({
        'outcome': ['count', lambda x: (x == 'denied').sum(), lambda x: (x == 'approved').sum()]
    })
    cb5_yearly.columns = ['total', 'denied', 'approved']
    cb5_yearly = cb5_yearly[(cb5_yearly.index >= 2020) & (cb5_yearly.index <= 2025)]

    # SRTS by year
    cb5_srts_yearly = cb5_srts.groupby('year').agg({
        'projectcode': 'count',
        'segmentstatusdescription': [lambda x: (x == 'Not Feasible').sum(), lambda x: (x == 'Feasible').sum()]
    })
    cb5_srts_yearly.columns = ['total', 'denied', 'approved']
    cb5_srts_yearly = cb5_srts_yearly[(cb5_srts_yearly.index >= 2020) & (cb5_srts_yearly.index <= 2025)]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Left: Signal Studies
    width = 0.35
    x = np.arange(len(cb5_yearly))
    axes[0].bar(x - width/2, cb5_yearly['denied'], width, label='Denied', color=COLORS['denied'], edgecolor='black', zorder=3)
    axes[0].bar(x + width/2, cb5_yearly['approved'], width, label='Approved', color=COLORS['approved'], edgecolor='black', zorder=3)

    axes[0].set_xlabel('Year', fontweight='bold')
    axes[0].set_ylabel('Number of Requests', fontweight='bold')
    axes[0].set_title(f'QCB5 Signal Study Outcomes by Year\n(Excl. APS, n={int(cb5_yearly["total"].sum()):,}, 2020–2025)', fontweight='bold', fontsize=12)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(cb5_yearly.index.astype(int))
    axes[0].legend()

    # Right: Speed Bumps
    x2 = np.arange(len(cb5_srts_yearly))
    axes[1].bar(x2 - width/2, cb5_srts_yearly['denied'], width, label='Denied', color=COLORS['denied'], edgecolor='black', zorder=3)
    axes[1].bar(x2 + width/2, cb5_srts_yearly['approved'], width, label='Approved', color=COLORS['approved'], edgecolor='black', zorder=3)

    axes[1].set_xlabel('Year', fontweight='bold')
    axes[1].set_ylabel('Number of Requests', fontweight='bold')
    axes[1].set_title(f'QCB5 Speed Bump Outcomes by Year\n(n={int(cb5_srts_yearly["total"].sum()):,}, 2020–2025)', fontweight='bold', fontsize=12)
    axes[1].set_xticks(x2)
    axes[1].set_xticklabels(cb5_srts_yearly.index.astype(int))
    axes[1].legend()

    fig.suptitle('QCB5 Annual Request Outcomes, 2020–2025', fontweight='bold', fontsize=14, y=1.02)
    fig.text(0.01, -0.02, 'Source: NYC Open Data - Signal Studies (w76s-c5u4), SRTS (9n6h-pt9g)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_10_combined_annual_summary.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print("  Chart 10 saved.")


def chart_11_denial_reasons(data):
    """Chart 11: Denial Reasons Detailed."""
    cb5_no_aps = data['cb5_no_aps']
    cb5_srts = data['cb5_srts']

    cb5_no_aps_denied = cb5_no_aps[cb5_no_aps['outcome'] == 'denied'].copy()
    cb5_srts_denied = cb5_srts[cb5_srts['segmentstatusdescription'] == 'Not Feasible'].copy()
    cb5_srts_denied['requestdate'] = pd.to_datetime(cb5_srts_denied['requestdate'], errors='coerce')
    cb5_srts_denied['year'] = cb5_srts_denied['requestdate'].dt.year

    cb5_no_aps_filtered = cb5_no_aps_denied[(cb5_no_aps_denied['year'] >= 2020) & (cb5_no_aps_denied['year'] <= 2025)]
    cb5_srts_filtered = cb5_srts_denied[(cb5_srts_denied['year'] >= 2020) & (cb5_srts_denied['year'] <= 2025)]

    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Left panel: Signal Study Denial Status
    status_counts = cb5_no_aps_filtered['statusdescription'].value_counts()
    status_consolidated = {}
    for status, count in status_counts.items():
        if 'request' in status.lower() and 'denial' in status.lower():
            status_consolidated['Request Denied'] = status_consolidated.get('Request Denied', 0) + count
        elif 'study completed' in status.lower() or 'engineering' in status.lower():
            status_consolidated['Study Completed - Denied'] = status_consolidated.get('Study Completed - Denied', 0) + count
        else:
            status_consolidated['Other Denial'] = status_consolidated.get('Other Denial', 0) + count

    status_names = list(status_consolidated.keys())
    status_values = list(status_consolidated.values())

    colors_status = [COLORS['primary'], '#4A7FA8', '#7BA3C2'][:len(status_names)]
    bars1 = axes[0].barh(status_names, status_values, color=colors_status, edgecolor='black', zorder=3)
    for bar, val in zip(bars1, status_values):
        axes[0].text(val + 3, bar.get_y() + bar.get_height()/2, str(val),
                     va='center', fontsize=11, fontweight='bold')

    axes[0].set_xlabel('Number of Denials', fontweight='bold')
    axes[0].set_title(f'QCB5 Signal Study Denial Status\n(Excl. APS, n={len(cb5_no_aps_filtered):,}, 2020–2025)', fontweight='bold', fontsize=12)
    axes[0].set_xlim(0, max(status_values) * 1.15)

    # Right panel: Speed Bump Denial Reasons over time
    def categorize_denial(reason):
        if pd.isna(reason): return 'Not Specified'
        r = str(reason).lower()
        if 'speed' in r and 'below' in r: return 'Speed Below 30 mph'
        if 'driveway' in r or 'curb cut' in r: return 'Driveways/Curb Cuts'
        if 'street too short' in r or 'block' in r: return 'Street Too Short'
        if 'stop control' in r: return 'Stop Controls Present'
        if 'bus' in r: return 'Bus Route'
        return 'Other'

    cb5_srts_filtered['reason_category'] = cb5_srts_filtered['denialreason'].apply(categorize_denial)
    yearly_reasons = cb5_srts_filtered.groupby(['year', 'reason_category']).size().unstack(fill_value=0)
    top_reasons = yearly_reasons.sum().sort_values(ascending=False).head(5).index.tolist()
    yearly_reasons_top = yearly_reasons[top_reasons]

    for i, reason in enumerate(top_reasons):
        if reason in yearly_reasons_top.columns:
            axes[1].plot(yearly_reasons_top.index, yearly_reasons_top[reason],
                        marker='o', linewidth=2, markersize=6, color=CATEGORY_PALETTE[i],
                        label=reason, zorder=3)

    axes[1].set_xlabel('Year', fontweight='bold')
    axes[1].set_ylabel('Number of Denials', fontweight='bold')
    axes[1].set_title(f'Speed Bump Denial Reasons Over Time\n(QCB5, n={len(cb5_srts_filtered):,}, 2020–2025)', fontweight='bold', fontsize=12)
    axes[1].legend(loc='upper left', fontsize=9, framealpha=0.9)
    axes[1].xaxis.set_major_locator(MaxNLocator(integer=True))

    total_denials = len(cb5_srts_filtered)
    axes[1].annotate(f'Total: {total_denials:,} denials',
                    xy=(0.98, 0.98), xycoords='axes fraction',
                    ha='right', va='top', fontsize=10, fontweight='bold',
                    bbox=dict(boxstyle='round', facecolor='white', edgecolor='gray', alpha=0.9))

    fig.suptitle('QCB5 Denial Reasons Analysis, 2020–2025', fontweight='bold', fontsize=14, y=1.02)
    fig.text(0.01, -0.02, 'Source: NYC Open Data - Signal Studies (w76s-c5u4), SRTS (9n6h-pt9g)',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_11_denial_reasons_detailed.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    print("  Chart 11 saved.")


def chart_12_request_types(data):
    """Chart 12: Request Type Mix — CB5 vs Citywide (2020-2025)."""
    cb5_no_aps = data['cb5_no_aps']
    signal_no_aps = data['signal_no_aps']
    srts_resolved = data['srts_resolved']
    cb5_srts = data['cb5_srts']

    # Filter to 2020-2025
    cb5_recent = cb5_no_aps[cb5_no_aps['year'].between(2020, 2025)]
    cw_recent = signal_no_aps[signal_no_aps['year'].between(2020, 2025)]
    srts_recent = srts_resolved[srts_resolved['year'].between(2020, 2025)]
    cb5_srts_recent = cb5_srts[cb5_srts['year'].between(2020, 2025)]

    cb5_by_type = cb5_recent.groupby('requesttype').size().sort_values(ascending=False)
    cw_by_type = cw_recent.groupby('requesttype').size().sort_values(ascending=False)

    # Request types to compare
    request_types = ['Traffic Signal', 'All-Way Stop', 'Leading Pedestrian Interval',
                     'Left Turn Arrow/Signal', 'Speed Bumps']
    cb5_counts = []
    cw_counts = []

    for rtype in request_types:
        if rtype == 'Speed Bumps':
            cb5_counts.append(len(cb5_srts_recent))
            cw_counts.append(len(srts_recent))
        else:
            cb5_counts.append(cb5_by_type.get(rtype, 0))
            cw_counts.append(cw_by_type.get(rtype, 0))

    cb5_total = sum(cb5_counts)
    cw_total = sum(cw_counts)
    cb5_pct = [c / cb5_total * 100 for c in cb5_counts]
    cw_pct = [c / cw_total * 100 for c in cw_counts]

    fig, ax = plt.subplots(figsize=(12, 7))

    x = np.arange(len(request_types))
    width = 0.35

    bars1 = ax.bar(x - width/2, cb5_pct, width, label=f'QCB5 (n={cb5_total:,})',
                   color=COLORS['primary'], edgecolor='black', zorder=3)
    bars2 = ax.bar(x + width/2, cw_pct, width, label=f'Citywide (n={cw_total:,})',
                   color=COLORS['citywide'], edgecolor='black', zorder=3)

    for bar, pct in zip(bars1, cb5_pct):
        if pct > 1:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f'{pct:.1f}%',
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
    for bar, pct in zip(bars2, cw_pct):
        if pct > 1:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f'{pct:.1f}%',
                    ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_ylabel('Share of Total Resolved Requests (%)', fontweight='bold')
    ax.set_title(f'Request Type Mix: QCB5 vs. Citywide, 2020–2025\n(Resolved Requests, Excl. APS, QCB5 n={cb5_total:,})',
                 fontweight='bold', fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace('/', '/\n') for t in request_types], fontsize=10)
    ax.legend(loc='upper left', fontsize=10)
    ax.set_ylim(0, max(max(cb5_pct), max(cw_pct)) * 1.15)
    ax.xaxis.grid(False)

    fig.text(0.01, -0.02, 'Source: NYC Open Data - Signal Studies (w76s-c5u4), SRTS (9n6h-pt9g) | Resolved records only, APS excluded',
             ha='left', fontsize=9, style='italic', color='#333333')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/chart_12_request_types_distribution.png', dpi=300,
                bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()

    # Save underlying data table
    table_12 = pd.DataFrame({
        'Request Type': request_types,
        'CB5 Count': cb5_counts,
        'CB5 Share (%)': [round(p, 1) for p in cb5_pct],
        'Citywide Count': cw_counts,
        'Citywide Share (%)': [round(p, 1) for p in cw_pct]
    })
    table_12.to_csv(f'{OUTPUT_DIR}/table_12_request_type_mix.csv', index=False)

    print("  Chart 12 saved.")


def main():
    """Generate all charts."""
    print("=" * 60)
    print("CB5 SAFETY ANALYSIS - CHART GENERATION")
    print("=" * 60)

    # Load and prepare data
    signal_studies, srts, crashes, cb5_studies = load_data()
    data = prepare_data(signal_studies, srts, crashes, cb5_studies)

    print("\nGenerating charts...")

    # Generate focused charts (2020–2025)
    chart_01_request_volume(data)
    chart_01b_requests_by_year(data)
    chart_02_denial_rates_by_borough(data)
    chart_03_year_over_year_trends(data)
    chart_04_denial_rates_by_type(data)
    chart_05_speed_bump_analysis(data)
    chart_06_most_denied_intersections(data)
    chart_07_most_denied_streets_speed_bumps(data)
    chart_08_crash_hotspots(data)
    chart_12_request_types(data)

    # Generate z-series (full history)
    print("\nGenerating z-series (full history)...")
    chart_01z_request_volume_full(data)
    chart_01bz_requests_by_year_full(data)
    chart_03z_year_over_year_full(data)
    chart_05z_speed_bump_full(data)

    print("\nAll charts saved to output/")
    print("=" * 60)


if __name__ == "__main__":
    main()
