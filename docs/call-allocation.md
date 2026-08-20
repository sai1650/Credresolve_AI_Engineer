# Call Allocation

The allocator is the only component that creates a new outbound provider call
request. The flow is Campaign, Pacing Engine, Safety Controller, Call Allocator,
then Telecom Provider. Pacing is a soft recommendation; the allocator accepts
only a `SafetyDecision` and uses `approved_calls`, never the pacing request.

## Reservations and lifecycle

An agent is atomically reserved through the existing `Agent` mechanism. Its
state changes from `AVAILABLE` to `RESERVED` and then to `DIALING` only after
provider initiation succeeds. An account is reserved under `account_id`, which
is the operational identity because borrower identifiers are inconsistent in
the source data. An active account cannot receive another outbound call.

Created calls follow `QUEUED`, `RESERVED`, and `INITIATED`. The allocator does
not mark calls answered or connected; those states must come from provider
events later.

## Concurrency and idempotency

The prototype uses a process-local lock and atomic `Agent.reserve` operations.
Workers therefore cannot reserve the same agent or account simultaneously.
Each job has a deterministic key made from campaign, account, and allocation
window. Re-delivery returns the existing allocation and does not invoke the
provider a second time.

## Retries and crashes

If provider initiation fails, the allocator releases both agent and account so
the job can be retried safely. If initiation succeeds and the worker crashes
afterward, a later delivery finds the idempotency record instead of blindly
creating another outbound call. Reconciliation should eventually confirm the
provider lifecycle state.

## Stale reservations

`recover_stale_reservations()` uses the configured timeout to release stale
account and agent reservations. This is deliberately conservative prototype
recovery logic; production reconciliation should also verify provider state
before releasing an initiated call.

## Safety boundary

The allocator rejects malformed safety decisions, rejects unapproved predictive
fallbacks, and never increases `approved_calls`. A rejected decision or a zero
approval creates no calls. Agent availability and account eligibility are
checked again during allocation, so a stale pacing recommendation cannot turn
into an unsafe provider request. The allocator contains provider invocation
logic because it is the designated boundary, but it does not implement a
provider or let pacing and safety components invoke one.