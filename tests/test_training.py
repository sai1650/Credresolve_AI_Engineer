import json
from pathlib import Path

from app.ml.train import _load_dataset, _split, train_model

ROOT = Path(__file__).parents[1]


def test_training_preserves_chronological_splits_and_report():
    frame = _load_dataset(ROOT / "data/processed/modeling_dataset.csv")
    train, validation, test = _split(frame)
    assert train.event_at.max() < validation.event_at.min()
    assert validation.event_at.max() < test.event_at.min()


def test_training_writes_report_and_model(tmp_path: Path):
    report_path = tmp_path / "model_report.json"
    model_path = tmp_path / "model.joblib"
    report = train_model(
        ROOT / "data/processed/modeling_dataset.csv",
        model_path,
        report_path,
    )
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert model_path.exists()
    assert saved["features_used"] == report["features_used"]
    assert "roc_auc" in saved["metrics"]["test"]
    assert saved["recommendation"]
