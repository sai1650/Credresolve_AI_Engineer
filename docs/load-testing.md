# Load Testing

This load layer is a process-local simulation of allocator contention. It uses
100 agents, 1000 accounts, and configurable worker counts of 5, 10, 20, and 50.
No network, queue, cache, or external service is used.

## Concurrency model

Workers share one `CallAllocator`, its lock-protected agent/account reservation
store, and its idempotency store. Each worker receives a partition of the
approved quota. Repeated workers submit the same deterministic job keys, so a
retry or duplicate delivery returns the existing allocation instead of creating
another provider request.

The report measures allocation attempts, unique successful calls, duplicate job
responses, agent/account contention, latency, p95 latency, throughput, failures,
recovery time, and invariant violations. It is written to
`data/processed/load_test_report.json` by `run_load_matrix()`.

## Guarantees checked

The load test fails immediately if any of these is violated:

- `created_calls <= approved_calls`
- `created_calls <= available_agent_capacity`
- active agent IDs are unique
- deterministic duplicate jobs do not create duplicate call IDs

The prototype uses process-local locks. A multi-process deployment would require
an external transactional reservation/idempotency store, which is intentionally
outside this assignment.

## Scale analysis

At 100 agents, lock contention and provider initiation dominate short runs.
At 1,000 agents, the shared reservation lock and account-key hot spots become
more visible; sharding reservations by agent/account hash would reduce waiting.
At 10,000 agents, event processing, provider throughput, idempotency persistence,
metrics aggregation, and hot campaign partitions become the likely bottlenecks.
A practical design would use partitioned durable storage, batch event ingestion,
per-partition counters, and provider-specific rate limits. Simply adding worker
threads would increase contention without solving those bottlenecks.

## Commands

```text
python -m app.simulation.load_test
python -m pytest -q tests/test_load.py
```
