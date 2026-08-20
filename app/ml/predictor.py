"""Safe loading and inference for the answer-probability model."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.ml.model import FEATURE_NAMES, validate_feature_names


class AnswerProbabilityPredictor:
    def __init__(
        self, model_path: str | Path = "models/answer_probability_model.joblib"
    ) -> None:
        artifact = joblib.load(model_path)
        self.model = (
            artifact["model"] if isinstance(artifact, dict) else artifact
        )
        self.feature_names = (
            tuple(artifact.get("feature_names", FEATURE_NAMES))
            if isinstance(artifact, dict)
            else FEATURE_NAMES
        )

    def predict_probability(self, features: dict[str, Any]) -> float:
        validate_feature_names(features)
        values = {name: features[name] for name in self.feature_names}
        probability = float(
            self.model.predict_proba(pd.DataFrame([values]))[0, 1]
        )
        return min(1.0, max(0.0, probability))
