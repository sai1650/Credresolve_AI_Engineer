# Failure Handling

The failure tests exercise the same process-local locks, provider manager,
allocator idempotency store, and event state machine used by the simulator.

## Worker crash and stale reservations

The allocator reserves the agent and account before provider initiation. If
initiation fails, both reservations are released immediately. If a worker
crashes after initiation, the idempotency record remains authoritative: a retry
returns the existing logical call and does not initiate another provider call.
`recover_stale_reservations()` releases reservations older than the configured
timeout, but production reconciliation should confirm provider state before
releasing an initiated call.

## Provider outage

Existing event streams continue through the event processor. New initiation
requests are routed only to healthy providers by `ProviderManager`; if none are
healthy, the Safety Controller can reject predictive calls or choose progressive
fallback. Provider B can receive new calls after Provider A health falls below
its threshold. Provider health does not cancel existing calls.

## Availability and answer-rate failures

The current available-agent count is the source used for each new pacing and
Safety Controller decision. A 100-to-60 drop is recalculated immediately. A
70%-to-10% observed answer-rate collapse is supplied as recent campaign behavior
against the prior predictor estimate, reducing pacing without inflating
outstanding calls.

## Duplicate and out-of-order events

Event IDs are stored and duplicate IDs are ignored. Duplicate logical ANSWERED
or COMPLETED events are rejected as invalid or terminal-state events. An
out-of-order COMPLETED is accepted as a terminal fact; later ANSWERED and
RINGING events are recorded as stale and cannot reopen the call.

## Stale state source of truth

For this prototype the locked `Agent` object and allocator reservation store are
the source of truth. A cache-like state that says RESERVED while the object says
AVAILABLE is reported as a conflict and resolves to AVAILABLE. The prototype
does not silently merge contradictory states. A production system would reconcile
against durable reservation and provider records.

## Retry storms

Ten submissions of the same campaign/account/window key produce one logical
outbound call and nine duplicate-job responses. Retries therefore remain
idempotent even when workers repeat a request after a timeout or crash.
