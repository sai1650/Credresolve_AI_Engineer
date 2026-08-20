"""Train and evaluate the chronological answer-probability baseline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.ml.evaluation import baseline_predictions, evaluate_predictions
from app.ml.model import (
    CATEGORICAL_FEATURES,
    FEATURE_NAMES,
    FORBIDDEN_COLUMNS,
    NUMERIC_FEATURES,
    RANDOM_STATE,
    TARGET,
    make_model,
)

TRAIN_END = pd.Timestamp("2026-06-01T00:00:00Z")
VALIDATION_END = pd.Timestamp("2026-07-01T00:00:00Z")


def _load_dataset(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = set(FEATURE_NAMES) | {"event_at", TARGET}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            f"modeling dataset is missing columns: {sorted(missing)}"
        )
    unexpected_post_call = set(frame.columns) & FORBIDDEN_COLUMNS
    if unexpected_post_call:
        raise ValueError(
            "post-call columns are not allowed: "
            f"{sorted(unexpected_post_call)}"
        )
    frame["event_at"] = pd.to_datetime(
        frame["event_at"], utc=True, errors="raise"
    )
    frame = frame.sort_values("event_at", kind="mergesort").reset_index(
        drop=True
    )
    return frame


def _split(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = frame[frame.event_at < TRAIN_END]
    validation = frame[
        (frame.event_at >= TRAIN_END) & (frame.event_at < VALIDATION_END)
    ]
    test = frame[frame.event_at >= VALIDATION_END]
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError(
            "chronological train, validation, and test "
            "splits must be non-empty"
        )
    return train, validation, test


def train_model(
    input_path: str | Path = "data/processed/modeling_dataset.csv",
    model_path: str | Path = "models/answer_probability_model.joblib",
    report_path: str | Path = "data/processed/model_report.json",
) -> dict[str, Any]:
    frame = _load_dataset(input_path)
    train, validation, test = _split(frame)
    x_train, y_train = train[list(FEATURE_NAMES)], train[TARGET].astype(int)
    x_validation, y_validation = validation[list(FEATURE_NAMES)], validation[
        TARGET
    ].astype(int)
    x_test, y_test = test[list(FEATURE_NAMES)], test[TARGET].astype(int)
    rate = y_train.mean()
    imbalance = min(rate, 1 - rate) / max(rate, 1 - rate)
    class_weight = "balanced" if imbalance < 0.75 else None
    model = make_model(class_weight)
    model.fit(x_train, y_train)
    validation_probability = model.predict_proba(x_validation)[:, 1]
    test_probability = model.predict_proba(x_test)[:, 1]
    validation_metrics = evaluate_predictions(
        y_validation, validation_probability
    )
    test_metrics = evaluate_predictions(y_test, test_probability)
    baseline_validation = evaluate_predictions(
        y_validation, baseline_predictions(y_train, y_validation)
    )
    baseline_test = evaluate_predictions(
        y_test, baseline_predictions(y_train, y_test)
    )
    output_model = Path(model_path)
    output_model.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "feature_names": list(FEATURE_NAMES),
            "target": TARGET,
        },
        output_model,
    )
    warnings = [
        "This is an offline baseline and is not production-ready.",
        "Missing historical values are imputed in preprocessing.",
    ]
    report = {
        "training_rows": len(train),
        "validation_rows": len(validation),
        "test_rows": len(test),
        "features_used": list(FEATURE_NAMES),
        "target_distribution": {
            "overall": frame[TARGET].value_counts().sort_index().to_dict(),
            "train": y_train.value_counts().sort_index().to_dict(),
        },
        "metrics": {"validation": validation_metrics, "test": test_metrics},
        "statistical_baseline_metrics": {
            "validation": baseline_validation,
            "test": baseline_test,
        },
        "model_parameters": {
            "algorithm": "LogisticRegression",
            "class_weight": class_weight,
            "random_state": RANDOM_STATE,
            "numeric_features": list(NUMERIC_FEATURES),
            "categorical_features": list(CATEGORICAL_FEATURES),
        },
        "calibration_results": {
            "validation": validation_metrics["calibration"],
            "test": test_metrics["calibration"],
        },
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "warnings": warnings,
        "recommendation": _recommend(
            validation_metrics,
            test_metrics,
            baseline_validation,
            baseline_test,
        ),
    }
    output_report = Path(report_path)
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    _print_summary(report)
    return report


def _recommend(
    model_validation: dict[str, Any],
    model_test: dict[str, Any],
    baseline_validation: dict[str, Any],
    baseline_test: dict[str, Any],
) -> str:
    improvement = (
        model_test["log_loss"] < baseline_test["log_loss"]
        and model_test["brier_score"] < baseline_test["brier_score"]
    )
    return (
        "Use ML as a candidate input only; validate calibration "
        "before production."
        if improvement
        else (
            "Keep the statistical estimator primary; ML does not "
            "improve probability quality."
        )
    )


def _print_summary(report: dict[str, Any]) -> None:
    print("A. Features used:", ", ".join(report["features_used"]))
    print("B. Target distribution:", report["target_distribution"])
    print(
        "C. Train/validation/test sizes:",
        report["training_rows"],
        report["validation_rows"],
        report["test_rows"],
    )
    print("D. Model metrics:", report["metrics"])
    print("E. Calibration results:", report["calibration_results"])
    print(
        "F. Statistical baseline metrics:",
        report["statistical_baseline_metrics"],
    )
    print("G. Recommendation:", report["recommendation"])


if __name__ == "__main__":
    train_model()
