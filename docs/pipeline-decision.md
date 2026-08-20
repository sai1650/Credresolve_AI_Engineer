# Pipeline Decision

## Current Canonical Pipeline

The authoritative path is:

```text
raw CSV
  -> app/data/normalization.py
  -> data/processed/canonical_calls.csv
  -> app/data/features.py
  -> app/data/feature_pipeline.py
  -> data/processed/modeling_dataset.csv
  -> app/ml/train.py
```

It uses canonical `event_at`, `outcome`, `account_id`, `call_id`, and
`event_id` fields. Calls are ordered by `(event_at, event_id)`. Historical
features are filtered with the strict rule `historical_event_time <
prediction_time`, including account, campaign, vendor, hourly, recent campaign,
and talk-time aggregates.

The target mapper is `target_from_outcome()` in `app/data/features.py`:

```text
ANSWERED                 -> 1
BUSY/FAILED/NO_ANSWER/VOICEMAIL -> 0
unknown or missing       -> excluded and counted in the quality report
```

## Legacy Pipeline

`app/ml/data_pipeline.py` reads raw files directly, including accounts,
campaigns, daily targeting, calls, call attempts, call dispositions, and vendor
telephony. It builds a separate raw-data model table with the target column
`target`, legacy raw feature names, and its own train/validation/test encoder.

It is not imported by application code or by `app/ml/train.py`. It remains
available because the legacy regression tests import its constants and public
functions directly.

## Dependencies

The only repository importer of the legacy module is:

```text
tests/test_data_pipeline.py
```

That test imports:

- `CATEGORICAL_FEATURES`
- `NUMERIC_FEATURES`
- `METADATA_COLUMNS`
- `build_model_table()`
- `prepare_datasets()`

No production/application module imports `app.ml.data_pipeline`.

## Differences

| Area | Canonical `app/data/` | Legacy `app/ml/data_pipeline.py` |
|---|---|---|
| Input | `canonical_calls.csv` | Multiple raw CSV datasets |
| Schema | Canonical `event_id`, `event_type`, `event_at`, `outcome` | Raw `call_status`, `attempt_status`, `disposition_code` |
| Timestamp | Timezone-aware UTC parsing | Raw timestamps normalized to naive UTC |
| Deduplication | Event ID, then deterministic CALL selection | Raw call ID and source event IDs |
| Account identity | `account_id` operational identity | Also uses `account_id` |
| Outcome | Canonical call vocabulary | Raw source status fields |
| Features | 16 canonical as-of features | Larger legacy feature set with account/targeting metadata |
| Target | `answered_next_call` | `target` |
| Unknown target | Excluded and reported by canonical mapper | Any non-`ANSWERED` value becomes `0` |
| Leakage controls | Strict filtering for all historical aggregate timestamps | Prior slicing plus incremental campaign/vendor histories |
| Output | `modeling_dataset.csv`, feature report | `train.csv`, `validation.csv`, `test.csv` |
| Tests | `test_features.py`, `test_training.py` | `test_data_pipeline.py` |

## Decision

**CONSOLIDATE_LATER**

The legacy module is not active application code, but it is still required by
existing tests and provides a distinct legacy raw-data contract. It should not be
deleted in this change. Future retirement should first migrate or replace
`tests/test_data_pipeline.py` with canonical-pipeline coverage, confirm no
external consumers, and remove the duplicate outputs deliberately.
