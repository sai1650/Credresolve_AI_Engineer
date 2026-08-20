# Safety Controller

The Safety Controller is the hard boundary between a pacing recommendation and
any later call-allocation workflow. It is independent of the predictive model,
the pacing engine, and telecom providers. Its `evaluate` method accepts a
pacing decision and a small `SafetyState`, then returns a `SafetyDecision`.

## Hard limits and actions

`PacingDecision.requested_calls` is a soft recommendation. The controller never
increases it. `approved_calls` is capped by the smallest applicable capacity:

- available agents multiplied by `max_calls_per_agent`;
- remaining global outstanding-call capacity;
- remaining campaign capacity, when supplied;
- deductions for stale reservations.

The result is one of `APPROVE`, `REDUCE`, `REJECT`, or
`FALLBACK_TO_PROGRESSIVE`. All limit values live in `SafetyLimits`, where they
can be reviewed and configured rather than hidden in calculation code.

## Provider outage and degradation

An unavailable provider or provider health below `minimum_provider_health`
causes `FALLBACK_TO_PROGRESSIVE` with zero predictive approvals. Excessive
failure rate or latency halves the otherwise safe capacity. This prevents a
provider problem from turning a pacing recommendation into a burst of failed
or outstanding work.

## Operational changes

If answer rate falls from 70% to 10%, the pacing engine may reduce its request,
but the Safety Controller still independently applies its hard limits. If 40 of
100 agents disappear, the current state is recalculated immediately: capacity
is based on the current 60 agents, not the previous 100. With zero agents,
new calls are rejected.

Ringing calls count toward outstanding load. Once the configured ringing or
outstanding limit is reached, the controller rejects additional requests.
Stale reservations are deducted until their owning workflow clears them.

## Why progressive fallback is safer

Progressive fallback is a conservative operating mode for provider distress. It
avoids approving predictive bursts while allowing a separately governed,
stepwise workflow to decide what can be attempted. The controller itself never
calls a provider, imports a provider implementation, or bypasses another safety
check. A later allocator must still pass through this boundary before placing
anything.