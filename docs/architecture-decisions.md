# Architecture Decisions

## Python

**Decision:** Use Python modules and dataclasses.

**Why:** The assignment is a deterministic data and concurrency prototype, and
Python already provides the CSV, threading, testing, and scientific libraries
used here.

**Problem solved:** Fast, readable implementation of normalization, modeling,
pacing, safety, providers, and simulation.

**Trade-offs:** Process-local state and the GIL limit production-scale
concurrency and durability.

**Alternative considered:** A distributed service architecture.

**Why alternative was rejected:** It would add infrastructure without helping
this simulation assignment.

## Current storage and data approach

**Decision:** Use repository CSV files, generated CSV/JSON artifacts, and
in-memory dictionaries/sets for runtime reservations and event IDs.

**Why:** The assignment supplies CSV data and asks for a simulation.

**Problem solved:** Reproducible historical processing and transparent reports.

**Trade-offs:** No durable transaction boundary across processes.

**Alternative considered:** PostgreSQL, Redis, Kafka, or a service database.

**Why alternative was rejected:** None exists in the repository and none is
necessary for the prototype.

## In-memory thread-safe reservations

**Decision:** Protect allocator maps with a process-local `Lock`; protect each
`Agent` with its own lock.

**Why:** Multiple worker threads must not reserve one agent or account twice.

**Problem solved:** Atomic prototype reservations and deterministic retry behavior.

**Trade-offs:** The guarantee ends at the process boundary; persistence and
cross-process leases would be needed for deployment.

**Alternative considered:** Redis/distributed locks.

**Why alternative was rejected:** Unnecessary infrastructure for this scope.

## Statistical estimator versus ML

**Decision:** Keep the statistical answer-rate estimator as the preferred pacing
input.

**Why:** The saved test report shows better log loss, Brier score, and calibration
for the smoothed rate baseline than the Logistic Regression model.

**Problem solved:** Provides a simple probability that is better calibrated on
this dataset.

**Trade-offs:** It captures less feature interaction than ML.

**Alternative considered:** Use ML as the primary pacing signal.

**Why alternative was rejected:** Offline results did not justify the added
complexity or poor calibration.

## Logistic Regression

**Decision:** Implement regularized sklearn Logistic Regression as an evaluated
offline baseline.

**Why:** It is explainable, supports mixed prepared features through imputation,
scaling, and one-hot encoding, and uses chronological splits.

**Problem solved:** Establishes a reproducible ML comparison without deep learning.

**Trade-offs:** Its measured test ROC-AUC was near random and probabilities were
poorly calibrated.

**Alternative considered:** Deep learning or random splitting.

**Why alternative was rejected:** Deep learning violates scope; random splitting
would leak temporal structure.

## Predictive pacing separation

**Decision:** Pacing returns a bounded recommendation object only.

**Why:** Utilization optimization should not have authority to create calls.

**Problem solved:** Keeps capacity estimation explainable and independently testable.

**Trade-offs:** More explicit handoff data is required.

**Alternative considered:** Let pacing call the provider directly.

**Why alternative was rejected:** It would bypass safety and allocator controls.

## Independent Safety Controller

**Decision:** Safety accepts a pacing decision and live safety state, then applies
configurable hard limits.

**Why:** Safety must remain authoritative even when model estimates are wrong.

**Problem solved:** Deterministic caps for agents, outstanding calls, provider
health, ringing load, campaigns, and stale reservations.

**Trade-offs:** Safety may reject useful but uncertain work.

**Alternative considered:** Put safety multipliers inside pacing.

**Why alternative was rejected:** Hidden coupling would make hard guarantees hard
to audit.

## Provider abstraction

**Decision:** Use `TelecomProvider`, `ProviderResponse`, `ProviderHealth`, and
`ProviderManager`.

**Why:** Allocator code should not know Provider A/B implementation details.

**Problem solved:** Health selection, failover, and provider substitution.

**Trade-offs:** The manager needs a compatibility adapter for the existing
allocator interface.

**Alternative considered:** Import Provider A and B in the allocator.

**Why alternative was rejected:** It violates the provider boundary.

## Mock providers

**Decision:** Use seeded Provider A and Provider B simulations.

**Why:** Failure, latency, duplicate, and out-of-order behavior must be testable
without network calls.

**Problem solved:** Reproducible external-system failure paths.

**Trade-offs:** The timing and traffic model are not real carrier behavior.

**Alternative considered:** Real telecom APIs.

**Why alternative was rejected:** Explicitly out of scope and unsafe for a test.

## Idempotency

**Decision:** Key jobs by campaign, account, and allocation window; retain the
existing allocation in memory.

**Why:** Retries and duplicate worker deliveries must produce one logical call.

**Problem solved:** Duplicate outbound initiation.

**Trade-offs:** The store is process-local and not durable.

**Alternative considered:** A distributed idempotency database.

**Why alternative was rejected:** Not required for the prototype.

## Out-of-order event handling

**Decision:** Store processed event IDs, validate transitions, record ignored
events, and never reopen terminal states.

**Why:** Providers can duplicate or reorder events.

**Problem solved:** Stable logical call state despite bad event delivery.

**Trade-offs:** An out-of-order terminal completion is accepted as a terminal
fact, which favors safety over reconstructing every intermediate state.

**Alternative considered:** Trust provider event order.

**Why alternative was rejected:** Provider B deliberately violates that assumption.

## Progressive fallback

**Decision:** Safety can return `FALLBACK_TO_PROGRESSIVE` when provider health is
unacceptable.

**Why:** A conservative path is safer than approving predictive bursts during an
outage.

**Problem solved:** Provider distress without disabling the safety boundary.

**Trade-offs:** Throughput drops and a separate progressive workflow would be
needed to execute fallback work.

**Alternative considered:** Let the provider decide whether to continue.

**Why alternative was rejected:** Provider implementations must not contain
safety policy.

## 100-agent simulation

**Decision:** Use configurable 100-agent, 1000-account, five-worker scenarios.

**Why:** This is the specified workload and demonstrates concurrency, pacing,
safety, allocation, provider events, and metrics together.

**Problem solved:** End-to-end verification with reproducible Scenario A-D runs.

**Trade-offs:** It is finite and simplified, not a production traffic model.

**Alternative considered:** Load-test scale in the main simulation.

**Why alternative was rejected:** Load testing is a separate layer with its own
reports and invariants.
