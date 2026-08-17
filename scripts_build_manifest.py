#!/usr/bin/env python3
"""Build a machine-readable provenance manifest for local analysis outputs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts_fetch_data import FETCH_PAGE_SIZE, fetch_query_plan


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
MANIFEST_PATH = OUTPUT / "source_manifest.json"
STUDY_START_YEAR = 2020


DATASETS = [
    {
        "key": "signal_studies",
        "name": "Traffic Signal and All-Way Stop Study Requests",
        "endpoint": "w76s-c5u4",
        "source_url": "https://data.cityofnewyork.us/Transportation/Traffic-Signal-and-All-Way-Stop-Study-Requests/w76s-c5u4",
        "file": "data_raw/signal_studies_citywide.csv",
        "date_column": "daterequested",
        "required": True,
    },
    {
        "key": "srts",
        "name": "Speed Reducer Tracking System",
        "endpoint": "9n6h-pt9g",
        "source_url": "https://data.cityofnewyork.us/Transportation/Speed-Reducer-Tracking-System-SRTS-/9n6h-pt9g",
        "file": "data_raw/srts_citywide.csv",
        "date_column": "requestdate",
        "required": True,
    },
    {
        "key": "aps_installed",
        "name": "Accessible Pedestrian Signal Locations",
        "endpoint": "de3m-c5p4",
        "source_url": "https://data.cityofnewyork.us/Transportation/Accessible-Pedestrian-Signal-Locations/de3m-c5p4",
        "file": "data_raw/aps_installed_citywide.csv",
        "date_column": "date_insta",
        "required": True,
    },
    {
        "key": "crashes",
        "name": "Motor Vehicle Collisions - Crashes",
        "endpoint": "h9gi-nx95",
        "source_url": "https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95",
        "file": "data_raw/crashes_queens_2020plus.csv",
        "date_column": "crash_date",
        "required": True,
        "fetch_note": "CB5-area bounding-box candidates with at least one injury or fatality; final membership uses the CB5 polygon.",
    },
    {
        "key": "cb5_signal_studies",
        "name": "Curated CB5 Signal Studies",
        "endpoint": None,
        "source_url": None,
        "file": "output/data_cb5_signal_studies.csv",
        "date_column": "daterequested",
        "required": True,
        "curated_input": True,
        "provenance_status": "Needs human-reviewable inclusion/exclusion provenance before publication.",
    },
    {
        "key": "cb5_signal_studies_provenance",
        "name": "Curated CB5 Signal Studies Provenance Scaffold",
        "endpoint": None,
        "source_url": None,
        "file": "output/data_cb5_signal_studies_provenance.csv",
        "required": True,
        "derived": True,
        "provenance_status": (
            "Row-level scaffold with committed raw-snapshot match metadata; all rows require "
            "human review before publication."
        ),
    },
    {
        "key": "cb5_boundary",
        "name": "QCB5 Boundary GeoJSON",
        "endpoint": None,
        "source_url": "https://raw.githubusercontent.com/nycehs/NYC_geography/master/CD.geo.json",
        "file": "data_raw/cb5_boundary.geojson",
        "required": True,
    },
    {
        "key": "signal_geocode_cache",
        "name": "Signal Study Geocode Cache",
        "endpoint": None,
        "source_url": None,
        "file": "output/geocode_cache_signal_studies.csv",
        "date_column": "daterequested",
        "required": True,
        "derived": True,
    },
    {
        "key": "unmatched_signal_geocodes",
        "name": "Unmatched Signal Study Geocodes",
        "endpoint": None,
        "source_url": None,
        "file": "output/data_unmatched_signal_geocodes.csv",
        "date_column": "daterequested",
        "required": True,
        "derived": True,
        "provenance_status": "Derived review list for current resolved non-APS signal-study rows without an in-polygon local geocode.",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_metadata(path: Path, date_column: str | None = None) -> dict:
    df = pd.read_csv(path, low_memory=False)
    metadata = {
        "rows": int(len(df)),
        "columns": list(df.columns),
    }
    if date_column and date_column in df.columns:
        dates = pd.to_datetime(df[date_column], errors="coerce")
        if dates.notna().any():
            metadata["date_column"] = date_column
            metadata["date_min"] = dates.min().date().isoformat()
            metadata["date_max"] = dates.max().date().isoformat()
    return metadata


def _coordinate_positions(coordinates):
    if not coordinates:
        return []
    if isinstance(coordinates[0], (int, float)):
        return [coordinates]
    positions = []
    for item in coordinates:
        positions.extend(_coordinate_positions(item))
    return positions


def geojson_metadata(path: Path) -> dict:
    geojson = json.loads(path.read_text())
    features = geojson.get("features", [])
    positions = []
    for feature in features:
        positions.extend(_coordinate_positions(feature.get("geometry", {}).get("coordinates", [])))

    metadata = {
        "geojson_type": geojson.get("type"),
        "feature_count": len(features),
        "feature_ids": [feature.get("id") for feature in features],
        "geometry_types": [feature.get("geometry", {}).get("type") for feature in features],
        "coordinate_points": len(positions),
    }
    if len(features) == 1:
        metadata["properties"] = features[0].get("properties", {})
    if positions:
        lons = [position[0] for position in positions]
        lats = [position[1] for position in positions]
        metadata["bounds"] = {
            "min_lon": min(lons),
            "min_lat": min(lats),
            "max_lon": max(lons),
            "max_lat": max(lats),
        }
    return metadata


def file_metadata(spec: dict) -> dict:
    path = ROOT / spec["file"]
    if not path.exists():
        if spec.get("required", False):
            raise FileNotFoundError(spec["file"])
        return {"exists": False}

    info = {
        "exists": True,
        "path": spec["file"],
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }
    if path.suffix.lower() == ".csv":
        info.update(csv_metadata(path, spec.get("date_column")))
    elif path.suffix.lower() == ".geojson":
        info.update(geojson_metadata(path))
    return info


def source_links(spec: dict) -> dict:
    endpoint = spec.get("endpoint")
    if not endpoint:
        return {}
    return {
        "resource_url": f"https://data.cityofnewyork.us/resource/{endpoint}.json",
        "metadata_url": f"https://data.cityofnewyork.us/api/views/{endpoint}.json",
    }


def build_manifest() -> dict:
    fetch_plan = fetch_query_plan()
    datasets = []
    analysis_end_year = datetime.now(timezone.utc).date().year - 1
    for spec in DATASETS:
        entry = {k: v for k, v in spec.items() if k not in {"file", "date_column", "required"}}
        entry.update(source_links(spec))
        if spec["key"] in fetch_plan:
            query = fetch_plan[spec["key"]]
            entry["fetch_query"] = {
                "where": query.get("where"),
                "select": query.get("select"),
                "order": query.get("order"),
                "limit": query.get("limit"),
                "page_size": FETCH_PAGE_SIZE,
                "output_path": query.get("output_path"),
            }
        entry.update(file_metadata(spec))
        datasets.append(entry)

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "analysis_window": {
            "start_year": STUDY_START_YEAR,
            "end_year": analysis_end_year,
            "note": (
                f"Current committed outputs use {STUDY_START_YEAR}-{analysis_end_year}; "
                "scripts auto-compute the last complete year."
            ),
        },
        "datasets": datasets,
    }


def write_manifest(path: Path = MANIFEST_PATH) -> dict:
    from scripts_build_curated_provenance import write_provenance

    write_provenance()
    manifest = build_manifest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> int:
    manifest = write_manifest()
    print(f"Wrote {MANIFEST_PATH}")
    for dataset in manifest["datasets"]:
        rows = dataset.get("rows")
        rows_text = f"{rows:,} rows" if rows is not None else "non-tabular"
        print(f"  - {dataset['key']}: {rows_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
