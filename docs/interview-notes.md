# Interview Notes

## 1. Why predictive dialing?

It uses estimated answer probability, talk time, ringing load, and agent
capacity to keep agents productive without blindly creating outstanding calls.

## 2. Why not let ML place calls?

A model estimates probability. It has no authority to enforce agent, provider,
account, campaign, or outstanding-call constraints.

## 3. Why is Safety Controller independent?

It is the auditable hard boundary. Its decision remains deterministic even when
the model is wrong, unavailable, or poorly calibrated.

## 4. How do you prevent two workers reserving one agent?

Each `Agent` has a lock. `reserve()` checks state and call ID and changes them
atomically from `AVAILABLE` to `RESERVED`.

## 5. How do you handle duplicate events?

The event processor stores processed event IDs and ignores repeats. Repeated
logical events that have different IDs are rejected when invalid for the current
state.

## 6. How do you handle out-of-order events?

An out-of-order `COMPLETED` is accepted as a terminal fact. Later events cannot
reopen the terminal call and are recorded as ignored.

## 7. What happens if a worker crashes?

After successful initiation, the idempotency record prevents blind retry. Stale
reservations can be recovered, with production reconciliation needed to confirm
provider state before releasing initiated resources.

## 8. What happens if a provider goes down?

Provider health becomes unhealthy; new work is reduced, rejected, or sent to
another healthy provider by `ProviderManager`. Existing event processing is not
cancelled by the health change.

## 9. How does progressive fallback work?

The Safety Controller can return `FALLBACK_TO_PROGRESSIVE` with zero predictive
approval. The repository implements the decision boundary, not a separate
progressive dialing execution component.

## 10. How does pacing use answer rate?

Expected answers are proposed calls multiplied by estimated answer probability.
If prediction is unavailable, pacing falls back to the supplied historical rate.

## 11. How does talk time affect pacing?

Expected agent demand multiplies expected answers by average talk time and
normalizes by the planning window. Longer talk time reduces the recommendation.

## 12. What happens when answer rate falls from 70% to 10%?

Recent campaign rate is compared with the prior estimate, reducing the pacing
factor. Scenario D also recalculates from 100 to 60 available agents and records
both reasons in the decision output.

## 13. What breaks at 1,000 agents?

The process-local reservation lock, account hot spots, provider throughput, event
processing, and metric aggregation become meaningful contention points.

## 14. What breaks at 10,000 agents?

In-memory reservations/idempotency are no longer a durable coordination layer;
event ingestion, provider rate limits, hot campaigns, and metrics need
partitioning and durable aggregation.

## 15. Why this prediction approach?

Regularized Logistic Regression is explainable and supports the prepared mixed
features. Its chronological test results were weak, so the statistical smoothed
rate estimator remains the preferred pacing input.

## 16. How did you prevent data leakage?

Historical features use only records with `event_at < T`; current outcome and
duration are excluded, as are future attempts and future external events.

## 17. Why use a time-based split?

Dialer behavior is temporal. Chronological train/validation/test partitions avoid
letting future behavior influence earlier evaluation.

## 18. What are the biggest limitations?

The system is a finite simulation with process-local state, simplified seeded
providers, incomplete agent lifecycle states, imperfect source data, and a weak
ML baseline. It is not production telecom infrastructure.
