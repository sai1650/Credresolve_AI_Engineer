"""Independent hard safety boundary for predictive pacing decisions."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

APPROVE = "APPROVE"
REDUCE = "REDUCE"
REJECT = "REJECT"
FALLBACK_TO_PROGRESSIVE = "FALLBACK_TO_PROGRESSIVE"


@dataclass(frozen=True)
class SafetyLimits:
    """Explicit hard limits used by the safety evaluation."""

    max_outstanding_calls: int = 200
    max_calls_per_agent: int = 1
    max_provider_failure_rate: float = 0.20
    max_provider_latency_ms: float = 1000.0
    reservation_timeout_seconds: float = 300.0
    minimum_provider_health: float = 0.50
    maximum_ringing_calls: int = 100


@dataclass(frozen=True)
class SafetyState:
    """Only live operational facts needed for a safety decision."""

    available_agents: int
    connected_calls: int
    ringing_calls: int
    provider_health: float
    provider_latency_ms: float = 0.0
    provider_failure_rate: float = 0.0
    campaign_active_calls: int = 0
    campaign_max_calls: int | None = None
    stale_reservations: int = 0
    previous_available_agents: int | None = None
    provider_available: bool = True


@dataclass(frozen=True)
class SafetyDecision:
    requested_calls: int
    approved_calls: int
    action: str
    reason: str
    safety_checks: dict[str, Any] = field(default_factory=dict)
    progressive_fallback: bool = False

    @property
    def allowed(self) -> bool:
        """Compatibility property for legacy allocator authorization."""
        return self.action in {APPROVE, REDUCE} and self.approved_calls > 0


class SafetyController:
    """Final authority over pacing recommendations; never places calls."""

    def __init__(
        self,
        limits: SafetyLimits | None = None,
        max_attempts_per_account: int = 3,
    ) -> None:
        self.limits = limits or SafetyLimits()
        self.max_attempts_per_account = max_attempts_per_account

    def evaluate(
        self, pacing_decision: Any, safety_state: SafetyState
    ) -> SafetyDecision:
        requested = max(0, int(getattr(pacing_decision, "requested_calls", 0)))
        checks = self._checks(safety_state, requested)
        if requested == 0:
            return self._decision(
                requested, 0, APPROVE, "no calls requested", checks
            )
        if safety_state.available_agents <= 0:
            return self._decision(
                requested, 0, REJECT, "no available agents", checks
            )
        if not checks["provider_healthy"]:
            return self._decision(
                requested,
                0,
                FALLBACK_TO_PROGRESSIVE,
                "provider is unhealthy; predictive calls are not approved",
                checks,
                True,
            )
        if safety_state.ringing_calls >= self.limits.maximum_ringing_calls:
            return self._decision(
                requested, 0, REJECT, "maximum ringing calls reached", checks
            )
        if checks["outstanding_at_limit"]:
            return self._decision(
                requested,
                0,
                REJECT,
                "maximum outstanding calls reached",
                checks,
            )

        safe_capacity = checks["safe_capacity"]
        if (
            safety_state.provider_failure_rate
            > self.limits.max_provider_failure_rate
        ):
            safe_capacity = min(safe_capacity, max(0, safe_capacity // 2))
            reason = "provider failure rate exceeds limit"
        elif (
            safety_state.provider_latency_ms
            > self.limits.max_provider_latency_ms
        ):
            safe_capacity = min(safe_capacity, max(0, safe_capacity // 2))
            reason = "provider latency exceeds limit"
        elif checks["availability_dropped"]:
            reason = "agent availability dropped; capacity recalculated"
        elif safe_capacity < requested:
            reason = "agent or outstanding-call capacity constraint"
        else:
            reason = "within independent safety limits"
        approved = min(requested, safe_capacity)
        action = APPROVE if approved == requested else REDUCE
        if approved == 0:
            action = REJECT
        return self._decision(requested, approved, action, reason, checks)

    def _checks(self, state: SafetyState, requested: int) -> dict[str, Any]:
        outstanding = state.connected_calls + state.ringing_calls
        outstanding_capacity = max(
            0, self.limits.max_outstanding_calls - outstanding
        )
        agent_capacity = max(
            0, state.available_agents * self.limits.max_calls_per_agent
        )
        campaign_capacity = None
        if state.campaign_max_calls is not None:
            campaign_capacity = max(
                0, state.campaign_max_calls - state.campaign_active_calls
            )
        safe_capacity = min(agent_capacity, outstanding_capacity)
        if campaign_capacity is not None:
            safe_capacity = min(safe_capacity, campaign_capacity)
        safe_capacity = max(0, safe_capacity - state.stale_reservations)
        return {
            "available_agents": state.available_agents,
            "agent_capacity": agent_capacity,
            "outstanding_calls": outstanding,
            "outstanding_capacity": outstanding_capacity,
            "safe_capacity": safe_capacity,
            "campaign_capacity": campaign_capacity,
            "stale_reservations": state.stale_reservations,
            "provider_healthy": (
                state.provider_available
                and state.provider_health
                >= self.limits.minimum_provider_health
            ),
            "provider_failure_within_limit": (
                state.provider_failure_rate
                <= self.limits.max_provider_failure_rate
            ),
            "provider_latency_within_limit": (
                state.provider_latency_ms
                <= self.limits.max_provider_latency_ms
            ),
            "outstanding_at_limit": outstanding
            >= self.limits.max_outstanding_calls,
            "availability_dropped": (
                state.previous_available_agents is not None
                and state.available_agents < state.previous_available_agents
            ),
            "requested_calls": requested,
        }

    @staticmethod
    def _decision(
        requested: int,
        approved: int,
        action: str,
        reason: str,
        checks: dict[str, Any],
        fallback: bool = False,
    ) -> SafetyDecision:
        return SafetyDecision(
            requested_calls=requested,
            approved_calls=max(0, min(requested, approved)),
            action=action,
            reason=reason,
            safety_checks=checks,
            progressive_fallback=fallback,
        )

    # Legacy account authorization remains separate from pacing evaluation.
    def authorize(
        self,
        account_ids: Iterable[str],
        active_account_count: int,
        attempt_counts: Counter[str],
    ) -> SafetyDecision:
        accounts = list(account_ids)
        if len(accounts) != len(set(accounts)):
            return self._decision(
                len(accounts),
                0,
                REJECT,
                "DUPLICATE_ACCOUNT_BATCH",
                {},
            )
        if active_account_count < 0:
            return self._decision(
                len(accounts),
                0,
                REJECT,
                "INVALID_ACTIVE_ACCOUNT_COUNT",
                {},
            )
        if any(
            attempt_counts[account_id] >= self.max_attempts_per_account
            for account_id in accounts
        ):
            return self._decision(
                len(accounts),
                0,
                REJECT,
                "MAX_ATTEMPTS_PER_ACCOUNT",
                {},
            )
        return self._decision(
            len(accounts),
            len(accounts),
            APPROVE,
            "within account safety limits",
            {},
        )
