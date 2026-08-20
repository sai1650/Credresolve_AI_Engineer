from pathlib import Path

from app.ml.data_pipeline import (
    CATEGORICAL_FEATURES,
    METADATA_COLUMNS,
    NUMERIC_FEATURES,
    build_model_table,
    prepare_datasets,
)

ROOT = Path(__file__).parents[1]


def test_model_table_has_one_deduplicated_call_per_row() -> None:
    rows, quality = build_model_table(ROOT / "data")
    assert len(rows) == quality["usable_rows"]
    assert len({row["call_id"] for row in rows}) == len(rows)
    assert quality["duplicate_call_rows_removed"] > 0
    assert all(row["target"] in (0, 1) for row in rows)


def test_features_exclude_current_outcome_fields() -> None:
    rows, _ = build_model_table(ROOT / "data")
    feature_names = set(rows[0]) - set(METADATA_COLUMNS)
    assert "call_status" not in feature_names
    assert "duration_sec" not in feature_names
    assert "disposition_code" not in feature_names
    assert set(CATEGORICAL_FEATURES).issubset(feature_names)
    assert set(NUMERIC_FEATURES).issubset(feature_names)


def test_prepared_files_are_time_ordered_and_have_no_missing_values(
    tmp_path: Path,
) -> None:
    report = prepare_datasets(ROOT / "data", tmp_path)
    assert report["train_size"] > report["validation_size"] > 0
    assert report["test_size"] > 0
    assert report["missing_values_before_imputation"]
    for split in ("train", "validation", "test"):
        output = tmp_path / f"{split}.csv"
        assert output.exists()
        lines = output.read_text(encoding="utf-8").splitlines()
        assert "__MISSING__" in lines[0]
        assert "call_status" not in lines[0]
        assert "duration_sec" not in lines[0].split(",")
