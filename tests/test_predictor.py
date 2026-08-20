from pathlib import Path

import pytest

from app.ml.model import FEATURE_NAMES
from app.ml.predictor import AnswerProbabilityPredictor

ROOT = Path(__file__).parents[1]


def _features() -> dict[str, object]:
    values = {name: 0 for name in FEATURE_NAMES}
    values.update(
        {
            "previous_outcome": "UNKNOWN",
            "campaign_id": "CMP0000001",
            "vendor_id": "VND0000001",
        }
    )
    return values


def test_probability_is_bounded_and_deterministic():
    predictor = AnswerProbabilityPredictor(
        ROOT / "models/answer_probability_model.joblib"
    )
    features = _features()
    first = predictor.predict_probability(features)
    second = predictor.predict_probability(features)
    assert 0.0 <= first <= 1.0
    assert first == second


def test_missing_required_feature_is_clear():
    predictor = AnswerProbabilityPredictor(
        ROOT / "models/answer_probability_model.joblib"
    )
    features = _features()
    del features["campaign_id"]
    with pytest.raises(ValueError, match="missing required features"):
        predictor.predict_probability(features)


def test_post_call_fields_are_rejected():
    predictor = AnswerProbabilityPredictor(
        ROOT / "models/answer_probability_model.joblib"
    )
    features = _features()
    features["duration_sec"] = 12
    with pytest.raises(ValueError, match="post-call fields"):
        predictor.predict_probability(features)
