"""Provider registration, health selection, and initiation routing."""

from __future__ import annotations

from app.providers.base import (
    OutboundCall,
    ProviderHealth,
    ProviderResponse,
    TelecomProvider,
)


class ProviderManager:
    def __init__(self, providers: list[TelecomProvider] | None = None) -> None:
        self.providers: list[TelecomProvider] = []
        self._provider_by_call: dict[str, TelecomProvider] = {}
        self._response_by_call: dict[str, ProviderResponse] = {}
        for provider in providers or []:
            self.register(provider)

    def register(self, provider: TelecomProvider) -> None:
        self.providers.append(provider)

    def health(self) -> dict[str, ProviderHealth]:
        return {
            provider.provider_name: provider.get_health()
            for provider in self.providers
        }

    def select_healthy(self) -> TelecomProvider | None:
        healthy = [
            provider
            for provider in self.providers
            if provider.get_health().healthy
        ]
        return min(
            healthy,
            key=lambda provider: provider.get_health().latency_ms,
            default=None,
        )

    def initiate_call(self, call: OutboundCall) -> ProviderResponse:
        provider = self.select_healthy()
        if provider is None:
            raise RuntimeError("no healthy provider available")
        response = provider.initiate_call(call)
        self._provider_by_call[call.call_id] = provider
        self._response_by_call[call.call_id] = response
        return response

    def events_for_call(
        self,
        call: OutboundCall,
        response: ProviderResponse,
        mode: str = "normal",
    ):
        provider = self._provider_by_call.get(call.call_id)
        if provider is None or not hasattr(provider, "events_for"):
            return []
        if mode == "normal":
            return provider.events_for(call, response)
        return provider.events_for(call, response, mode)

    def events_for_call_id(
        self, call_id: str, account_id: str, mode: str = "normal"
    ):
        response = self._response_by_call.get(call_id)
        if response is None:
            return []
        return self.events_for_call(
            OutboundCall(call_id, account_id),
            response,
            mode,
        )

    def response_for_call(self, call_id: str) -> ProviderResponse | None:
        return self._response_by_call.get(call_id)

    def place_call(self, call_id: str, account_id: str):
        """Compatibility adapter for the allocator provider boundary."""
        response = self.initiate_call(OutboundCall(call_id, account_id))
        from app.providers.base import ProviderResult

        return ProviderResult(
            response.accepted,
            response.error,
            response.provider_call_id,
        )
