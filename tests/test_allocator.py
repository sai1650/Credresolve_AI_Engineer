from pathlib import Path

import pytest

from app.dialer.allocator import AllocationResult, CallAllocator
from app.models.agent import Agent
from app.providers.mock_provider import MockProvider
from app.safety.controller import (
    APPROVE,
    FALLBACK_TO_PROGRESSIVE,
    REJECT,
    SafetyDecision,
)


def decision(
    requested: int, approved: int | None = None, action: str = APPROVE
):
    approved = requested if approved is None else approved
    return SafetyDecision(requested, approved, action, "test")


def test_zero_approval_creates_no_calls():
    provider = MockProvider()
    result = CallAllocator(provider=provider).allocate(
        decision(5, 0, REJECT),
        "campaign",
        [Agent(1)],
        ["A"],
    )
    assert isinstance(result, AllocationResult)
    assert result.created_calls == [] and provider.calls == []


def test_allocation_never_exceeds_approval_or_agents():
    allocator = CallAllocator(provider=MockProvider())
    result = allocator.allocate(
        decision(5),
        "campaign",
        [Agent(1), Agent(2), Agent(3)],
        ["A", "B", "C", "D", "E"],
    )
    assert len(result.created_calls) == 3
    assert all(call.lifecycle == "INITIATED" for call in result.created_calls)
    assert all(
        call.lifecycle_history == ("QUEUED", "RESERVED", "INITIATED")
        for call in result.created_calls
    )


def test_duplicate_job_returns_existing_call():
    provider = MockProvider()
    allocator = CallAllocator(provider=provider)
    first = allocator.allocate(
        decision(1), "campaign", [Agent(1)], ["A"], "window"
    )
    second = allocator.allocate(
        decision(1), "campaign", [Agent(2)], ["A"], "window"
    )
    assert first.created_calls[0].call_id == second.created_calls[0].call_id
    assert second.duplicate_jobs == 1
    assert len(provider.calls) == 1


def test_same_account_is_not_active_twice_in_another_job():
    allocator = CallAllocator(provider=MockProvider())
    allocator.allocate(decision(1), "campaign", [Agent(1)], ["A"], "one")
    result = allocator.allocate(
        decision(1), "campaign", [Agent(2)], ["A"], "two"
    )
    assert result.created_calls == []
    assert result.skipped_accounts == ["A"]


def test_failed_provider_call_releases_reservations():
    provider = MockProvider(fail_call_ids={"CALL-00000001"})
    agent = Agent(1)
    allocator = CallAllocator(provider=provider)
    result = allocator.allocate(decision(1), "campaign", [agent], ["A"])
    assert result.failed_allocations == ["A"]
    assert agent.state == "AVAILABLE"
    retry = allocator.allocate(
        decision(1), "campaign", [agent], ["A"], "retry"
    )
    assert len(retry.created_calls) == 1


def test_fallback_requires_explicit_progressive_authorization():
    fallback = decision(2, 0, FALLBACK_TO_PROGRESSIVE)
    allocator = CallAllocator(provider=MockProvider())
    with pytest.raises(ValueError, match="progressive fallback"):
        allocator.allocate(fallback, "campaign", [Agent(1)], ["A"])


def test_invalid_decision_and_requested_only_api_fail_clearly():
    allocator = CallAllocator(provider=MockProvider())
    with pytest.raises(ValueError, match="approved_calls"):
        allocator.allocate(decision(1, 2), "campaign", [Agent(1)], ["A"])
    with pytest.raises(ValueError, match="SafetyDecision"):
        allocator.allocate(5, "campaign", [Agent(1)], ["A"])


def test_stale_reservations_are_recovered():
    agent = Agent(1)
    allocator = CallAllocator(
        provider=MockProvider(), reservation_timeout_seconds=1
    )
    allocator.allocate(decision(1), "campaign", [agent], ["A"])
    assert allocator.recover_stale_reservations(now=10**9) == 1
    assert agent.state == "AVAILABLE"
