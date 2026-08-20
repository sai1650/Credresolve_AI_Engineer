"""Provider contracts shared by dialer implementations."""

from __future__ import annotations

from dataclasses import dataclass
from abc import ABC, abstractmethod
from datetime import datetime, timezone


@dataclass(frozen=True)
class ProviderResult:
    accepted: bool
    reason: str | None = None
    provider_call_id: str | None = None


@dataclass(frozen=True)
class ProviderResponse:
    provider_call_id: str | None
    accepted: bool
    timestamp: datetime
    provider_name: str
    error: str | None = None


@dataclass(frozen=True)
class ProviderHealth:
    healthy: bool
    latency_ms: float
    failure_rate: float
    reason: str


@dataclass(frozen=True)
class OutboundCall:
    call_id: str
    account_id: str


class TelecomProvider(ABC):
    """Stable interface consumed by the allocator/manager boundary."""

    provider_name: str

    @abstractmethod
    def initiate_call(self, call: OutboundCall) -> ProviderResponse:
        raise NotImplementedError

    @abstractmethod
    def get_health(self) -> ProviderHealth:
        raise NotImplementedError

    def place_call(self, call_id: str, account_id: str) -> ProviderResult:
        response = self.initiate_call(OutboundCall(call_id, account_id))
        return ProviderResult(
            accepted=response.accepted,
            reason=response.error,
            provider_call_id=response.provider_call_id,
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
