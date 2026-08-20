from app.simulation.scenarios import Scenario, SimulationConfig, scenarios
from app.simulation.simulator import SmartDialerSimulator


def run(name: str):
    simulator = SmartDialerSimulator(
        SimulationConfig(agents=100, accounts=1000, workers=5, seed=42),
    )
    return simulator.run(scenarios()[name])


def test_baseline_and_all_scenarios_produce_valid_metrics():
    for name in ("A", "B", "C", "D"):
        result = run(name)
        metrics = result.metrics
        assert metrics["total_calls_initiated"] >= 0
        assert (
            metrics["total_calls_connected"]
            <= metrics["total_calls_initiated"]
        )
        assert 0 <= metrics["answer_rate"] <= 1
        assert 0 <= metrics["agent_utilization"] <= 1
        assert not metrics["invariant_failures"]


def test_answer_rate_collapse_reduces_scenario_d_pacing():
    result = run("D")
    before = result.before_after["before"]
    after = result.before_after["after"]
    assert before["requested_calls"] > after["requested_calls"]
    assert after["available_agents"] == 60


def test_agent_availability_drop_reduces_safe_capacity():
    scenario = Scenario(
        "drop",
        0.5,
        90.0,
        collapse_answer_rate=0.5,
        agents_after_drop=60,
    )
    simulator = SmartDialerSimulator(SimulationConfig(seed=42))
    result = simulator.run(scenario)
    assert (
        result.before_after["before"]["approved_calls"]
        >= result.before_after["after"]["approved_calls"]
    )


def test_reproducible_with_same_seed():
    first = run("B").metrics
    second = run("B").metrics
    assert first == second


def test_provider_failures_and_event_defenses_are_measured():
    metrics = run("D").metrics
    assert metrics["provider_failures"] >= 0
    assert metrics["duplicate_provider_events"] >= 0
    assert metrics["out_of_order_provider_events"] >= 0


def test_no_real_telecom_api_is_used():
    text = open("app/simulation/simulator.py", encoding="utf-8").read()
    assert "requests." not in text
    assert "twilio" not in text.lower()
