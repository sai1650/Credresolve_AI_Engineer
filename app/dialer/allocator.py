"""Safety-bound, idempotent outbound call allocation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from threading import Lock
import time
from typing import Any, Iterable

from app.models.agent import Agent
from app.safety.controller import (
    APPROVE,
    FALLBACK_TO_PROGRESSIVE,
    REDUCE,
    REJECT,
    SafetyDecision,
)


@dataclass(frozen=True)
class Allocation:
    call_id: str
    account_id: str
    agent: Agent
    provider_result: Any
    campaign_id: str = ""
    idempotency_key: str = ""
    lifecycle: str = "INITIATED"
    lifecycle_history: tuple[str, ...] = ("QUEUED", "RESERVED", "INITIATED")


@dataclass
class AllocationResult:
    created_calls: list[Allocation] = field(default_factory=list)
    skipped_accounts: list[str] = field(default_factory=list)
    unavailable_agents: int = 0
    duplicate_jobs: int = 0
    failed_allocations: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class _AccountReservation:
    account_id: str
    call_id: str
    reserved_at: float
    active: bool = True


class CallAllocator:
    """The only component that creates outbound provider call requests."""

    def __init__(
        self,
        safety_controller: Any = None,
        provider: Any = None,
        reservation_timeout_seconds: float = 300.0,
    ) -> None:
        self.safety_controller = safety_controller
        self.provider = provider
        self.reservation_timeout_seconds = reservation_timeout_seconds
        self._lock = Lock()
        self._accounts: dict[str, _AccountReservation] = {}
        self._jobs: dict[str, Allocation] = {}
        self._agent_reservations: dict[int, float] = {}
        self._reserved_agents: dict[int, Agent] = {}
        self._next_call_number = 1

    def allocate(
        self,
        safety_decision: Any,
        campaign_id: Any,
        available_agents: Any = None,
        eligible_accounts: Any = None,
        allocation_window: str = "default",
        progressive_authorized: bool = False,
    ) -> AllocationResult | list[Allocation]:
        """Allocate up to the independently approved number of calls.

        The two-argument list/agent form is retained solely for older callers;
        all new allocation jobs must provide a SafetyDecision.
        """
        if not isinstance(safety_decision, SafetyDecision):
            if not isinstance(safety_decision, Iterable) or not isinstance(
                campaign_id, list
            ):
                raise ValueError("allocator requires a SafetyDecision")
            return self._legacy_allocate(safety_decision, campaign_id)
        self._validate_decision(safety_decision, progressive_authorized)
        requested = safety_decision.approved_calls
        result = AllocationResult()
        if requested == 0 or safety_decision.action in {
            REJECT,
            FALLBACK_TO_PROGRESSIVE,
        }:
            result.reason = "safety decision authorizes no predictive calls"
            return result
        agents = list(available_agents or [])
        accounts = [
            self._account_id(item) for item in (eligible_accounts or [])
        ]
        created = 0
        for account_id in accounts:
            if created >= requested:
                break
            key = self._idempotency_key(
                campaign_id, account_id, allocation_window
            )
            with self._lock:
                existing = self._jobs.get(key)
                if existing is not None:
                    result.created_calls.append(existing)
                    result.duplicate_jobs += 1
                    created += 1
                    continue
                if self._active_account(account_id):
                    result.skipped_accounts.append(account_id)
                    continue
                call_id = f"CALL-{self._next_call_number:08d}"
                agent = self._reserve_agent(agents, call_id)
                if agent is None:
                    result.unavailable_agents += 1
                    break
                self._next_call_number += 1
                self._accounts[account_id] = _AccountReservation(
                    account_id, call_id, time.monotonic()
                )
                self._agent_reservations[agent.agent_id] = time.monotonic()
            try:
                provider_result = self._create_call(call_id, account_id)
            except Exception as error:
                self._release(account_id, agent)
                result.failed_allocations.append(f"{account_id}: {error}")
                continue
            if not getattr(provider_result, "accepted", False):
                self._release(account_id, agent)
                result.failed_allocations.append(account_id)
                continue
            agent.start_call()
            allocation = Allocation(
                call_id,
                account_id,
                agent,
                provider_result,
                str(campaign_id),
                key,
            )
            with self._lock:
                self._jobs[key] = allocation
            result.created_calls.append(allocation)
            created += 1
        result.reason = "allocation completed within safety approval"
        return result

    def recover_stale_reservations(self, now: float | None = None) -> int:
        current = time.monotonic() if now is None else now
        recovered = 0
        with self._lock:
            stale_accounts = [
                account_id
                for account_id, reservation in self._accounts.items()
                if reservation.active
                and current - reservation.reserved_at
                > self.reservation_timeout_seconds
            ]
            for account_id in stale_accounts:
                self._accounts.pop(account_id)
                for agent_id, reserved_at in list(
                    self._agent_reservations.items()
                ):
                    if (
                        current - reserved_at
                        > self.reservation_timeout_seconds
                    ):
                        self._agent_reservations.pop(agent_id)
                        agent = self._reserved_agents.pop(agent_id, None)
                        if agent is not None:
                            agent.release()
                recovered += 1
        return recovered

    def _create_call(self, call_id: str, account_id: str) -> Any:
        if self.provider is None or not hasattr(self.provider, "place_call"):
            raise RuntimeError("allocator requires a provider boundary")
        return self.provider.place_call(call_id, account_id)

    def _reserve_agent(
        self, agents: Iterable[Agent], call_id: str
    ) -> Agent | None:
        for agent in agents:
            try:
                agent.reserve(call_id)
            except RuntimeError:
                continue
            self._reserved_agents[agent.agent_id] = agent
            return agent
        return None

    def _release(self, account_id: str, agent: Agent) -> None:
        with self._lock:
            self._accounts.pop(account_id, None)
            self._agent_reservations.pop(agent.agent_id, None)
            self._reserved_agents.pop(agent.agent_id, None)
        agent.release()

    def _active_account(self, account_id: str) -> bool:
        reservation = self._accounts.get(account_id)
        return reservation is not None and reservation.active

    @staticmethod
    def _account_id(account: Any) -> str:
        if isinstance(account, str):
            return account
        if isinstance(account, dict) and account.get("account_id"):
            return str(account["account_id"])
        if hasattr(account, "account_id"):
            return str(account.account_id)
        raise ValueError("eligible account must provide account_id")

    @staticmethod
    def _idempotency_key(
        campaign_id: Any, account_id: str, allocation_window: str
    ) -> str:
        return f"{campaign_id}:{account_id}:{allocation_window}"

    @staticmethod
    def _validate_decision(
        decision: SafetyDecision, progressive_authorized: bool
    ) -> None:
        if decision.action not in {
            APPROVE,
            REDUCE,
            REJECT,
            FALLBACK_TO_PROGRESSIVE,
        }:
            raise ValueError("invalid SafetyDecision action")
        if decision.approved_calls < 0 or decision.requested_calls < 0:
            raise ValueError("SafetyDecision call counts cannot be negative")
        if decision.approved_calls > decision.requested_calls:
            raise ValueError("approved_calls cannot exceed requested_calls")
        if (
            decision.action == FALLBACK_TO_PROGRESSIVE
            and not progressive_authorized
        ):
            raise ValueError(
                "progressive fallback requires explicit authorization"
            )
        if decision.action == REJECT and decision.approved_calls != 0:
            raise ValueError("REJECT decisions cannot approve calls")

    def _legacy_allocate(
        self, calls: Iterable[tuple[str, str]], agents: list[Agent]
    ) -> list[Allocation]:
        call_list = list(calls)
        if self.safety_controller is not None and hasattr(
            self.safety_controller, "authorize"
        ):
            decision = self.safety_controller.authorize(
                [account_id for _, account_id in call_list],
                0,
                Counter(),
            )
            if not decision.allowed:
                return []
        allocations: list[Allocation] = []
        for (call_id, account_id), agent in zip(call_list, agents):
            try:
                agent.reserve(call_id)
            except RuntimeError:
                continue
            result = self._create_call(call_id, account_id)
            if not result.accepted:
                agent.release()
                allocations.append(
                    Allocation(call_id, account_id, agent, result)
                )
                continue
            agent.start_call()
            allocations.append(Allocation(call_id, account_id, agent, result))
        return allocations
