"""Run a small deterministic Provider A/B demonstration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.providers.base import OutboundCall
from app.providers.provider_a import ProviderA
from app.providers.provider_b import ProviderB


def main() -> None:
    for provider in (
        ProviderA(seed=7, failure_probability=0.05),
        ProviderB(seed=7, failure_probability=0.15, timeout_probability=0.10),
    ):
        for index in range(20):
            call = OutboundCall(f"DEMO-{index}", f"ACCOUNT-{index}")
            response = provider.initiate_call(call)
            if response.accepted:
                provider.events_for(call, response)
        metrics = provider.metrics
        print(provider.provider_name)
        print("calls attempted", metrics.calls_attempted)
        print("accepted", metrics.accepted)
        print("failed", metrics.failed)
        print("timeouts", metrics.timeouts)
        print("average latency", metrics.average_latency_ms)
        print("duplicate events", metrics.duplicate_events)
        print("out-of-order events", metrics.out_of_order_events)


if __name__ == "__main__":
    main()
