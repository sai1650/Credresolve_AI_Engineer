"""Model contract and sklearn pipeline for answer-probability estimation."""

from __future__ import annotations

from typing import Any

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

TARGET = "answered_next_call"
METADATA_COLUMNS = {"account_id", "event_at", TARGET}
FORBIDDEN_COLUMNS = {
    "outcome",
    "duration_sec",
    "current_outcome",
    "current_duration",
    "disposition",
    "call_disposition",
    "call_status",
}
CATEGORICAL_FEATURES = ("previous_outcome", "campaign_id", "vendor_id")
NUMERIC_FEATURES = (
    "previous_attempt_count",
    "time_since_previous_call_sec",
    "account_answer_rate",
    "campaign_answer_rate",
    "vendor_answer_rate",
    "hour_answer_rate",
    "recent_campaign_answer_rate",
    "historical_average_talk_time_sec",
    "campaign_average_talk_time_sec",
    "vendor_average_talk_time_sec",
    "attempt_no",
    "hour_of_day",
    "day_of_week",
)
FEATURE_NAMES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
RANDOM_STATE = 42


def make_model(
    class_weight: str | dict[int, float] | None = "balanced",
) -> Pipeline:
    numeric = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preprocessing = ColumnTransformer(
        [
            ("numeric", numeric, list(NUMERIC_FEATURES)),
            ("categorical", categorical, list(CATEGORICAL_FEATURES)),
        ]
    )
    return Pipeline(
        [
            ("preprocessing", preprocessing),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight=class_weight,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def validate_feature_names(features: dict[str, Any]) -> None:
    supplied = set(features)
    forbidden = supplied & FORBIDDEN_COLUMNS
    if forbidden:
        raise ValueError(
            f"post-call fields are not accepted: {sorted(forbidden)}"
        )
    missing = set(FEATURE_NAMES) - supplied
    if missing:
        raise ValueError(f"missing required features: {sorted(missing)}")
