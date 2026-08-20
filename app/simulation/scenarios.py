"""Configurable simulation scenarios and workload settings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationConfig:
    agents: int = 100
    accounts: int = 1000
    workers: int = 5
    seed: int = 42
    campaign_id: str = "SIM-CAMPAIGN"
    allocation_window: str = "simulation-window"


@dataclass(frozen=True)
class Scenario:
    name: str
    answer_rate: float
    average_talk_time_seconds: float
    provider_a_failure_probability: float = 0.02
    provider_b_failure_probability: float = 0.15
    provider_b_timeout_probability: float = 0.10
    provider_a_latency_ms: float = 80.0
    provider_b_latency_ms: float = 450.0
    provider_available: bool = True
    collapse_answer_rate: float | None = None
    agents_after_drop: int | None = None


def scenarios() -> dict[str, Scenario]:
    return {
        "A": Scenario("A", 0.20, 120.0),
        "B": Scenario("B", 0.50, 90.0),
        "C": Scenario("C", 0.70, 180.0),
        "D": Scenario(
            "D",
            0.70,
            180.0,
            provider_a_failure_probability=0.02,
            provider_b_failure_probability=0.35,
            provider_b_timeout_probability=0.20,
            provider_b_latency_ms=1500.0,
            collapse_answer_rate=0.10,
            agents_after_drop=60,
        ),
    }
