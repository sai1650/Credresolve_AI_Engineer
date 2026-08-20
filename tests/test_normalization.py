from datetime import timezone
from pathlib import Path

from app.data.normalization import normalize_events

ROOT = Path(__file__).parents[1]


def test_normalization_builds_one_ordered_stream_from_real_events() -> None:
    events, report = normalize_events(ROOT / "data")

    assert report["raw_rows"] == 246350
    assert report["usable_rows"] == 245000
    assert report["duplicates_removed"] == 1350
    assert {event.event_type for event in events} == {
        "CALL",
        "ATTEMPT",
        "DISPOSITION",
    }
    assert events == sorted(
        events, key=lambda event: (event.event_at, event.event_id)
    )
    assert all(event.event_at.tzinfo == timezone.utc for event in events)


def test_account_borrower_mapping_is_canonical() -> None:
    events, report = normalize_events(ROOT / "data")

    assert report["borrower_mismatches_corrected"] > 0
    account_to_borrower = {}
    for event in events:
        if event.account_id in account_to_borrower:
            assert event.borrower_id == account_to_borrower[event.account_id]
        else:
            account_to_borrower[event.account_id] = event.borrower_id


def test_event_fields_are_mapped_by_source() -> None:
    events, _ = normalize_events(ROOT / "data")

    call = next(event for event in events if event.event_type == "CALL")
    attempt = next(event for event in events if event.event_type == "ATTEMPT")
    disposition = next(
        event for event in events if event.event_type == "DISPOSITION"
    )
    assert call.outcome in {
        "ANSWERED",
        "BUSY",
        "FAILED",
        "NO_ANSWER",
        "VOICEMAIL",
    }
    assert attempt.attempt_no is not None
    assert disposition.disposition_version in {"v1", "v2", "legacy"}
