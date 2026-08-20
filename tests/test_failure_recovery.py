from app.models.agent import Agent
from app.simulation.failure_tests import (
    availability_and_answer_collapse,
    duplicate_and_out_of_order_check,
    provider_outage_check,
    retry_storm_check,
    stale_state_reconcile,
)


def test_provider_outage_fails_over_to_provider_b():
    result = provider_outage_check()
    assert result["provider_b_used"]


def test_retry_storm_is_idempotent():
    result = retry_storm_check(10)
    assert result["logical_calls"] == 1
    assert result["provider_requests"] == 1
    assert result["duplicate_jobs"] == 9


def test_duplicate_and_out_of_order_events_are_terminal_safe():
    result = duplicate_and_out_of_order_check()
    assert result["final_state"] == "COMPLETED"
    assert result["accepted_transitions"] == 2
    assert result["ignored_events"] == 3


def test_availability_and_answer_rate_collapse_reduce_work():
    result = availability_and_answer_collapse()
    assert result["after"][0] < result["before"][0]
    assert result["after"][1] <= result["before"][1]


def test_source_of_truth_reconciliation_is_explicit():
    agent = Agent(1)
    result = stale_state_reconcile(agent, "RESERVED")
    assert result.conflict
    assert result.resolved_state == "AVAILABLE"
    assert "source of truth" in result.reason
