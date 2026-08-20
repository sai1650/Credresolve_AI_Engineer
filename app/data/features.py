"""Leakage-safe historical features from the canonical call event stream."""

from __future__ import annotations

import csv
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ANSWERED = "ANSWERED"
UNKNOWN = "UNKNOWN"
VALID_CALL_OUTCOMES = frozenset(
    {"ANSWERED", "BUSY", "FAILED", "NO_ANSWER", "VOICEMAIL"}
)
DEFAULT_PRIOR_RATE = 0.5
SMOOTHING_ALPHA = 5.0
RECENT_CAMPAIGN_WINDOW = timedelta(days=30)

FEATURE_NAMES = (
    "previous_attempt_count",
    "time_since_previous_call_sec",
    "previous_outcome",
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
    "campaign_id",
    "vendor_id",
)
OUTPUT_COLUMNS = (
    "account_id",
    "event_at",
    "answered_next_call",
    *FEATURE_NAMES,
)


def target_from_outcome(outcome: Any) -> int | None:
    """Map a valid canonical call outcome to a supervised target."""
    if outcome in (None, ""):
        return None
    normalized = str(outcome).strip().upper()
    if normalized not in VALID_CALL_OUTCOMES:
        return None
    return int(normalized == ANSWERED)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _value(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    return str(value).strip() if value not in (None, "") else UNKNOWN


def _duration(row: dict[str, Any]) -> float | None:
    try:
        value = float(row.get("duration_sec", ""))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _rate(successes: int, total: int, prior: float) -> float:
    return (successes + SMOOTHING_ALPHA * prior) / (total + SMOOTHING_ALPHA)


def _deduplicate(
    rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    events: dict[str, dict[str, Any]] = {}
    removed = 0
    for row in rows:
        event_id = _value(row, "event_id")
        if event_id == UNKNOWN or event_id in events:
            removed += 1
            continue
        events[event_id] = row
    calls: dict[str, dict[str, Any]] = {}
    for row in events.values():
        if _value(row, "event_type") != "CALL":
            continue
        call_id = _value(row, "call_id")
        event_time = _parse_time(row.get("event_at"))
        if call_id == UNKNOWN or event_time is None:
            continue
        previous = calls.get(call_id)
        previous_time = (
            _parse_time(previous.get("event_at")) if previous else None
        )
        if previous is None or (event_time, _value(row, "event_id")) < (
            previous_time,
            _value(previous, "event_id"),
        ):
            if previous is not None:
                removed += 1
            calls[call_id] = row
        else:
            removed += 1
    usable = [
        row for row in calls.values() if _value(row, "account_id") != UNKNOWN
    ]
    usable.sort(
        key=lambda row: (_parse_time(row["event_at"]), _value(row, "event_id"))
    )
    return usable, removed


def build_feature_rows(
    rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build one row per CALL using only events with ``event_at < T``."""
    all_rows = list(rows)
    calls, duplicates_removed = _deduplicate(all_rows)
    attempts = [
        row
        for row in all_rows
        if _value(row, "event_type") == "ATTEMPT"
        and _parse_time(row.get("event_at")) is not None
    ]
    attempts.sort(
        key=lambda row: (_parse_time(row["event_at"]), _value(row, "event_id"))
    )
    attempt_index = 0
    attempt_counts: defaultdict[str, int] = defaultdict(int)
    account_history: defaultdict[str, list[tuple[Any, ...]]] = defaultdict(
        list
    )
    campaign_history: defaultdict[str, list[tuple[Any, ...]]] = defaultdict(
        list
    )
    vendor_history: defaultdict[str, list[tuple[Any, ...]]] = defaultdict(list)
    hour_history: defaultdict[int, list[tuple[datetime, bool]]] = defaultdict(
        list
    )
    recent_campaign: defaultdict[str, deque[tuple[datetime, bool]]] = (
        defaultdict(deque)
    )
    total_calls = total_answered = rows_without_history = 0
    pending_calls = pending_answered = 0
    last_event_time: datetime | None = None
    unknown_outcome_rows = 0
    feature_rows: list[dict[str, Any]] = []
    for call in calls:
        event_time = _parse_time(call["event_at"])
        if last_event_time != event_time:
            total_calls += pending_calls
            total_answered += pending_answered
            pending_calls = pending_answered = 0
            last_event_time = event_time
        account_id, campaign_id, vendor_id = (
            _value(call, key)
            for key in ("account_id", "campaign_id", "vendor_id")
        )
        while (
            attempt_index < len(attempts)
            and _parse_time(attempts[attempt_index]["event_at"]) < event_time
        ):
            attempt_counts[_value(attempts[attempt_index], "account_id")] += 1
            attempt_index += 1
        global_prior = _rate(total_answered, total_calls, DEFAULT_PRIOR_RATE)
        account_prior, campaign_prior, vendor_prior = (
            account_history[account_id],
            campaign_history[campaign_id],
            vendor_history[vendor_id],
        )
        current_recent = recent_campaign[campaign_id]
        while (
            current_recent
            and current_recent[0][0] < event_time - RECENT_CAMPAIGN_WINDOW
        ):
            current_recent.popleft()

        def history_rate(history: list[tuple[Any, ...]]) -> float:
            return _rate(
                sum(item[1] for item in history), len(history), global_prior
            )

        def duration_average(history: list[tuple[Any, ...]]) -> float | None:
            durations = [item[2] for item in history if item[2] is not None]
            return sum(durations) / len(durations) if durations else None

        account_prior = [
            item for item in account_prior if item[0] < event_time
        ]
        campaign_prior = [
            item for item in campaign_prior if item[0] < event_time
        ]
        vendor_prior = [
            item for item in vendor_prior if item[0] < event_time
        ]
        previous = account_prior[-1] if account_prior else None
        target = target_from_outcome(call.get("outcome"))
        if target is None:
            unknown_outcome_rows += 1
            continue
        rows_without_history += int(
            not account_prior and attempt_counts[account_id] == 0
        )
        feature_rows.append(
            {
                "account_id": account_id,
                "event_at": event_time.isoformat(),
                "answered_next_call": target,
                "previous_attempt_count": attempt_counts[account_id],
                "time_since_previous_call_sec": (
                    (event_time - previous[0]).total_seconds()
                    if previous
                    else None
                ),
                "previous_outcome": (
                    _value(previous[3], "outcome") if previous else UNKNOWN
                ),
                "account_answer_rate": history_rate(account_prior),
                "campaign_answer_rate": history_rate(campaign_prior),
                "vendor_answer_rate": history_rate(vendor_prior),
                "hour_answer_rate": _rate(
                    sum(
                        item[1]
                        for item in hour_history[event_time.hour]
                        if item[0] < event_time
                    ),
                    sum(
                        item[0] < event_time
                        for item in hour_history[event_time.hour]
                    ),
                    global_prior,
                ),
                "recent_campaign_answer_rate": _rate(
                    sum(
                        item[1]
                        for item in current_recent
                        if item[0] < event_time
                    ),
                    sum(item[0] < event_time for item in current_recent),
                    global_prior,
                ),
                "historical_average_talk_time_sec": duration_average(
                    account_prior
                ),
                "campaign_average_talk_time_sec": duration_average(
                    campaign_prior
                ),
                "vendor_average_talk_time_sec": duration_average(vendor_prior),
                "attempt_no": attempt_counts[account_id] + 1,
                "hour_of_day": event_time.hour,
                "day_of_week": event_time.weekday(),
                "campaign_id": campaign_id,
                "vendor_id": vendor_id,
            }
        )
        answered, duration = _value(
            call, "outcome"
        ).upper() == ANSWERED, _duration(call)
        history_item = (event_time, answered, duration, call)
        account_history[account_id].append(history_item)
        campaign_history[campaign_id].append(history_item)
        vendor_history[vendor_id].append(history_item)
        hour_history[event_time.hour].append((event_time, answered))
        current_recent.append((event_time, answered))
        pending_calls += 1
        pending_answered += int(answered)
    return feature_rows, {
        "duplicates_removed": duplicates_removed,
        "rows_without_historical_information": rows_without_history,
        "input_rows": len(all_rows),
        "usable_rows": len(feature_rows),
        "unknown_outcome_rows_excluded": unknown_outcome_rows,
    }


def read_canonical_calls(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))
