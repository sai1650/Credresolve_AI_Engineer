"""Build leakage-safe, time-split training data from the supplied CSV files."""

from __future__ import annotations

import csv
import math
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_DATASETS = (
    "accounts",
    "campaigns",
    "daily_targeting",
    "calls",
    "call_attempts",
    "call_dispositions",
    "vendor_telephony",
)
TRAIN_END = datetime(2026, 6, 1)
VALIDATION_END = datetime(2026, 7, 1)
CATEGORICAL_FEATURES = (
    "loan_type",
    "account_timezone",
    "campaign_id",
    "campaign_channel",
    "strategy_version",
    "target_definition",
    "vendor_id",
    "vendor_timezone",
    "call_timezone",
    "recommended_channel",
)
NUMERIC_FEATURES = (
    "principal_amount",
    "account_age_days",
    "target_priority",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "previous_call_count",
    "previous_answered_count",
    "previous_answer_rate",
    "previous_average_duration_sec",
    "previous_attempt_count",
    "previous_connected_attempt_count",
    "previous_disposition_count",
    "previous_ptp_count",
    "campaign_previous_call_count",
    "campaign_previous_answer_rate",
    "vendor_previous_call_count",
    "vendor_previous_answer_rate",
)
METADATA_COLUMNS = ("call_id", "event_at", "target")


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
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _number(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def _first_by_key(
    rows: list[dict[str, str]], key: str
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        if value and value not in result:
            result[value] = row
    return result


def _deduplicate_calls(
    rows: list[dict[str, str]],
) -> tuple[list[tuple[datetime, dict[str, str]]], int, int]:
    grouped: dict[str, list[tuple[datetime, dict[str, str]]]] = defaultdict(
        list
    )
    invalid_timestamps = 0
    for row in rows:
        event_at = _parse_timestamp(row.get("event_at"))
        if event_at is None or not row.get("call_id"):
            invalid_timestamps += 1
            continue
        grouped[row["call_id"]].append((event_at, row))
    deduplicated: list[tuple[datetime, dict[str, str]]] = []
    duplicate_count = 0
    for call_rows in grouped.values():
        call_rows.sort(key=lambda item: (item[0], tuple(item[1].values())))
        deduplicated.append(call_rows[0])
        duplicate_count += len(call_rows) - 1
    deduplicated.sort(key=lambda item: (item[0], item[1]["call_id"]))
    return deduplicated, duplicate_count, invalid_timestamps


def _historical_events(
    rows: list[dict[str, str]], timestamp_column: str, deduplicate_key: str
) -> dict[str, list[tuple[datetime, dict[str, str]]]]:
    grouped: dict[str, list[tuple[datetime, dict[str, str]]]] = defaultdict(
        list
    )
    seen: set[str] = set()
    for row in rows:
        event_at = _parse_timestamp(row.get(timestamp_column))
        account_id = row.get("account_id", "")
        event_id = row.get(deduplicate_key, "")
        if (
            event_at is None
            or not account_id
            or (event_id and event_id in seen)
        ):
            continue
        if event_id:
            seen.add(event_id)
        grouped[account_id].append((event_at, row))
    for events in grouped.values():
        events.sort(key=lambda item: item[0])
    return grouped


def _prior_events(
    events: list[tuple[datetime, dict[str, str]]], event_at: datetime
) -> list[dict[str, str]]:
    timestamps = [item[0] for item in events]
    return [row for _, row in events[: bisect_left(timestamps, event_at)]]


def _rate(successes: int, total: int) -> float | None:
    return successes / total if total else None


def build_model_table(
    data_dir: str | Path = "data",
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Create one pre-call feature row for each usable, deduplicated call."""
    data_path = Path(data_dir)
    loaded = {
        dataset: _read_csv(data_path, dataset) for dataset in REQUIRED_DATASETS
    }
    calls, duplicate_count, invalid_call_timestamps = _deduplicate_calls(
        loaded["calls"]
    )
    accounts = _first_by_key(loaded["accounts"], "account_id")
    campaigns = _first_by_key(loaded["campaigns"], "campaign_id")
    vendors = _first_by_key(loaded["vendor_telephony"], "vendor_id")
    targets: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in loaded["daily_targeting"]:
        key = (
            row.get("account_id", ""),
            row.get("campaign_id", ""),
            row.get("target_date", ""),
        )
        if all(key) and key not in targets:
            targets[key] = row
    attempt_events = _historical_events(
        loaded["call_attempts"], "event_at", "attempt_id"
    )
    disposition_events = _historical_events(
        loaded["call_dispositions"], "event_at", "disposition_id"
    )
    calls_by_account: dict[str, list[tuple[datetime, dict[str, str]]]] = (
        defaultdict(list)
    )
    for event_at, row in calls:
        calls_by_account[row.get("account_id", "")].append((event_at, row))
    campaign_history: dict[str, list[tuple[datetime, bool]]] = defaultdict(
        list
    )
    vendor_history: dict[str, list[tuple[datetime, bool]]] = defaultdict(list)
    model_rows: list[dict[str, Any]] = []
    for event_at, call in calls:
        account_id, campaign_id, vendor_id = (
            call.get("account_id", ""),
            call.get("campaign_id", ""),
            call.get("vendor_id", ""),
        )
        account, campaign, vendor = (
            accounts.get(account_id, {}),
            campaigns.get(campaign_id, {}),
            vendors.get(vendor_id, {}),
        )
        prior_calls = _prior_events(calls_by_account[account_id], event_at)
        prior_attempts = _prior_events(
            attempt_events.get(account_id, []), event_at
        )
        prior_dispositions = _prior_events(
            disposition_events.get(account_id, []), event_at
        )
        prior_campaign = campaign_history[campaign_id]
        prior_vendor = vendor_history[vendor_id]
        opened_at = _parse_timestamp(account.get("opened_at"))
        target_row = targets.get(
            (account_id, campaign_id, event_at.date().isoformat()), {}
        )
        durations = [_number(row.get("duration_sec")) for row in prior_calls]
        durations = [
            duration for duration in durations if duration is not None
        ]
        previous_answered = sum(
            row.get("call_status") == "ANSWERED" for row in prior_calls
        )
        connected_attempts = sum(
            row.get("attempt_status") == "CONNECTED" for row in prior_attempts
        )
        ptp_dispositions = sum(
            row.get("disposition_code") in {"PTP", "PROMISE_TO_PAY"}
            for row in prior_dispositions
        )
        model_rows.append(
            {
                "call_id": call["call_id"],
                "event_at": event_at.isoformat(sep=" "),
                "target": int(call.get("call_status") == "ANSWERED"),
                "loan_type": account.get("loan_type"),
                "account_timezone": account.get("timezone"),
                "principal_amount": _number(account.get("principal_amount")),
                "account_age_days": (
                    (event_at - opened_at).days if opened_at else None
                ),
                "campaign_id": campaign_id,
                "campaign_channel": campaign.get("channel"),
                "strategy_version": campaign.get("strategy_version"),
                "target_definition": campaign.get("target_definition"),
                "vendor_id": vendor_id,
                "vendor_timezone": vendor.get("timezone"),
                "call_timezone": call.get("timezone"),
                "target_priority": _number(target_row.get("priority")),
                "recommended_channel": target_row.get("recommended_channel"),
                "hour_of_day": event_at.hour,
                "day_of_week": event_at.weekday(),
                "is_weekend": int(event_at.weekday() >= 5),
                "previous_call_count": len(prior_calls),
                "previous_answered_count": previous_answered,
                "previous_answer_rate": _rate(
                    previous_answered, len(prior_calls)
                ),
                "previous_average_duration_sec": (
                    sum(durations) / len(durations) if durations else None
                ),
                "previous_attempt_count": len(prior_attempts),
                "previous_connected_attempt_count": connected_attempts,
                "previous_disposition_count": len(prior_dispositions),
                "previous_ptp_count": ptp_dispositions,
                "campaign_previous_call_count": len(prior_campaign),
                "campaign_previous_answer_rate": _rate(
                    sum(item[1] for item in prior_campaign),
                    len(prior_campaign),
                ),
                "vendor_previous_call_count": len(prior_vendor),
                "vendor_previous_answer_rate": _rate(
                    sum(item[1] for item in prior_vendor), len(prior_vendor)
                ),
            }
        )
        answered = call.get("call_status") == "ANSWERED"
        campaign_history[campaign_id].append((event_at, answered))
        vendor_history[vendor_id].append((event_at, answered))
    quality = {
        "raw_call_rows": len(loaded["calls"]),
        "usable_rows": len(model_rows),
        "duplicate_call_rows_removed": duplicate_count,
        "invalid_call_timestamps": invalid_call_timestamps,
        "raw_source_rows": sum(len(rows) for rows in loaded.values()),
    }
    return model_rows, quality


def _fit_transform(
    train_rows: list[dict[str, Any]], rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    medians: dict[str, float] = {}
    for feature in NUMERIC_FEATURES:
        values = sorted(
            float(row[feature])
            for row in train_rows
            if row.get(feature) is not None
        )
        medians[feature] = values[len(values) // 2] if values else 0.0
    categories = {
        feature: sorted(
            {str(row.get(feature) or "__MISSING__") for row in train_rows}
        )
        for feature in CATEGORICAL_FEATURES
    }
    feature_names = list(NUMERIC_FEATURES)
    for feature in CATEGORICAL_FEATURES:
        feature_names.extend(
            f"{feature}__{value}" for value in categories[feature]
        )
    transformed: list[dict[str, Any]] = []
    for row in rows:
        output = {column: row[column] for column in METADATA_COLUMNS}
        for feature in NUMERIC_FEATURES:
            output[feature] = (
                medians[feature] if row.get(feature) is None else row[feature]
            )
        for feature in CATEGORICAL_FEATURES:
            value = str(row.get(feature) or "__MISSING__")
            for category in categories[feature]:
                output[f"{feature}__{category}"] = int(value == category)
        transformed.append(output)
    return transformed, feature_names


def _write_csv(
    path: Path, rows: list[dict[str, Any]], columns: list[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def prepare_datasets(
    data_dir: str | Path = "data", output_dir: str | Path = "data/processed"
) -> dict[str, Any]:
    """Build and save train, validation, and test CSVs."""
    rows, quality = build_model_table(data_dir)
    train_rows = [
        row for row in rows if _parse_timestamp(row["event_at"]) < TRAIN_END
    ]
    validation_rows = [
        row
        for row in rows
        if TRAIN_END <= _parse_timestamp(row["event_at"]) < VALIDATION_END
    ]
    test_rows = [
        row
        for row in rows
        if _parse_timestamp(row["event_at"]) >= VALIDATION_END
    ]
    encoded_train, feature_names = _fit_transform(train_rows, train_rows)
    encoded_validation, _ = _fit_transform(train_rows, validation_rows)
    encoded_test, _ = _fit_transform(train_rows, test_rows)
    columns = list(METADATA_COLUMNS) + feature_names
    output_path = Path(output_dir)
    _write_csv(output_path / "train.csv", encoded_train, columns)
    _write_csv(output_path / "validation.csv", encoded_validation, columns)
    _write_csv(output_path / "test.csv", encoded_test, columns)
    target_distribution = Counter(row["target"] for row in rows)
    missing_values = {
        feature: sum(row.get(feature) is None for row in rows)
        for feature in (*NUMERIC_FEATURES, *CATEGORICAL_FEATURES)
        if any(row.get(feature) is None for row in rows)
    }
    report = {
        **quality,
        "number_of_features": len(feature_names),
        "target_distribution": dict(target_distribution),
        "train_size": len(train_rows),
        "validation_size": len(validation_rows),
        "test_size": len(test_rows),
        "missing_values_before_imputation": missing_values,
        "date_ranges": {
            split: (
                (split_rows[0]["event_at"], split_rows[-1]["event_at"])
                if split_rows
                else None
            )
            for split, split_rows in (
                ("train", train_rows),
                ("validation", validation_rows),
                ("test", test_rows),
            )
        },
    }
    _print_report(report)
    return report


def _print_report(report: dict[str, Any]) -> None:
    print("SmartDialer data-quality report")
    for key in (
        "raw_call_rows",
        "usable_rows",
        "number_of_features",
        "target_distribution",
        "train_size",
        "validation_size",
        "test_size",
        "missing_values_before_imputation",
        "date_ranges",
        "duplicate_call_rows_removed",
    ):
        print(f"{key}: {report[key]}")


if __name__ == "__main__":
    prepare_datasets()
