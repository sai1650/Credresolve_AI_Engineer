"""Evaluation metrics for probability predictions."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate_predictions(
    y_true: Any, probabilities: Any, threshold: float = 0.5
) -> dict[str, Any]:
    y_true = np.asarray(y_true, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    predictions = (probabilities >= threshold).astype(int)
    metrics = {
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "log_loss": float(log_loss(y_true, probabilities, labels=[0, 1])),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision": float(
            precision_score(y_true, predictions, zero_division=0)
        ),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "predicted_probability_mean": float(probabilities.mean()),
        "actual_answer_rate": float(y_true.mean()),
    }
    fraction, mean = calibration_curve(
        y_true, probabilities, n_bins=10, strategy="quantile"
    )
    calibration_error = (
        float(np.mean(np.abs(mean - fraction))) if len(mean) else 0.0
    )
    metrics["calibration"] = {
        "probability_mean_by_bin": [float(value) for value in mean],
        "actual_rate_by_bin": [float(value) for value in fraction],
        "calibration_error": calibration_error,
        "number_of_bins": len(mean),
    }
    return metrics


def baseline_predictions(y_train: Any, y_rows: Any) -> np.ndarray:
    """Return the training-set smoothed answer-rate baseline."""
    y_train = np.asarray(y_train, dtype=int)
    prior_rate = (int(y_train.sum()) + 1.0) / (len(y_train) + 2.0)
    return np.full(len(y_rows), prior_rate, dtype=float)
