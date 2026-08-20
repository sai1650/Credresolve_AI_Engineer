from concurrent.futures import ThreadPoolExecutor

from app.dialer.allocator import CallAllocator
from app.models.agent import Agent
from app.providers.mock_provider import MockProvider
from app.safety.controller import APPROVE, SafetyDecision


def decision(count: int) -> SafetyDecision:
    return SafetyDecision(count, count, APPROVE, "test")


def test_workers_competing_for_one_agent_create_one_call():
    allocator = CallAllocator(provider=MockProvider())
    agents = [Agent(1)]

    def worker(index: int):
        return allocator.allocate(
            decision(1),
            "campaign",
            agents,
            [f"A{index}"],
            str(index),
        )

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(worker, range(5)))
    assert sum(len(result.created_calls) for result in results) == 1


def test_workers_competing_for_one_account_are_idempotent_or_skipped():
    provider = MockProvider()
    allocator = CallAllocator(provider=provider)

    def worker(index: int):
        return allocator.allocate(
            decision(1),
            "campaign",
            [Agent(index)],
            ["ACCOUNT"],
            "same",
        )

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(worker, range(5)))
    assert sum(len(result.created_calls) for result in results) == 5
    assert len(provider.calls) == 1
    assert sum(result.duplicate_jobs for result in results) == 4
