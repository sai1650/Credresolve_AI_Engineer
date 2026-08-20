"""Metrics collected from simulation decisions, allocations, and events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimulationMetrics:
    total_calls_initiated: int = 0
    total_calls_connected: int = 0
    total_calls_completed: int = 0
    total_calls_failed: int = 0
    total_answered: int = 0
    total_talk_time_seconds: float = 0.0
    connected_agent_seconds: float = 0.0
    available_agent_seconds: float = 0.0
    peak_ringing_calls: int = 0
    ringing_samples: list[int] = field(default_factory=list)
    pacing_recommendations: int = 0
    safety_approvals: int = 0
    safety_reductions: int = 0
    safety_rejections: int = 0
    progressive_fallbacks: int = 0
    provider_failures: int = 0
    provider_latency_ms: list[float] = field(default_factory=list)
    duplicate_provider_events: int = 0
    out_of_order_provider_events: int = 0
    allocation_failures: int = 0
    stale_reservation_recoveries: int = 0
    pacing_log: list[dict[str, Any]] = field(default_factory=list)
    invariant_failures: list[str] = field(default_factory=list)

    def record_safety(self, decision: Any) -> None:
        self.pacing_recommendations += 1
        self.safety_approvals += int(decision.action == "APPROVE")
        self.safety_reductions += int(decision.action == "REDUCE")
        self.safety_rejections += int(decision.action == "REJECT")
        self.progressive_fallbacks += int(
            decision.action == "FALLBACK_TO_PROGRESSIVE"
        )

    def finalize(self) -> dict[str, Any]:
        answer_rate = (
            self.total_answered / self.total_calls_initiated
            if self.total_calls_initiated
            else 0.0
        )
        average_talk = (
            self.total_talk_time_seconds / self.total_answered
            if self.total_answered
            else 0.0
        )
        utilization = (
            self.connected_agent_seconds / self.available_agent_seconds
            if self.available_agent_seconds
            else 0.0
        )
        return {
            "total_calls_initiated": self.total_calls_initiated,
            "total_calls_connected": self.total_calls_connected,
            "total_calls_completed": self.total_calls_completed,
            "total_calls_failed": self.total_calls_failed,
            "answer_rate": answer_rate,
            "average_talk_time_seconds": average_talk,
            "agent_utilization": utilization,
            "peak_ringing_calls": self.peak_ringing_calls,
            "average_ringing_calls": (
                sum(self.ringing_samples) / len(self.ringing_samples)
                if self.ringing_samples
                else 0.0
            ),
            "pacing_recommendations": self.pacing_recommendations,
            "safety_approvals": self.safety_approvals,
            "safety_reductions": self.safety_reductions,
            "safety_rejections": self.safety_rejections,
            "progressive_fallbacks": self.progressive_fallbacks,
            "provider_failures": self.provider_failures,
            "provider_latency_ms": (
                sum(self.provider_latency_ms) / len(self.provider_latency_ms)
                if self.provider_latency_ms
                else 0.0
            ),
            "duplicate_provider_events": self.duplicate_provider_events,
            "out_of_order_provider_events": self.out_of_order_provider_events,
            "allocation_failures": self.allocation_failures,
            "stale_reservation_recoveries": self.stale_reservation_recoveries,
            "invariant_failures": list(self.invariant_failures),
            "pacing_log": list(self.pacing_log),
        }
