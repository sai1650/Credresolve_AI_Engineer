"""Deterministic fast and reliable mock telecom provider."""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.providers.base import (
    OutboundCall,
    ProviderHealth,
    ProviderResponse,
    TelecomProvider,
    utc_now,
)
from app.providers.events import CallState, ProviderEvent, make_event


@dataclass
class ProviderMetrics:
    calls_attempted: int = 0
    accepted: int = 0
    failed: int = 0
    timeouts: int = 0
    total_latency_ms: float = 0.0
    duplicate_events: int = 0
    out_of_order_events: int = 0

    @property
    def average_latency_ms(self) -> float:
        return (
            self.total_latency_ms / self.calls_attempted
            if self.calls_attempted
            else 0.0
        )


class ProviderA(TelecomProvider):
    provider_name = "provider_a"

    def __init__(
        self,
        latency_ms: float = 80.0,
        failure_probability: float = 0.02,
        seed: int = 1,
    ) -> None:
        self.latency_ms = latency_ms
        self.failure_probability = failure_probability
        self.random = random.Random(seed)
        self.metrics = ProviderMetrics()
        self._counter = 0

    def initiate_call(self, call: OutboundCall) -> ProviderResponse:
        self.metrics.calls_attempted += 1
        self.metrics.total_latency_ms += self.latency_ms
        self._counter += 1
        if self.random.random() < self.failure_probability:
            self.metrics.failed += 1
            return ProviderResponse(
                None,
                False,
                utc_now(),
                self.provider_name,
                "PROVIDER_A_FAILURE",
            )
        self.metrics.accepted += 1
        return ProviderResponse(
            f"A-{self._counter:08d}",
            True,
            utc_now(),
            self.provider_name,
        )

    def get_health(self) -> ProviderHealth:
        failures = (
            self.metrics.failed / self.metrics.calls_attempted
            if self.metrics.calls_attempted
            else 0.0
        )
        return ProviderHealth(
            healthy=failures <= 0.20,
            latency_ms=self.latency_ms,
            failure_rate=failures,
            reason="healthy" if failures <= 0.20 else "failure rate exceeded",
        )

    def events_for(
        self,
        call: OutboundCall,
        response: ProviderResponse,
        mode: str = "normal",
    ) -> list[ProviderEvent]:
        if not response.accepted:
            return [
                make_event(
                    f"{response.provider_name}-{call.call_id}-failed",
                    call.call_id,
                    CallState.FAILED,
                    self.provider_name,
                    response.provider_call_id or call.call_id,
                )
            ]
        types = [
            CallState.RINGING,
            CallState.ANSWERED,
            CallState.CONNECTED,
            CallState.COMPLETED,
        ]
        return [
            make_event(
                f"{self.provider_name}-{call.call_id}-{index}",
                call.call_id,
                event_type,
                self.provider_name,
                response.provider_call_id or call.call_id,
            )
            for index, event_type in enumerate(types, 1)
        ]
