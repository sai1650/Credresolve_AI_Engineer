from datetime import datetime, timezone

from app.providers.events import (
    CallState,
    ProviderEvent,
    ProviderEventProcessor,
)


def event(event_id: str, event_type: CallState) -> ProviderEvent:
    return ProviderEvent(
        event_id,
        "PC-1",
        "CALL-1",
        event_type,
        datetime.now(timezone.utc),
        "provider_b",
    )


def test_duplicate_event_id_is_ignored():
    processor = ProviderEventProcessor(CallState.RINGING)
    first = processor.process(event("same", CallState.ANSWERED))
    second = processor.process(event("same", CallState.ANSWERED))
    assert first.accepted and not second.accepted
    assert processor.state == CallState.ANSWERED
    assert len(processor.transitions) == 1


def test_duplicate_answered_events_only_transition_once():
    processor = ProviderEventProcessor(CallState.RINGING)
    results = processor.process_many(
        [
            event("a", CallState.ANSWERED),
            event("b", CallState.ANSWERED),
            event("c", CallState.ANSWERED),
        ]
    )
    assert sum(result.accepted for result in results) == 1
    assert processor.state == CallState.ANSWERED


def test_terminal_call_does_not_reopen_after_out_of_order_events():
    processor = ProviderEventProcessor(CallState.INITIATED)
    assert processor.process(event("complete", CallState.COMPLETED)).accepted
    processor = ProviderEventProcessor(CallState.ANSWERED)
    assert processor.process(event("complete", CallState.COMPLETED)).accepted
    assert not processor.process(event("late", CallState.RINGING)).accepted
    assert processor.state == CallState.COMPLETED


def test_invalid_transition_is_rejected_and_recorded():
    processor = ProviderEventProcessor(CallState.INITIATED)
    result = processor.process(event("bad", CallState.CONNECTED))
    assert not result.accepted
    assert "invalid" in result.reason
    assert processor.ignored_events
