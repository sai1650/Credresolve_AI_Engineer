# SmartDialer Simulation

This is a deterministic prototype simulation, not a representation of real
telecom traffic. It makes no phone calls and uses only mock Provider A and
Provider B implementations.

## Workload and workers

The default configuration is 100 agents, 1000 accounts, and 5 concurrent
workers. These values are configurable through `SimulationConfig`. Workers
share the allocator reservation store. Approved call quotas are partitioned
across workers so the aggregate cannot exceed the Safety Controller approval.

## Flow

Each phase selects eligible accounts, asks the Predictive Pacing Engine for a
recommendation, sends that recommendation and live provider state to the Safety
Controller, and sends only the approved count to the Call Allocator. The
allocator routes initiation through ProviderManager. Provider events are then
processed by the event state machine and metrics are collected.

## Scenarios

- A uses a 20% answer rate and 120-second talk time.
- B uses a 50% answer rate and 90-second talk time.
- C uses a 70% answer rate and 180-second talk time.
- D starts at 70%, changes observed campaign answer rate to 10%, reduces
  available agents from 100 to 60, and uses degraded provider conditions.

Answer outcomes are deterministic from call IDs and the configured scenario
rate. Talk time is the scenario input for connected calls. Provider failures,
latency, duplicate events, and out-of-order events come from the seeded mock
providers and event processor.

## Utilization

Agent utilization is calculated as:

`seconds agents spend CONNECTED / total available agent seconds`

The simulation uses a 300-second planning window for each available agent.
Connected seconds are accumulated from accepted `CONNECTED` event transitions;
no utilization value is fabricated.

## Metrics and invariants

The metrics include initiated, connected, completed, failed, answer rate, talk
time, utilization, ringing load, pacing decisions, safety actions, provider
failures and latency, duplicate/out-of-order events, allocation failures, and
stale recovery counts.

Every phase checks:

- `approved_calls <= safe_capacity`
- `created_calls <= approved_calls`
- `created_calls <= available_agent_capacity`

A violation raises an error immediately.

## Reproducibility and limitations

Run with `--seed 42` for reproducible provider outcomes. This prototype uses
process-local locks, a finite synthetic workload, simplified answer outcomes,
and a short planning window. It does not model real carrier routing, network
jitter, agent wrap-up, contact policies, or production persistence. It is for
architecture and failure-path verification only.

## Commands

```text
python scripts/run_simulation.py
python scripts/run_simulation.py --scenario A
python scripts/run_simulation.py --scenario B
python scripts/run_simulation.py --scenario C
python scripts/run_simulation.py --scenario D
python scripts/run_simulation.py --all --seed 42
```
