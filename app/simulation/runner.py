"""Command-line reporting for SmartDialer simulation scenarios."""

from __future__ import annotations

from app.simulation.scenarios import SimulationConfig, scenarios
from app.simulation.simulator import SmartDialerSimulator


def run(names: list[str] | None = None, seed: int = 42) -> list[dict]:
    selected = names or ["A", "B", "C", "D"]
    simulator = SmartDialerSimulator(SimulationConfig(seed=seed))
    results = []
    for name in selected:
        result = simulator.run(scenarios()[name])
        results.append(
            {
                "scenario": result.scenario,
                **result.metrics,
                "before_after": result.before_after,
            }
        )
    return results


def print_results(results: list[dict]) -> None:
    print(
        "Scenario | Answer Rate | Avg Talk Time | Calls Initiated | "
        "Calls Connected | Utilization | Safety Reductions | Provider Failures"
    )
    for result in results:
        print(
            f"{result['scenario']} | {result['answer_rate']:.3f} | "
            f"{result['average_talk_time_seconds']:.1f} | "
            f"{result['total_calls_initiated']} | "
            f"{result['total_calls_connected']} | "
            f"{result['agent_utilization']:.3f} | "
            f"{result['safety_reductions']} | "
            f"{result['provider_failures']}"
        )
        for entry in result["pacing_log"]:
            print(
                f"  {entry['timestamp']}: agents={entry['available_agents']} "
                f"requested={entry['requested_calls']} "
                f"approved={entry['approved_calls']} "
                f"action={entry['safety_action']} reason={entry['reason']}"
            )
        if result["scenario"] == "D":
            print("  Scenario D before/after:", result["before_after"])


if __name__ == "__main__":
    print_results(run())
