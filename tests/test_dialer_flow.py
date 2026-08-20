from collections import Counter
from pathlib import Path

from app.data.normalization import normalize_events
from app.dialer.allocator import CallAllocator
from app.dialer.estimators import AnswerRateEstimator, TalkTimeEstimator
from app.dialer.pacing import PredictivePacing
from app.models.agent import Agent
from app.providers.mock_provider import MockProvider
from app.safety.controller import SafetyController

ROOT = Path(__file__).parents[1]


def test_estimators_fit_from_canonical_call_data() -> None:
    events, _ = normalize_events(ROOT / "data")
    answer_rate = AnswerRateEstimator()
    talk_time = TalkTimeEstimator()
    answer_rate.fit(events)
    talk_time.fit(events)

    assert 0 < answer_rate.answer_rate < 1
    assert talk_time.talk_time_seconds > 0


def test_pacing_only_recommends_a_batch() -> None:
    pacing = PredictivePacing(AnswerRateEstimator(), TalkTimeEstimator())
    recommendation = pacing.recommend(available_agents=100, queued_calls=80)

    assert recommendation.calls_to_offer == 80
    assert recommendation.answer_rate == 0.5


def test_safety_blocks_duplicate_accounts_before_provider() -> None:
    provider = MockProvider()
    allocator = CallAllocator(SafetyController(), provider)
    allocations = allocator.allocate(
        [("CALL-1", "ACC-1"), ("CALL-2", "ACC-1")],
        [Agent(1), Agent(2)],
    )

    assert allocations == []
    assert provider.calls == []


def test_allocator_reserves_agents_and_handles_provider_failure() -> None:
    provider = MockProvider(fail_call_ids={"CALL-2"})
    allocator = CallAllocator(SafetyController(), provider)
    agents = [Agent(1), Agent(2)]
    allocations = allocator.allocate(
        [("CALL-1", "ACC-1"), ("CALL-2", "ACC-2")], agents
    )

    assert [
        allocation.provider_result.accepted for allocation in allocations
    ] == [
        True,
        False,
    ]
    assert agents[0].current_call_id == "CALL-1"
    assert agents[1].current_call_id is None


def test_safety_enforces_attempt_limit() -> None:
    safety = SafetyController(max_attempts_per_account=2)

    decision = safety.authorize(["ACC-1"], 0, Counter({"ACC-1": 2}))

    assert not decision.allowed
    assert decision.reason == "MAX_ATTEMPTS_PER_ACCOUNT"
