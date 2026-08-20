"""Deterministic provider for local simulations and tests."""

from __future__ import annotations

from app.providers.base import ProviderResult


class MockProvider:
    def __init__(self, fail_call_ids: set[str] | None = None) -> None:
        self.fail_call_ids = fail_call_ids or set()
        self.calls: list[tuple[str, str]] = []

    def place_call(self, call_id: str, account_id: str) -> ProviderResult:
        self.calls.append((call_id, account_id))
        if call_id in self.fail_call_ids:
            return ProviderResult(
                accepted=False, reason="MOCK_PROVIDER_FAILURE"
            )
        return ProviderResult(
            accepted=True, provider_call_id=f"MOCK-{call_id}"
        )
