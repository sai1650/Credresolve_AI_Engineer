from app.dialer.predictive import PacingState, PredictivePacingEngine


def state(**changes):
    values = dict(
        available_agents=10,
        connected_calls=0,
        ringing_calls=0,
        answer_probability=0.5,
        historical_answer_rate=0.5,
        average_talk_time_seconds=90,
        recent_call_volume=100,
        provider_health=1.0,
        provider_latency_ms=0,
        provider_failure_rate=0,
    )
    values.update(changes)
    return PacingState(**values)


def test_zero_agents_returns_zero():
    assert (
        PredictivePacingEngine()
        .calculate_pacing(state(available_agents=0))
        .requested_calls
        == 0
    )


def test_healthy_system_recommends_calls_and_is_bounded():
    decision = PredictivePacingEngine(max_recommendation=7).calculate_pacing(
        state()
    )
    assert 0 < decision.requested_calls <= 7


def test_provider_health_and_latency_reduce_recommendation():
    healthy = PredictivePacingEngine().calculate_pacing(state())
    unhealthy = PredictivePacingEngine().calculate_pacing(
        state(
            provider_health=0.4,
            provider_latency_ms=1800,
            provider_failure_rate=0.3,
        ),
    )
    assert unhealthy.requested_calls < healthy.requested_calls


def test_answer_rate_drop_reduces_recommendation():
    normal = PredictivePacingEngine().calculate_pacing(
        state(answer_probability=0.7, campaign_answer_rate=0.7)
    )
    dropped = PredictivePacingEngine().calculate_pacing(
        state(answer_probability=0.7, campaign_answer_rate=0.1)
    )
    assert dropped.requested_calls < normal.requested_calls


def test_availability_drop_and_long_talk_time_reduce_recommendation():
    normal = PredictivePacingEngine().calculate_pacing(state())
    reduced = PredictivePacingEngine().calculate_pacing(
        state(
            available_agents=5,
            previous_available_agents=10,
            average_talk_time_seconds=600,
        ),
    )
    assert reduced.requested_calls < normal.requested_calls


def test_same_inputs_are_deterministic_and_no_provider_is_used():
    engine = PredictivePacingEngine()
    first = engine.calculate_pacing(state())
    second = engine.calculate_pacing(state())
    assert first == second
    assert not hasattr(engine, "provider")


def test_insufficient_prediction_uses_fallback():
    decision = PredictivePacingEngine().calculate_pacing(
        state(answer_probability=None, historical_answer_rate=0.2),
    )
    assert decision.fallback_recommended
    assert "historical answer rate" in decision.reason
