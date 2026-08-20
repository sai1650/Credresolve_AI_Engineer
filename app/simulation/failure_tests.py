"""Reproducible failure and recovery checks for the simulator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.dialer.predictive import PacingState, PredictivePacingEngine
from app.models.agent import Agent
from app.providers.base import OutboundCall
from app.providers.events import CallState, ProviderEventProcessor
from app.providers.manager import ProviderManager
from app.providers.provider_a import ProviderA
from app.providers.provider_b import ProviderB
from app.safety.controller import SafetyController, SafetyState
from app.dialer.allocator import CallAllocator
from app.safety.controller import APPROVE, SafetyDecision


@dataclass(frozen=True)
class StateReconciliation:
    source_state: str
    cache_state: str
    resolved_state: str
    conflict: bool
    reason: str


def provider_outage_check() -> dict[str, Any]:
    provider_a = ProviderA(failure_probability=1.0, seed=1)
    provider_b = ProviderB(
        failure_probability=0, timeout_probability=0, seed=2
    )
    manager = ProviderManager([provider_a, provider_b])
    existing = OutboundCall("EXISTING", "ACCOUNT-1")
    response = manager.initiate_call(existing)
    health_before = manager.health()
    fallback = manager.initiate_call(OutboundCall("NEW", "ACCOUNT-2"))
    return {
        "existing_call_processed": response is not None,
        "provider_a_healthy": health_before["provider_a"].healthy,
        "failover_provider": fallback.provider_name,
        "provider_b_used": fallback.provider_name == "provider_b",
    }


def stale_state_reconcile(
    source_agent: Agent, cache_state: str
) -> StateReconciliation:
    source_state = source_agent.state
    return StateReconciliation(
        source_state,
        cache_state,
        source_state,
        source_state != cache_state,
        "Agent object is the prototype source of truth; cache is advisory.",
    )


def retry_storm_check(attempts: int = 10) -> dict[str, Any]:
    provider = ProviderManager([ProviderA(failure_probability=0, seed=3)])
    allocator = CallAllocator(provider=provider)
    decision = SafetyDecision(1, 1, APPROVE, "retry test")
    results = [
        allocator.allocate(
            decision,
            "RETRY",
            [Agent(1)],
            ["ACCOUNT-1"],
            "same-job",
        )
        for _ in range(attempts)
    ]
    call_ids = {
        call.call_id for result in results for call in result.created_calls
    }
    return {
        "submissions": attempts,
        "logical_calls": len(call_ids),
        "provider_requests": len(provider._response_by_call),
        "duplicate_jobs": sum(result.duplicate_jobs for result in results),
    }


def duplicate_and_out_of_order_check() -> dict[str, Any]:
    processor = ProviderEventProcessor(CallState.RINGING)
    answered = [CallState.ANSWERED] * 3 + [CallState.COMPLETED] * 2
    accepted = [
        processor.process(_event(index, state)).accepted
        for index, state in enumerate(answered)
    ]
    return {
        "accepted_transitions": sum(accepted),
        "final_state": processor.state.value,
        "ignored_events": len(processor.ignored_events),
    }


def _event(index: int, state: CallState):
    from app.providers.events import make_event

    return make_event(f"EVENT-{index}", "CALL-1", state, "provider_b")


def availability_and_answer_collapse() -> dict[str, Any]:
    pacing = PredictivePacingEngine(max_recommendation=200)
    safety = SafetyController()

    def evaluate(agents: int, estimate: float, recent: float):
        p_state = PacingState(
            agents,
            0,
            0,
            estimate,
            estimate,
            180,
            100,
            1.0,
            80,
            0,
            recent,
            previous_available_agents=100,
        )
        pacing_decision = pacing.calculate_pacing(p_state)
        safety_decision = safety.evaluate(
            pacing_decision,
            SafetyState(agents, 0, 0, 1.0, previous_available_agents=100),
        )
        return pacing_decision.requested_calls, safety_decision.approved_calls

    return {
        "before": evaluate(100, 0.7, 0.7),
        "after": evaluate(60, 0.7, 0.1),
    }
