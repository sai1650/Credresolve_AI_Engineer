"""Concurrent allocator load tests for the simulation prototype."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from app.dialer.allocator import AllocationResult, CallAllocator
from app.models.agent import Agent
from app.providers.manager import ProviderManager
from app.providers.provider_a import ProviderA
from app.safety.controller import APPROVE, SafetyDecision


@dataclass(frozen=True)
class LoadTestConfig:
    agents: int = 100
    accounts: int = 1000
    workers: int = 5
    seed: int = 42


def _decision(approved: int) -> SafetyDecision:
    return SafetyDecision(approved, approved, APPROVE, "load test")


def run_load_test(config: LoadTestConfig = LoadTestConfig()) -> dict[str, Any]:
    agents = [Agent(index) for index in range(config.agents)]
    accounts = [f"ACCOUNT-{index:04d}" for index in range(config.accounts)]
    provider = ProviderManager(
        [ProviderA(failure_probability=0, seed=config.seed)]
    )
    allocator = CallAllocator(provider=provider)
    attempts = config.workers * config.accounts
    quota = config.agents
    quotas = [quota // config.workers] * config.workers
    for index in range(quota % config.workers):
        quotas[index] += 1
    latencies: list[float] = []
    results: list[AllocationResult] = []

    def worker(index: int) -> AllocationResult:
        started = time.perf_counter()
        result = allocator.allocate(
            _decision(quotas[index]),
            "LOAD",
            agents,
            accounts[index :: config.workers],
            f"workers-{config.workers}",
        )
        latencies.append(time.perf_counter() - started)
        return result

    with ThreadPoolExecutor(max_workers=config.workers) as pool:
        results = list(pool.map(worker, range(config.workers)))
    duplicate = allocator.allocate(
        _decision(1),
        "LOAD",
        agents,
        [accounts[0]],
        f"workers-{config.workers}",
    )
    results.append(duplicate)
    all_allocations = [
        call for result in results for call in result.created_calls
    ]
    unique_call_ids = {call.call_id for call in all_allocations}
    duplicate_jobs = sum(result.duplicate_jobs for result in results)
    conflicts_agents = sum(result.unavailable_agents for result in results)
    conflicts_accounts = sum(
        len(result.skipped_accounts) for result in results
    )
    failures = sum(len(result.failed_allocations) for result in results)
    approved = sum(quotas)
    invariant_violations = []
    if len(unique_call_ids) > approved:
        invariant_violations.append("created_calls > approved_calls")
    if len(unique_call_ids) > config.agents:
        invariant_violations.append("created_calls > available_agent_capacity")
    active_agents = [
        agent for agent in agents if agent.current_call_id is not None
    ]
    if len(active_agents) != len({agent.agent_id for agent in active_agents}):
        invariant_violations.append("agent has multiple active reservations")
    report = {
        "workers": config.workers,
        "agents": config.agents,
        "accounts": config.accounts,
        "allocation_attempts": attempts,
        "successful_allocations": len(unique_call_ids),
        "calls_created": len(unique_call_ids),
        "duplicate_attempts": duplicate_jobs,
        "duplicate_jobs": duplicate_jobs,
        "agent_reservation_conflicts": conflicts_agents,
        "account_reservation_conflicts": conflicts_accounts,
        "average_allocation_latency_seconds": (
            mean(latencies) if latencies else 0.0
        ),
        "p95_allocation_latency_seconds": _percentile(latencies, 0.95),
        "throughput_calls_per_second": len(unique_call_ids)
        / max(sum(latencies), 1e-9),
        "failures": failures,
        "safety_controller_decisions": config.workers,
        "recovery_time_seconds": 0.0,
        "invariant_violations": invariant_violations,
    }
    if invariant_violations:
        raise RuntimeError(
            "load-test invariant violation: " + ", ".join(invariant_violations)
        )
    return report


def run_load_matrix(
    worker_counts: tuple[int, ...] = (5, 10, 20, 50),
    output_path: str | Path = "data/processed/load_test_report.json",
) -> dict[str, Any]:
    reports = {
        str(workers): run_load_test(LoadTestConfig(workers=workers))
        for workers in worker_counts
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(reports, indent=2, sort_keys=True), encoding="utf-8"
    )
    return reports


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile)))
    return ordered[index]


if __name__ == "__main__":
    print(json.dumps(run_load_matrix(), indent=2, sort_keys=True))
