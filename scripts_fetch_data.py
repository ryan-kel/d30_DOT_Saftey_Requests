"""
Comprehensive NYC DOT Safety Data Explorer
==========================================
This script downloads and explores ALL relevant NYC Open Data datasets for
Community Board 5 (Queens) safety analysis.

Datasets:
1. Traffic Signal and All-Way Stop Study Requests (w76s-c5u4) - PRIMARY
2. Speed Reducer Tracking System / SRTS (9n6h-pt9g)
3. Accessible Pedestrian Signal Locations (de3m-c5p4) - INSTALLED APS
4. Motor Vehicle Collisions (h9gi-nx95)
5. 311 Service Requests - DOT subset (erm2-nwe9)
6. Community Board Boundaries (5crt-au7u)

Author: CB5 Safety Analysis Project
"""

import pandas as pd
import requests
import os
from datetime import datetime

# === CONFIGURATION ===
DATA_DIR = "data_raw"
OUTPUT_DIR = "output"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# NYC Open Data Socrata API endpoints
DATASETS = {
    "signal_studies": {
        "name": "Traffic Signal and All-Way Stop Study Requests",
        "endpoint": "w76s-c5u4",
        "description": "Primary dataset for infrastructure study requests (signals, stop signs, APS)",
        "doc_url": "https://data.cityofnewyork.us/Transportation/Traffic-Signal-and-All-Way-Stop-Study-Requests/w76s-c5u4",
    },
    "srts": {
        "name": "Speed Reducer Tracking System (SRTS)",
        "endpoint": "9n6h-pt9g",
        "description": "Speed bump/hump requests and their outcomes",
        "doc_url": "https://data.cityofnewyork.us/Transportation/Speed-Reducer-Tracking-System-SRTS-/9n6h-pt9g",
    },
    "aps_installed": {
        "name": "Accessible Pedestrian Signal Locations",
        "endpoint": "de3m-c5p4",
        "description": "Currently INSTALLED APS devices (not requests)",
        "doc_url": "https://data.cityofnewyork.us/Transportation/Accessible-Pedestrian-Signal-Locations/de3m-c5p4",
    },
    "crashes": {
        "name": "Motor Vehicle Collisions - Crashes",
        "endpoint": "h9gi-nx95",
        "description": "All motor vehicle crashes reported by NYPD",
        "doc_url": "https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95",
    },
    "cb_boundaries": {
        "name": "Community Board Boundaries",
        "endpoint": "jp9i-3b7y",
        "description": "Geographic boundaries for all community boards",
        "doc_url": "https://data.cityofnewyork.us/City-Government/Community-Districts/yfnk-k7r4",
    },
}

# We'll handle 311 separately due to size
DATASET_311 = {
    "name": "311 Service Requests (DOT)",
    "endpoint": "erm2-nwe9",
    "description": "311 complaints - maintenance focused, less reliable for new infrastructure",
    "doc_url": "https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9",
}


def fetch_dataset(endpoint, limit=None, where=None, select=None):
    """Fetch data from NYC Open Data Socrata API."""
    base_url = f"https://data.cityofnewyork.us/resource/{endpoint}.json"
    params = {}

    if limit:
        params["$limit"] = limit
    else:
        params["$limit"] = 100000  # Large default

    if where:
        params["$where"] = where

    if select:
        params["$select"] = select

    try:
        response = requests.get(base_url, params=params, timeout=120)
        response.raise_for_status()
        return pd.DataFrame(response.json())
    except Exception as e:
        print(f"  ERROR fetching {endpoint}: {e}")
        return pd.DataFrame()


def explore_dataframe(df, name, show_samples=3):
    """Generate comprehensive exploration of a dataframe."""
    print(f"\n{'='*70}")
    print(f"DATASET: {name}")
    print(f"{'='*70}")

    print(f"\n[SHAPE] {df.shape[0]:,} rows x {df.shape[1]} columns")

    print(f"\n[COLUMNS] ({len(df.columns)} total):")
    for i, col in enumerate(df.columns):
        dtype = df[col].dtype
        non_null = df[col].notna().sum()
        pct = (non_null / len(df)) * 100 if len(df) > 0 else 0
        print(f"  {i+1:2}. {col:<40} {str(dtype):<15} {non_null:>6,} non-null ({pct:.0f}%)")

    print(f"\n[SAMPLE DATA] (first {show_samples} rows):")
    if not df.empty:
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', 50)
        print(df.head(show_samples).to_string())

    # Key categorical columns - show value counts
    print(f"\n[KEY FIELD DISTRIBUTIONS]:")
    categorical_hints = ['status', 'type', 'borough', 'description', 'category', 'reason']
    for col in df.columns:
        if any(hint in col.lower() for hint in categorical_hints):
            if df[col].dtype == 'object' and df[col].notna().sum() > 0:
                unique_count = df[col].nunique()
                if unique_count <= 30:  # Only show if reasonable number of categories
                    print(f"\n  >> {col} ({unique_count} unique values):")
                    vc = df[col].value_counts().head(15)
                    for val, count in vc.items():
                        pct = (count / len(df)) * 100
                        print(f"      {val:<50} {count:>6,} ({pct:>5.1f}%)")

    return df


