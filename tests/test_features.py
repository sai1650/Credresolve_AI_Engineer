from pathlib import Path

from app.data.features import build_feature_rows
from app.data.feature_pipeline import build_modeling_dataset


def _call(
    event_id,
    event_at,
    account="A",
    campaign="C",
    vendor="V",
    outcome="NO_ANSWER",
    duration="",
):
    return {
        "event_id": event_id,
        "event_type": "CALL",
        "event_at": event_at,
        "account_id": account,
        "call_id": event_id,
        "vendor_id": vendor,
        "campaign_id": campaign,
        "outcome": outcome,
        "duration_sec": duration,
    }


def test_future_call_is_not_used_in_historical_features():
    rows, _ = build_feature_rows(
        [
            _call(
                "c2",
                "2026-01-02T00:00:00Z",
                outcome="ANSWERED",
                duration="100",
            ),
            _call("c1", "2026-01-01T00:00:00Z"),
        ]
    )
    first, second = rows
    assert first["account_answer_rate"] == 0.5
    assert first["previous_outcome"] == "UNKNOWN"
    assert second["previous_outcome"] == "NO_ANSWER"
    assert second["historical_average_talk_time_sec"] is None


def test_pipeline_is_reproducible_and_chronological(tmp_path: Path):
    source = tmp_path / "canonical.csv"
    source.write_text(
        "event_id,event_type,event_at,account_id,call_id,vendor_id,"
        "campaign_id,outcome,duration_sec\n"
        "c1,CALL,2026-01-01T00:00:00Z,A,c1,V,C,ANSWERED,10\n"
        "c2,CALL,2026-01-02T00:00:00Z,A,c2,V,C,NO_ANSWER,\n",
        encoding="utf-8",
    )
    output1, report1 = tmp_path / "one.csv", tmp_path / "one.json"
    output2, report2 = tmp_path / "two.csv", tmp_path / "two.json"
    build_modeling_dataset(source, output1, report1)
    build_modeling_dataset(source, output2, report2)
    assert output1.read_bytes() == output2.read_bytes()
    assert report1.read_bytes() == report2.read_bytes()
    assert report1.exists()


def test_canonical_outcomes_map_to_targets_and_unknowns_are_excluded():
    outcomes = ["ANSWERED", "BUSY", "FAILED", "NO_ANSWER", "VOICEMAIL"]
    rows, report = build_feature_rows(
        [_call(f"c{index}", f"2026-01-01T00:0{index}:00Z", outcome=value)
         for index, value in enumerate(outcomes)]
        + [_call("unknown", "2026-01-01T00:05:00Z", outcome="UNKNOWN")]
        + [_call("missing", "2026-01-01T00:06:00Z", outcome="")]
    )
    assert [row["answered_next_call"] for row in rows] == [1, 0, 0, 0, 0]
    assert report["unknown_outcome_rows_excluded"] == 2


def test_same_timestamp_call_does_not_enter_historical_aggregate():
    rows, _ = build_feature_rows([
        _call("b", "2026-01-01T00:00:00Z", account="B", outcome="ANSWERED"),
        _call("a", "2026-01-01T00:00:00Z", account="A", outcome="ANSWERED"),
        _call("c", "2026-01-01T00:01:00Z", account="C", outcome="NO_ANSWER"),
    ])
    assert rows[0]["campaign_answer_rate"] == 0.5
    assert rows[1]["campaign_answer_rate"] == 0.5
    assert rows[2]["campaign_answer_rate"] != 0.5
