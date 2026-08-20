"""Build the chronological modeling dataset and its quality report."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.data.features import (
    FEATURE_NAMES,
    OUTPUT_COLUMNS,
    build_feature_rows,
    read_canonical_calls,
)


def build_modeling_dataset(
    input_path: str | Path = "data/processed/canonical_calls.csv",
    output_path: str | Path = "data/processed/modeling_dataset.csv",
    report_path: str | Path = "data/processed/feature_report.json",
) -> dict[str, Any]:
    """Create the modeling CSV and JSON report from canonical calls."""
    rows, quality = build_feature_rows(read_canonical_calls(input_path))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    report = {
        **quality,
        "number_of_rows": len(rows),
        "number_of_features": len(FEATURE_NAMES),
        "feature_names": list(FEATURE_NAMES),
        "target_distribution": dict(
            Counter(row["answered_next_call"] for row in rows)
        ),
        "missing_values": {
            name: sum(row.get(name) in (None, "") for row in rows)
            for name in FEATURE_NAMES
        },
        "date_range": {
            "start": rows[0]["event_at"] if rows else None,
            "end": rows[-1]["event_at"] if rows else None,
        },
        "smoothing": {
            "alpha": 5.0,
            "default_prior_rate": 0.5,
            "description": (
                "Rates use only calls strictly before the prediction event."
            ),
        },
        "leakage_checks": {
            "strictly_before_event_time": True,
            "current_outcome_excluded": True,
            "current_duration_excluded": True,
            "future_events_excluded": True,
            "future_external_datasets_used": False,
        },
    }
    Path(report_path).write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    build_modeling_dataset()
