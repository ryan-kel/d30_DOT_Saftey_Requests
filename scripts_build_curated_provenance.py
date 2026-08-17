#!/usr/bin/env python3
"""Build row-level provenance scaffolding for the curated CB5 signal-study input."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
CURATED_PATH = ROOT / "output" / "data_cb5_signal_studies.csv"
RAW_SIGNAL_PATH = ROOT / "data_raw" / "signal_studies_citywide.csv"
PROVENANCE_PATH = ROOT / "output" / "data_cb5_signal_studies_provenance.csv"

PROVENANCE_COLUMNS = [
    "curated_row_id",
    "source_file",
    "source_row_hash",
    "raw_source_file",
    "raw_match_status",
    "raw_match_count",
    "raw_row_hash",
    "raw_match_notes",
    "referencenumber",
    "id",
    "daterequested",
    "requesttype",
    "borough",
    "mainstreet",
    "crossstreet1",
    "crossstreet2",
    "statusdescription",
    "inclusion_status",
    "inclusion_basis",
    "provenance_status",
    "review_required",
    "review_notes",
]


def key_value(value) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def match_key(row: pd.Series) -> tuple[str, str]:
    return key_value(row.get("id", "")), key_value(row.get("referencenumber", ""))


def row_hash(row: pd.Series) -> str:
    parts = [
        key_value(row.get("id", "")),
        key_value(row.get("referencenumber", "")),
        key_value(row.get("daterequested", "")),
        key_value(row.get("requesttype", "")),
        key_value(row.get("mainstreet", "")),
        key_value(row.get("crossstreet1", "")),
        key_value(row.get("crossstreet2", "")),
        key_value(row.get("statusdescription", "")),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_raw_lookup(raw_path: Path = RAW_SIGNAL_PATH) -> dict[tuple[str, str], pd.DataFrame]:
    raw = pd.read_csv(raw_path, low_memory=False).copy()
    raw["_match_key"] = raw.apply(match_key, axis=1)
    return {
        key: group.drop(columns=["_match_key"])
        for key, group in raw.groupby("_match_key", sort=False, dropna=False)
    }


def raw_match_metadata(row: pd.Series, raw_lookup: dict[tuple[str, str], pd.DataFrame]) -> dict:
    matches = raw_lookup.get(match_key(row))
    if matches is None:
        return {
            "raw_source_file": "data_raw/signal_studies_citywide.csv",
            "raw_match_status": "missing_from_raw_snapshot",
            "raw_match_count": 0,
            "raw_row_hash": "",
            "raw_match_notes": (
                "No row with matching id and referencenumber exists in the committed raw "
                "Signal Studies snapshot; requires source refresh or manual provenance review."
            ),
        }

    match_count = len(matches)
    first_match = matches.iloc[0]
    if match_count == 1:
        status = "matched"
        note = "Matched committed raw Signal Studies snapshot by id and referencenumber."
    else:
        raw_hashes = {row_hash(match) for _, match in matches.iterrows()}
        status = "duplicate_raw_match"
        if len(raw_hashes) == 1:
            note = (
                "Matched duplicate identical raw rows by id and referencenumber; retained "
                "curated row for human review."
            )
        else:
            note = (
                "Matched multiple non-identical raw rows by id and referencenumber; requires "
                "manual provenance review."
            )

    return {
        "raw_source_file": "data_raw/signal_studies_citywide.csv",
        "raw_match_status": status,
        "raw_match_count": match_count,
        "raw_row_hash": row_hash(first_match),
        "raw_match_notes": note,
    }


def build_provenance(
    curated_path: Path = CURATED_PATH,
    raw_path: Path = RAW_SIGNAL_PATH,
) -> pd.DataFrame:
    curated = pd.read_csv(curated_path, low_memory=False).copy()
    raw_lookup = build_raw_lookup(raw_path)
    rows = []
    for i, (_, row) in enumerate(curated.iterrows(), start=1):
        rows.append({
            "curated_row_id": i,
            "source_file": "output/data_cb5_signal_studies.csv",
            "source_row_hash": row_hash(row),
            **raw_match_metadata(row, raw_lookup),
            "referencenumber": row.get("referencenumber", ""),
            "id": row.get("id", ""),
            "daterequested": row.get("daterequested", ""),
            "requesttype": row.get("requesttype", ""),
            "borough": row.get("borough", ""),
            "mainstreet": row.get("mainstreet", ""),
            "crossstreet1": row.get("crossstreet1", ""),
            "crossstreet2": row.get("crossstreet2", ""),
            "statusdescription": row.get("statusdescription", ""),
            "inclusion_status": "included",
            "inclusion_basis": (
                "Legacy curated QCB5 signal-study input. Signal Studies lack a community-board "
                "field and source coordinates; inclusion was carried forward from prior "
                "street-name curation and still needs row-level human review."
            ),
            "provenance_status": "needs_human_review",
            "review_required": True,
            "review_notes": "",
        })
    return pd.DataFrame(rows, columns=PROVENANCE_COLUMNS)


def write_provenance(path: Path = PROVENANCE_PATH) -> pd.DataFrame:
    provenance = build_provenance()
    path.parent.mkdir(parents=True, exist_ok=True)
    provenance.to_csv(path, index=False)
    return provenance


def main() -> int:
    provenance = write_provenance()
    print(f"Wrote {PROVENANCE_PATH} ({len(provenance):,} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
