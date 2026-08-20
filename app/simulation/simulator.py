"""Deterministic end-to-end SmartDialer simulation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import Any

from app.dialer.allocator import AllocationResult, CallAllocator
from app.dialer.predictive import PacingState, PredictivePacingEngine
from app.models.agent import Agent
from app.providers.events import CallState, ProviderEventProcessor
from app.providers.manager import ProviderManager
from app.providers.provider_a import ProviderA
from app.providers.provider_b import ProviderB
from app.safety.controller import SafetyController, SafetyState
from app.simulation.metrics import SimulationMetrics
from app.simulation.scenarios import Scenario, SimulationConfig


@dataclass
class SimulationResult:
    scenario: str
    metrics: dict[str, Any]
    before_after: dict[str, Any]


class SmartDialerSimulator:
    def __init__(self, config: SimulationConfig | None = None) -> None:
        self.config = config or SimulationConfig()

    def run(self, scenario: Scenario) -> SimulationResult:
        metrics = SimulationMetrics()
        agents = [Agent(index) for index in range(self.config.agents)]
        accounts = [
            f"ACCOUNT-{index:04d}" for index in range(self.config.accounts)
        ]
        providers = self._providers(scenario)
        manager = ProviderManager(providers)
        pacing = PredictivePacingEngine(
            max_recommendation=self.config.agents * 2
        )
        safety = SafetyController()
        allocator = CallAllocator(provider=manager)
        before = self._phase(
            scenario,
            scenario.answer_rate,
            len(agents),
            agents,
            accounts,
            manager,
            pacing,
            safety,
            allocator,
            metrics,
            "before",
            0,
        )
        after = before
        if scenario.collapse_answer_rate is not None:
            after_agents = scenario.agents_after_drop or len(agents)
            after = self._phase(
                scenario,
                scenario.collapse_answer_rate,
                after_agents,
                agents,
                accounts[100:],
                manager,
                pacing,
                safety,
                allocator,
                metrics,
                "after",
                1,
            )
        metrics.stale_reservation_recoveries += (
            allocator.recover_stale_reservations(
                now=10**9,
            )
        )
        metrics.provider_failures = sum(
            provider.metrics.failed for provider in providers
        )
        return SimulationResult(
            scenario.name,
            metrics.finalize(),
            {
                "before": before,
                "after": after,
            },
        )

    def _phase(
        self,
        scenario: Scenario,
        answer_rate: float,
        available_agents: int,
        agents: list[Agent],
        accounts: list[str],
        manager: ProviderManager,
        pacing: PredictivePacingEngine,
        safety: SafetyController,
        allocator: CallAllocator,
        metrics: SimulationMetrics,
        label: str,
        phase_number: int,
    ) -> dict[str, Any]:
        health_values = list(manager.health().values())
        healthy = [item for item in health_values if item.healthy]
        provider_health = any(item.healthy for item in health_values)
        latency = min((item.latency_ms for item in healthy), default=0.0)
        failure_rate = max(
            (item.failure_rate for item in health_values), default=1.0
        )
        connected = metrics.total_calls_connected
        ringing = 0
        state = PacingState(
            available_agents=available_agents,
            connected_calls=connected,
            ringing_calls=ringing,
            answer_probability=(
                scenario.answer_rate if label == "after" else answer_rate
            ),
            historical_answer_rate=answer_rate,
            average_talk_time_seconds=scenario.average_talk_time_seconds,
            recent_call_volume=len(accounts),
            provider_health=float(provider_health),
            provider_latency_ms=latency,
            provider_failure_rate=failure_rate,
            campaign_answer_rate=answer_rate,
            previous_available_agents=(
                self.config.agents if label == "after" else None
            ),
        )
        pacing_decision = pacing.calculate_pacing(state)
        safety_state = SafetyState(
            available_agents=available_agents,
            connected_calls=connected,
            ringing_calls=ringing,
            provider_health=float(provider_health),
            provider_latency_ms=latency,
            provider_failure_rate=failure_rate,
            provider_available=scenario.provider_available and bool(healthy),
            previous_available_agents=(
                self.config.agents if label == "after" else None
            ),
        )
        safety_decision = safety.evaluate(pacing_decision, safety_state)
        metrics.record_safety(safety_decision)
        metrics.pacing_log.append(
            {
                "timestamp": label,
                "available_agents": available_agents,
                "connected_calls": connected,
                "ringing_calls": ringing,
                "estimated_answer_rate": answer_rate,
                "estimated_talk_time": scenario.average_talk_time_seconds,
                "provider_health": provider_health,
                "requested_calls": pacing_decision.requested_calls,
                "approved_calls": safety_decision.approved_calls,
                "safety_action": safety_decision.action,
                "reason": (
                    f"{safety_decision.reason}; pacing: "
                    f"{pacing_decision.reason}"
                ),
            }
        )
        result = self._allocate_workers(
            allocator,
            safety_decision,
            agents[:available_agents],
            accounts,
            phase_number,
        )
        metrics.total_calls_failed += len(result.failed_allocations)
        if result.created_calls:
            self._process_events(
                result,
                manager,
                metrics,
                scenario,
                phase_number,
                answer_rate,
            )
        self._check_invariants(
            result, safety_decision, available_agents, metrics
        )
        return {
            "available_agents": available_agents,
            "requested_calls": pacing_decision.requested_calls,
            "approved_calls": safety_decision.approved_calls,
            "action": safety_decision.action,
            "reason": (
                f"{safety_decision.reason}; pacing: "
                f"{pacing_decision.reason}"
            ),
        }

    def _allocate_workers(
        self,
        allocator: CallAllocator,
        decision: Any,
        agents: list[Agent],
        accounts: list[str],
        phase: int,
    ) -> AllocationResult:
        chunks = [
            accounts[index :: self.config.workers]
            for index in range(self.config.workers)
        ]
        quotas = [
            decision.approved_calls // self.config.workers
        ] * self.config.workers
        for index in range(decision.approved_calls % self.config.workers):
            quotas[index] += 1

        def allocate(chunk: list[str], quota: int) -> AllocationResult:
            worker_decision = replace(
                decision,
                approved_calls=quota,
                requested_calls=quota,
            )
            return allocator.allocate(
                worker_decision,
                self.config.campaign_id,
                agents,
                chunk,
                f"{self.config.allocation_window}-{phase}",
            )

        with ThreadPoolExecutor(max_workers=self.config.workers) as pool:
            results = list(pool.map(allocate, chunks, quotas))
        combined = AllocationResult()
        for result in results:
            combined.created_calls.extend(result.created_calls)
            combined.failed_allocations.extend(result.failed_allocations)
            combined.skipped_accounts.extend(result.skipped_accounts)
            combined.unavailable_agents += result.unavailable_agents
            combined.duplicate_jobs += result.duplicate_jobs
        return combined

    @staticmethod
    def _process_events(
        result: AllocationResult,
        manager: ProviderManager,
        metrics: SimulationMetrics,
        scenario: Scenario,
        phase: int,
        answer_rate: float,
    ) -> None:
        for allocation in result.created_calls:
            metrics.total_calls_initiated += 1
            metrics.available_agent_seconds += 300.0
            response = manager.response_for_call(allocation.call_id)
            if response is None:
                metrics.allocation_failures += 1
                continue
            health = manager.health().get(response.provider_name)
            if health is not None:
                metrics.provider_latency_ms.append(health.latency_ms)
            mode = "normal"
            if scenario.name == "D" and phase == 1:
                mode = (
                    "out_of_order"
                    if allocation.call_id.endswith("1")
                    else "duplicate_answered"
                )
            events = manager.events_for_call_id(
                allocation.call_id,
                allocation.account_id,
                mode,
            )
            call_number = int(allocation.call_id[-4:])
            answered = (call_number * 37) % 1000 < answer_rate * 1000
            if not answered and events:
                events = [events[0], events[-1]]
                events[-1] = type(events[-1])(
                    f"{events[-1].event_id}-failed",
                    events[-1].provider_call_id,
                    events[-1].call_id,
                    CallState.FAILED,
                    events[-1].event_time,
                    events[-1].provider_name,
                    events[-1].sequence_number,
                )
            connected = False
            processor = ProviderEventProcessor(CallState.INITIATED)
            for event in events:
                process = processor.process(event)
                if not process.accepted:
                    if "duplicate" in process.reason:
                        metrics.duplicate_provider_events += 1
                    else:
                        metrics.out_of_order_provider_events += 1
                if process.accepted and process.state == CallState.ANSWERED:
                    metrics.total_answered += 1
                if process.accepted and process.state == CallState.CONNECTED:
                    metrics.total_calls_connected += 1
                    connected = True
                if process.accepted and process.state == CallState.COMPLETED:
                    metrics.total_calls_completed += 1
            if not response.accepted:
                metrics.total_calls_failed += 1
                metrics.provider_failures += 1
            if connected:
                metrics.total_talk_time_seconds += (
                    scenario.average_talk_time_seconds
                )
                metrics.connected_agent_seconds += (
                    scenario.average_talk_time_seconds
                )
            allocation.agent.release()

    @staticmethod
    def _check_invariants(
        result: AllocationResult,
        decision: Any,
        available_agents: int,
        metrics: SimulationMetrics,
    ) -> None:
        created = len(result.created_calls)
        approved = decision.approved_calls
        safe_capacity = decision.safety_checks.get(
            "safe_capacity", available_agents
        )
        if approved > safe_capacity:
            raise RuntimeError("approved_calls exceeded safety capacity")
        if created > approved:
            raise RuntimeError("created_calls exceeded approved_calls")
        if created > available_agents:
            raise RuntimeError("created_calls exceeded agent capacity")
        metrics.allocation_failures += len(result.failed_allocations)

    @staticmethod
    def _providers(scenario: Scenario) -> list[Any]:
        return [
            ProviderA(
                latency_ms=scenario.provider_a_latency_ms,
                failure_probability=scenario.provider_a_failure_probability,
                seed=42,
            ),
            ProviderB(
                latency_ms=scenario.provider_b_latency_ms,
                failure_probability=scenario.provider_b_failure_probability,
                timeout_probability=scenario.provider_b_timeout_probability,
                seed=43,
            ),
        ]
