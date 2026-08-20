from app.main import (
    SimulationRequest,
    dashboard_summary,
    providers,
    run_simulation,
)


def test_dashboard_api_returns_simulation_data():
    summary = dashboard_summary()
    assert summary["scenario"] == "A"
    assert "total_calls_initiated" in summary


def test_provider_health_endpoint_uses_provider_manager():
    health = providers()
    assert set(health) == {"provider_a", "provider_b"}
    assert "latency_ms" in health["provider_a"]


def test_simulation_api_runs_real_scenario():
    result = run_simulation(SimulationRequest(scenario="D", seed=42))
    assert result["scenario"] == "D"
    assert result["total_calls_initiated"] >= 0
