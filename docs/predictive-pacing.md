# Predictive Pacing

The predictive pacing engine recommends a number of calls for the next planning
window. It does not place calls, reserve agents, authorize accounts, or invoke a
telephony provider.

## Inputs and calculation

The engine receives available agents, connected calls, ringing calls, estimated
and historical answer rates, average talk time, recent call volume, provider
health signals, optional campaign behavior, and recent availability context.

It estimates demand using:

`expected_answers = requested_calls * answer_probability`

`expected_agent_demand = expected_answers * average_talk_time / planning_window`

The recommendation is bounded by available capacity, an outstanding-call limit,
recent volume, and a configurable maximum. The default planning window is 300
seconds, target utilization is 85%, and the outstanding limit is two calls per
available agent. These are configuration values, not hidden provider rules.

## Adjustments

Ringing and connected calls consume outstanding capacity. Provider health,
latency, and failure rate multiply the recommendation down. A sudden fall in
campaign answer rate also reduces it, as does a sharp drop in available agents.
When no model probability is available, the engine uses the supplied smoothed
historical rate and marks `fallback_recommended` true. Confidence is reduced for
that fallback and for poor provider health.

## Leakage Prevention

The canonical feature path is `app/data/normalization.py` ->
`app/data/features.py` -> `app/data/feature_pipeline.py`.

For a prediction at time `T`, every historical feature source must satisfy:

```text
historical_event_time < T
```

This applies to previous attempts, previous outcome, account/campaign/vendor
answer rates, hourly and recent campaign rates, and all historical talk-time
averages. Current outcome, current duration, current disposition, current
attempt status, future calls, future attempts, future dispositions, payments,
complaints, promises, account-status updates, and post-decision targeting data
are excluded from the canonical feature path.

Canonical calls are ordered deterministically by `(event_at, event_id)`, but
same-timestamp records are still excluded from historical aggregates rather than
being treated as earlier merely because of the secondary key. The secondary key
only makes output ordering reproducible.

The target is generated in the same canonical feature path. `ANSWERED` maps to
`1`; `BUSY`, `FAILED`, `NO_ANSWER`, and `VOICEMAIL` map to `0`. Unknown or
missing outcomes are excluded from supervised rows and counted in the feature
quality report instead of being silently treated as non-answers.

## Safety boundary

The output is only a `PacingDecision` recommendation. For example,
`requested_calls=17` means the engine suggests 17 calls; it does not mean 17
calls are allowed. A separate Safety Controller must independently apply account
limits, consent rules, duplicate protections, and other policy checks before any
allocation. Keeping that boundary prevents pacing logic from bypassing safety
controls and keeps the engine testable and provider-independent.