def main():
    print("="*70)
    print("NYC DOT SAFETY DATA - COMPREHENSIVE EXPLORATION")
    print(f"Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    all_data = {}

    # =========================================================================
    # 1. SIGNAL STUDIES - Most important for denial analysis
    # =========================================================================
    print("\n\n" + "#"*70)
    print("# 1. TRAFFIC SIGNAL AND ALL-WAY STOP STUDY REQUESTS")
    print("#    This is your PRIMARY dataset for 'batting average' analysis")
    print("#"*70)
    print(f"\nDocumentation: {DATASETS['signal_studies']['doc_url']}")

    print("\nFetching CITYWIDE data (all boroughs, all time)...")
    df_studies = fetch_dataset(DATASETS['signal_studies']['endpoint'])

    if not df_studies.empty:
        # Save raw data
        df_studies.to_csv(f"{DATA_DIR}/signal_studies_citywide.csv", index=False)
        print(f"  Saved to {DATA_DIR}/signal_studies_citywide.csv")

        all_data['signal_studies'] = explore_dataframe(df_studies, "Signal Studies (Citywide)")

        # Queens breakdown
        print("\n[QUEENS BREAKDOWN]:")
        queens = df_studies[df_studies['borough'] == 'Queens']
        print(f"  Queens total: {len(queens):,} requests")
        if 'statusdescription' in queens.columns:
            print("\n  Queens Status Distribution:")
            for status, count in queens['statusdescription'].value_counts().items():
                pct = (count / len(queens)) * 100
                print(f"    {status:<55} {count:>5,} ({pct:>5.1f}%)")

        # Request type breakdown
        if 'requesttype' in df_studies.columns:
            print("\n[REQUEST TYPES - Citywide]:")
            for rtype, count in df_studies['requesttype'].value_counts().items():
                pct = (count / len(df_studies)) * 100
                print(f"    {rtype:<45} {count:>6,} ({pct:>5.1f}%)")

    # =========================================================================
    # 2. SPEED REDUCER TRACKING SYSTEM (SRTS)
    # =========================================================================
    print("\n\n" + "#"*70)
    print("# 2. SPEED REDUCER TRACKING SYSTEM (SRTS)")
    print("#    Speed bump/hump requests - high denial rate dataset")
    print("#"*70)
    print(f"\nDocumentation: {DATASETS['srts']['doc_url']}")

    print("\nFetching CITYWIDE SRTS data...")
    df_srts = fetch_dataset(DATASETS['srts']['endpoint'])

    if not df_srts.empty:
        df_srts.to_csv(f"{DATA_DIR}/srts_citywide.csv", index=False)
        print(f"  Saved to {DATA_DIR}/srts_citywide.csv")

        all_data['srts'] = explore_dataframe(df_srts, "Speed Reducer Tracking System")

        # CB5 breakdown (cb='405' for Queens CB5)
        if 'cb' in df_srts.columns:
            cb5_srts = df_srts[df_srts['cb'] == '405']
            print(f"\n[CB5 (Queens) SRTS]: {len(cb5_srts):,} requests")
            if 'segmentstatusdescription' in cb5_srts.columns and len(cb5_srts) > 0:
                print("  CB5 Status Breakdown:")
                for status, count in cb5_srts['segmentstatusdescription'].value_counts().items():
                    pct = (count / len(cb5_srts)) * 100
                    print(f"    {status:<45} {count:>5,} ({pct:>5.1f}%)")

    # =========================================================================
    # 3. ACCESSIBLE PEDESTRIAN SIGNALS - INSTALLED
    # =========================================================================
    print("\n\n" + "#"*70)
    print("# 3. ACCESSIBLE PEDESTRIAN SIGNAL (APS) LOCATIONS - INSTALLED")
    print("#    Note: This is INSTALLED signals, not requests")
    print("#    Requests are tracked in Signal Studies with requesttype='Accessible Pedestrian Signal'")
    print("#"*70)
    print(f"\nDocumentation: {DATASETS['aps_installed']['doc_url']}")

    print("\nFetching APS installed locations...")
    df_aps = fetch_dataset(DATASETS['aps_installed']['endpoint'])

    if not df_aps.empty:
        df_aps.to_csv(f"{DATA_DIR}/aps_installed_citywide.csv", index=False)
        print(f"  Saved to {DATA_DIR}/aps_installed_citywide.csv")

        all_data['aps_installed'] = explore_dataframe(df_aps, "APS Installed Locations")

        # Queens breakdown
        if 'borough' in df_aps.columns:
            queens_aps = df_aps[df_aps['borough'] == 'Queens']
            print(f"\n[QUEENS APS Installed]: {len(queens_aps):,} signals")

            # Try to identify CB5 area (would need spatial join ideally)
            if 'borocd' in df_aps.columns:
                cb5_aps = df_aps[df_aps['borocd'] == '405']
                print(f"[CB5 APS Installed]: {len(cb5_aps):,} signals")

    # =========================================================================
    # 4. MOTOR VEHICLE CRASHES
    # =========================================================================
    print("\n\n" + "#"*70)
    print("# 4. MOTOR VEHICLE COLLISIONS - CRASHES")
    print("#    For correlating denied requests with crash locations")
    print("#"*70)
    print(f"\nDocumentation: {DATASETS['crashes']['doc_url']}")

    # Only fetch recent Queens crashes to keep manageable
    print("\nFetching Queens crashes (2020+, with injuries)...")
    df_crashes = fetch_dataset(
        DATASETS['crashes']['endpoint'],
        where="borough='QUEENS' AND crash_date >= '2020-01-01' AND number_of_persons_injured > 0",
        limit=50000
    )

    if not df_crashes.empty:
        df_crashes.to_csv(f"{DATA_DIR}/crashes_queens_2020plus.csv", index=False)
        print(f"  Saved to {DATA_DIR}/crashes_queens_2020plus.csv")

        all_data['crashes'] = explore_dataframe(df_crashes, "Motor Vehicle Crashes (Queens 2020+)")

    # =========================================================================
    # 5. 311 REQUESTS - Sample for DOT
    # =========================================================================
    print("\n\n" + "#"*70)
    print("# 5. 311 SERVICE REQUESTS (DOT)")
    print("#    Maintenance-focused - use with caution for infrastructure analysis")
    print("#    This is a SAMPLE - full dataset is massive")
    print("#"*70)
    print(f"\nDocumentation: {DATASET_311['doc_url']}")

    # Get CB5 DOT 311 requests from 2020+
    print("\nFetching CB5 DOT 311 requests (2020+)...")
    df_311 = fetch_dataset(
        DATASET_311['endpoint'],
        where="agency='DOT' AND community_board='05 QUEENS' AND created_date >= '2020-01-01'",
        limit=50000
    )

    if not df_311.empty:
        df_311.to_csv(f"{DATA_DIR}/311_cb5_dot_2020plus.csv", index=False)
        print(f"  Saved to {DATA_DIR}/311_cb5_dot_2020plus.csv")

        all_data['311'] = explore_dataframe(df_311, "311 Requests (CB5 DOT 2020+)")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n\n" + "="*70)
    print("DOWNLOAD SUMMARY")
    print("="*70)
    print(f"\nAll raw data saved to: {DATA_DIR}/")
    print("\nFiles created:")
    for f in os.listdir(DATA_DIR):
        if f.endswith('.csv'):
            size = os.path.getsize(f"{DATA_DIR}/{f}") / (1024*1024)
            print(f"  - {f} ({size:.1f} MB)")

    print("\n" + "="*70)
    print("DOCUMENTATION LINKS")
    print("="*70)
    for key, info in DATASETS.items():
        print(f"\n{info['name']}:")
        print(f"  URL: {info['doc_url']}")
        print(f"  Description: {info['description']}")
    print(f"\n{DATASET_311['name']}:")
    print(f"  URL: {DATASET_311['doc_url']}")
    print(f"  Description: {DATASET_311['description']}")

    return all_data


if __name__ == "__main__":
    data = main()
