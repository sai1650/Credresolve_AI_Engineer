# Mock Telecom Providers

The provider layer is behind the `TelecomProvider` interface. The allocator and
provider manager consume `initiate_call`, `get_health`, and the stable response
models; they do not know Provider A or Provider B internals.

## Providers

Provider A is a fast, reliable deterministic simulation with configurable
latency, failure probability, and random seed. Its normal events are
`RINGING`, `ANSWERED`, `CONNECTED`, and `COMPLETED`.

Provider B has higher latency and configurable failures and timeouts. Its event
helper can produce duplicate `ANSWERED` events or an out-of-order
`COMPLETED`, `ANSWERED`, `RINGING` sequence for resilience tests. A supplied
seed makes both providers reproducible.

## Event processing

`ProviderEventProcessor` keeps a processed event-id store, ignores duplicate
IDs, records ignored events, validates normal state transitions, and never
reopens `COMPLETED`, `FAILED`, or `CANCELLED` calls. An out-of-order `COMPLETED`
is accepted as a terminal fact; later earlier events are recorded as stale and
ignored. Duplicate `ANSWERED` events with different IDs do not create repeated
logical transitions.

## Health and safety

Providers report health, latency, and failure rate through `ProviderHealth`.
`ProviderManager` selects the lowest-latency healthy provider and exposes health
for the Safety Controller. Provider implementations do not make pacing or
safety decisions. Existing calls continue to be processed from their events;
health affects whether later work can be initiated.

The providers are fully simulated. No real telecom API, external service, or
load-testing infrastructure is used.
