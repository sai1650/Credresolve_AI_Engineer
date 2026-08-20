"""Provider event models and a defensive call-state event processor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class CallState(str, Enum):
    QUEUED = "QUEUED"
    RESERVED = "RESERVED"
    INITIATED = "INITIATED"
    RINGING = "RINGING"
    ANSWERED = "ANSWERED"
    CONNECTED = "CONNECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class ProviderEvent:
    event_id: str
    provider_call_id: str
    call_id: str
    event_type: CallState
    event_time: datetime
    provider_name: str
    sequence_number: int | None = None


@dataclass(frozen=True)
class EventProcessResult:
    accepted: bool
    state: CallState
    reason: str


class ProviderEventProcessor:
    """Deduplicate events and never reopen terminal calls."""

    _normal = {
        CallState.QUEUED: {CallState.RESERVED, CallState.CANCELLED},
        CallState.RESERVED: {CallState.INITIATED, CallState.CANCELLED},
        CallState.INITIATED: {CallState.RINGING, CallState.FAILED},
        CallState.RINGING: {CallState.ANSWERED, CallState.FAILED},
        CallState.ANSWERED: {CallState.CONNECTED, CallState.COMPLETED},
        CallState.CONNECTED: {CallState.COMPLETED},
    }
    _terminal = {CallState.COMPLETED, CallState.FAILED, CallState.CANCELLED}

    def __init__(self, initial_state: CallState = CallState.INITIATED) -> None:
        self.state = initial_state
        self.processed_event_ids: set[str] = set()
        self.ignored_events: list[tuple[str, str]] = []
        self.transitions: list[tuple[CallState, CallState]] = []

    def process(self, event: ProviderEvent) -> EventProcessResult:
        if event.event_id in self.processed_event_ids:
            self.ignored_events.append((event.event_id, "duplicate event_id"))
            return EventProcessResult(
                False, self.state, "duplicate event_id ignored"
            )
        self.processed_event_ids.add(event.event_id)
        if self.state in self._terminal:
            self.ignored_events.append((event.event_id, "terminal state"))
            return EventProcessResult(
                False, self.state, "terminal call cannot reopen"
            )
        if event.event_type == CallState.COMPLETED:
            previous = self.state
            self.state = CallState.COMPLETED
            self.transitions.append((previous, self.state))
            return EventProcessResult(
                True, self.state, "out-of-order terminal event accepted"
            )
        if event.event_type not in self._normal.get(self.state, set()):
            self.ignored_events.append((event.event_id, "invalid transition"))
            return EventProcessResult(
                False, self.state, "invalid call-state transition"
            )
        previous = self.state
        self.state = event.event_type
        self.transitions.append((previous, self.state))
        return EventProcessResult(True, self.state, "transition accepted")

    def process_many(
        self, events: list[ProviderEvent]
    ) -> list[EventProcessResult]:
        return [self.process(event) for event in events]


def make_event(
    event_id: str,
    call_id: str,
    event_type: CallState,
    provider_name: str,
    provider_call_id: str = "",
) -> ProviderEvent:
    return ProviderEvent(
        event_id,
        provider_call_id or call_id,
        call_id,
        event_type,
        datetime.now(timezone.utc),
        provider_name,
    )
