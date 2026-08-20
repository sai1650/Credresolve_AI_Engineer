from app.dialer.predictive import PacingDecision
from app.safety.controller import (
    APPROVE,
    FALLBACK_TO_PROGRESSIVE,
    REDUCE,
    REJECT,
    SafetyController,
    SafetyLimits,
    SafetyState,
)


def pacing(requested: int) -> PacingDecision:
    return PacingDecision(requested, 0, 0, 0, 1, "test", 1, False)


def live(**changes) -> SafetyState:
    values = dict(
        available_agents=10,
        connected_calls=0,
        ringing_calls=0,
        provider_health=1.0,
    )
    values.update(changes)
    return SafetyState(**values)


def test_zero_requested_calls_are_approved_as_zero():
    decision = SafetyController().evaluate(pacing(0), live(available_agents=0))
    assert (decision.action, decision.approved_calls) == (APPROVE, 0)


def test_no_agents_reject():
    decision = SafetyController().evaluate(pacing(5), live(available_agents=0))
    assert decision.action == REJECT
    assert decision.approved_calls == 0


def test_safe_request_approved_and_unsafe_request_reduced():
    controller = SafetyController()
    assert controller.evaluate(pacing(5), live()).action == APPROVE
    reduced = controller.evaluate(pacing(25), live())
    assert reduced.action == REDUCE
    assert reduced.approved_calls == 10


def test_unhealthy_provider_falls_back_without_predictive_approval():
    decision = SafetyController().evaluate(
        pacing(5),
        live(provider_health=0.2),
    )
    assert decision.action == FALLBACK_TO_PROGRESSIVE
    assert decision.progressive_fallback
    assert decision.approved_calls == 0


def test_provider_failure_and_latency_reduce():
    controller = SafetyController()
    failure = controller.evaluate(pacing(10), live(provider_failure_rate=0.5))
    latency = controller.evaluate(pacing(10), live(provider_latency_ms=2000))
    assert failure.action == REDUCE and failure.approved_calls == 5
    assert latency.action == REDUCE and latency.approved_calls == 5


def test_outstanding_and_ringing_hard_limits_reject():
    limits = SafetyLimits(max_outstanding_calls=20, maximum_ringing_calls=10)
    controller = SafetyController(limits)
    assert (
        controller.evaluate(pacing(1), live(ringing_calls=10)).action == REJECT
    )
    assert (
        controller.evaluate(pacing(1), live(connected_calls=20)).action
        == REJECT
    )


def test_availability_drop_recalculates_capacity_immediately():
    decision = SafetyController().evaluate(
        pacing(100),
        live(available_agents=60, previous_available_agents=100),
    )
    assert decision.approved_calls == 60
    assert "availability" in decision.reason


def test_hard_bounds_and_determinism():
    controller = SafetyController()
    state = live(available_agents=3, stale_reservations=1)
    first = controller.evaluate(pacing(100), state)
    second = controller.evaluate(pacing(100), state)
    assert first == second
    assert 0 <= first.approved_calls <= first.requested_calls <= 100
    assert first.approved_calls <= state.available_agents


def test_campaign_and_stale_reservation_limits_apply():
    decision = SafetyController().evaluate(
        pacing(10),
        live(
            campaign_active_calls=4, campaign_max_calls=6, stale_reservations=1
        ),
    )
    assert decision.approved_calls == 1


def test_controller_has_no_provider_dependency_or_call_method():
    source = __import__(
        "app.safety.controller", fromlist=["SafetyController"]
    ).__file__
    text = open(source, encoding="utf-8").read()
    assert "app.providers" not in text
    assert "place_call" not in text
