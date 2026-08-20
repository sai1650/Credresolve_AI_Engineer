"""Normalize CredResolve event streams for downstream statistics and pacing."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

EVENT_SOURCES = {
    "calls": ("call_id", "event_at", "CALL"),
    "call_attempts": ("attempt_id", "event_at", "ATTEMPT"),
    "call_dispositions": ("disposition_id", "event_at", "DISPOSITION"),
}


@dataclass(frozen=True)
class CanonicalEvent:
    event_id: str
    event_type: str
    event_at: datetime
    account_id: str
    borrower_id: str | None = None
    call_id: str | None = None
    agent_id: str | None = None
    vendor_id: str | None = None
    campaign_id: str | None = None
    outcome: str | None = None
    duration_sec: int | None = None
    attempt_no: int | None = None
    disposition_version: str | None = None
    source_schema_version: str | None = None


def _read_csv(data_dir: Path, dataset: str) -> list[dict[str, str]]:
    with (data_dir / f"{dataset}.csv").open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        return list(csv.DictReader(handle))


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _integer(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _deduplicate(
    rows: Iterable[dict[str, str]], id_column: str
) -> tuple[list[dict[str, str]], int]:
    unique: dict[str, dict[str, str]] = {}
    duplicates = 0
    for row in rows:
        event_id = row.get(id_column, "")
        if not event_id:
            continue
        if event_id in unique:
            duplicates += 1
            continue
        unique[event_id] = row
    return list(unique.values()), duplicates


def normalize_events(
    data_dir: str | Path = "data",
) -> tuple[list[CanonicalEvent], dict[str, Any]]:
    """Load calls, attempts, and dispositions as one ordered canonical stream.

    Invalid timestamps and rows without their event identifier or account are
    dropped. Duplicate event IDs are retained once, using the first source row.
    """
    data_path = Path(data_dir)
    account_rows = _read_csv(data_path, "accounts")
    account_borrowers = {
        row["account_id"]: row.get("borrower_id") or None
        for row in account_rows
        if row.get("account_id")
    }
    events: list[CanonicalEvent] = []
    report: dict[str, Any] = {
        "raw_rows": 0,
        "usable_rows": 0,
        "duplicates_removed": 0,
        "invalid_rows": 0,
        "borrower_mismatches_corrected": 0,
        "by_type": {},
    }
    for dataset, (
        id_column,
        timestamp_column,
        event_type,
    ) in EVENT_SOURCES.items():
        source_rows = _read_csv(data_path, dataset)
        report["raw_rows"] += len(source_rows)
        rows, duplicate_count = _deduplicate(source_rows, id_column)
        report["duplicates_removed"] += duplicate_count
        for row in rows:
            event_id = row.get(id_column, "")
            account_id = row.get("account_id", "")
            event_at = _parse_timestamp(row.get(timestamp_column))
            if not event_id or not account_id or event_at is None:
                report["invalid_rows"] += 1
                continue
            source_borrower = row.get("borrower_id") or None
            canonical_borrower = account_borrowers.get(
                account_id, source_borrower
            )
            if source_borrower and canonical_borrower != source_borrower:
                report["borrower_mismatches_corrected"] += 1
            events.append(
                CanonicalEvent(
                    event_id=event_id,
                    event_type=event_type,
                    event_at=event_at,
                    account_id=account_id,
                    borrower_id=canonical_borrower,
                    call_id=row.get("call_id")
                    or (row.get("call_id") if event_type == "CALL" else None),
                    agent_id=row.get("agent_id") or None,
                    vendor_id=row.get("vendor_id") or None,
                    campaign_id=row.get("campaign_id") or None,
                    outcome=(
                        row.get("call_status")
                        or row.get("attempt_status")
                        or row.get("disposition_code")
                        or None
                    ),
                    duration_sec=_integer(row.get("duration_sec")),
                    attempt_no=_integer(row.get("attempt_no")),
                    disposition_version=row.get("disposition_version") or None,
                    source_schema_version=None,
                )
            )
    events.sort(key=lambda event: (event.event_at, event.event_id))
    report["usable_rows"] = len(events)
    report["by_type"] = {
        event_type: sum(event.event_type == event_type for event in events)
        for _, _, event_type in EVENT_SOURCES.values()
    }
    return events, report


def events_as_dicts(events: Iterable[CanonicalEvent]) -> list[dict[str, Any]]:
    """Return canonical events in a serialization-friendly form."""
    return [asdict(event) for event in events]
