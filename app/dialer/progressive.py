"""Conservative progressive dialing recommendation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressiveDecision:
    requested_calls: int
    reason: str


class ProgressiveDialer:
    """Offer at most one agent-bound call per available agent."""

    def __init__(self, max_calls: int | None = None) -> None:
        self.max_calls = max_calls

    def recommend(
        self, available_agents: int, queued_accounts: int
    ) -> ProgressiveDecision:
        if available_agents < 0 or queued_accounts < 0:
            raise ValueError("agent and account counts cannot be negative")
        limit = available_agents
        if self.max_calls is not None:
            limit = min(limit, self.max_calls)
        return ProgressiveDecision(
            requested_calls=min(limit, queued_accounts),
            reason="one conservative call per available agent",
        )
