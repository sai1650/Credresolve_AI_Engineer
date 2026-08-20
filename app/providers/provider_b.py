"""Deterministic unreliable mock provider for resilience testing."""

from __future__ import annotations

import random

from app.providers.base import (
    OutboundCall,
    ProviderHealth,
    ProviderResponse,
    TelecomProvider,
    utc_now,
)
from app.providers.provider_a import ProviderMetrics
from app.providers.events import CallState, ProviderEvent, make_event


class ProviderB(TelecomProvider):
    provider_name = "provider_b"

    def __init__(
        self,
        latency_ms: float = 450.0,
        failure_probability: float = 0.10,
        timeout_probability: float = 0.05,
        seed: int = 2,
    ) -> None:
        self.latency_ms = latency_ms
        self.failure_probability = failure_probability
        self.timeout_probability = timeout_probability
        self.random = random.Random(seed)
        self.metrics = ProviderMetrics()
        self._counter = 0

    def initiate_call(self, call: OutboundCall) -> ProviderResponse:
        self.metrics.calls_attempted += 1
        self.metrics.total_latency_ms += self.latency_ms
        self._counter += 1
        roll = self.random.random()
        if roll < self.timeout_probability:
            self.metrics.timeouts += 1
            self.metrics.failed += 1
            return ProviderResponse(
                None,
                False,
                utc_now(),
                self.provider_name,
                "PROVIDER_B_TIMEOUT",
            )
        if roll < self.timeout_probability + self.failure_probability:
            self.metrics.failed += 1
            return ProviderResponse(
                None,
                False,
                utc_now(),
                self.provider_name,
                "PROVIDER_B_FAILURE",
            )
        self.metrics.accepted += 1
        return ProviderResponse(
            f"B-{self._counter:08d}", True, utc_now(), self.provider_name
        )

    def get_health(self) -> ProviderHealth:
        failures = (
            self.metrics.failed / self.metrics.calls_attempted
            if self.metrics.calls_attempted
            else 0.0
        )
        healthy = failures <= 0.20 and self.latency_ms <= 1000
        reason = "healthy" if healthy else "latency or failure rate exceeded"
        return ProviderHealth(healthy, self.latency_ms, failures, reason)

    def events_for(
        self,
        call: OutboundCall,
        response: ProviderResponse,
        mode: str = "normal",
    ) -> list[ProviderEvent]:
        provider_call_id = response.provider_call_id or call.call_id
        if not response.accepted:
            event = make_event(
                f"{self.provider_name}-{call.call_id}-failed",
                call.call_id,
                CallState.FAILED,
                self.provider_name,
                provider_call_id,
            )
            return [event]
        normal = [
            CallState.RINGING,
            CallState.ANSWERED,
            CallState.CONNECTED,
            CallState.COMPLETED,
        ]
        if mode == "duplicate_answered":
            normal.insert(2, CallState.ANSWERED)
        elif mode == "out_of_order":
            normal = [
                CallState.COMPLETED,
                CallState.ANSWERED,
                CallState.RINGING,
            ]
        return [
            make_event(
                f"{self.provider_name}-{call.call_id}-{index}",
                call.call_id,
                event_type,
                self.provider_name,
                provider_call_id,
            )
            for index, event_type in enumerate(normal, 1)
        ]
