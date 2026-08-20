"""Explainable, provider-independent predictive pacing recommendations."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import floor


@dataclass(frozen=True)
class PacingState:
    """The operational signals required to make one pacing recommendation."""

    available_agents: int
    connected_calls: int
    ringing_calls: int
    answer_probability: float | None
    historical_answer_rate: float
    average_talk_time_seconds: float
    recent_call_volume: int = 0
    provider_health: float = 1.0
    provider_latency_ms: float = 0.0
    provider_failure_rate: float = 0.0
    campaign_answer_rate: float | None = None
    recent_pacing_decisions: tuple[int, ...] = field(default_factory=tuple)
    previous_available_agents: int | None = None


@dataclass(frozen=True)
class PacingDecision:
    requested_calls: int
    estimated_answers: float
    estimated_agent_demand: float
    estimated_utilization: float
    pacing_factor: float
    reason: str
    confidence: float
    fallback_recommended: bool


class PredictivePacingEngine:
    """Recommend work without knowing about providers."""

    def __init__(
        self,
        max_recommendation: int = 100,
        target_utilization: float = 0.85,
        target_time_window_seconds: float = 300.0,
        max_outstanding_per_agent: float = 2.0,
    ) -> None:
        if max_recommendation < 0:
            raise ValueError("max_recommendation must be non-negative")
        if not 0 < target_utilization <= 1:
            raise ValueError("target_utilization must be in (0, 1]")
        if target_time_window_seconds <= 0 or max_outstanding_per_agent <= 0:
            raise ValueError("planning limits must be positive")
        self.max_recommendation = max_recommendation
        self.target_utilization = target_utilization
        self.target_time_window_seconds = target_time_window_seconds
        self.max_outstanding_per_agent = max_outstanding_per_agent

    def calculate_pacing(self, state: PacingState) -> PacingDecision:
        self._validate_state(state)
        probability, fallback = self._effective_probability(state)
        health_factor = self._provider_factor(state)
        availability_factor = self._availability_factor(state)
        deterioration_factor = self._recent_answer_factor(state, probability)
        decision_factor = self._recent_decision_factor(state)
        ringing_load = state.connected_calls + state.ringing_calls
        capacity = max(
            0.0,
            state.available_agents * self.max_outstanding_per_agent
            - ringing_load,
        )
        demand_per_call = (
            probability
            * state.average_talk_time_seconds
            / self.target_time_window_seconds
        )
        raw_capacity = (
            state.available_agents
            * self.target_utilization
            / max(demand_per_call, 0.01)
        )
        factor = (
            health_factor
            * availability_factor
            * deterioration_factor
            * decision_factor
        )
        proposed = min(
            capacity * factor,
            raw_capacity * factor,
            float(self.max_recommendation),
        )
        if state.recent_call_volume > 0:
            proposed = min(proposed, float(state.recent_call_volume))
        requested = max(0, floor(proposed))
        estimated_answers = requested * probability
        estimated_demand = (
            estimated_answers
            * state.average_talk_time_seconds
            / self.target_time_window_seconds
        )
        utilization = min(
            1.0, estimated_demand / max(state.available_agents, 1)
        )
        confidence = self._confidence(state, fallback, health_factor)
        reasons = self._reasons(
            state,
            fallback,
            health_factor,
            availability_factor,
            deterioration_factor,
            decision_factor,
        )
        return PacingDecision(
            requested_calls=requested,
            estimated_answers=estimated_answers,
            estimated_agent_demand=estimated_demand,
            estimated_utilization=utilization,
            pacing_factor=factor,
            reason="; ".join(reasons),
            confidence=confidence,
            fallback_recommended=fallback,
        )

    @staticmethod
    def _validate_state(state: PacingState) -> None:
        if (
            min(
                state.available_agents,
                state.connected_calls,
                state.ringing_calls,
                state.recent_call_volume,
            )
            < 0
        ):
            raise ValueError("counts cannot be negative")
        if state.average_talk_time_seconds <= 0:
            raise ValueError("average_talk_time_seconds must be positive")
        for value in (state.provider_health, state.provider_failure_rate):
            if not 0 <= value <= 1:
                raise ValueError("provider rates must be between 0 and 1")

    @staticmethod
    def _effective_probability(state: PacingState) -> tuple[float, bool]:
        probability = state.answer_probability
        fallback = probability is None
        if fallback:
            probability = state.historical_answer_rate
        probability = min(1.0, max(0.0, probability))
        return probability, fallback

    @staticmethod
    def _provider_factor(state: PacingState) -> float:
        latency_factor = max(
            0.5, 1.0 - max(0.0, state.provider_latency_ms - 200.0) / 1800.0
        )
        failure_factor = 1.0 - state.provider_failure_rate
        return min(
            1.0,
            max(0.0, state.provider_health * latency_factor * failure_factor),
        )

    @staticmethod
    def _availability_factor(state: PacingState) -> float:
        if (
            state.previous_available_agents is None
            or state.previous_available_agents <= 0
        ):
            return 1.0
        ratio = state.available_agents / state.previous_available_agents
        return min(1.0, max(0.5, ratio))

    @staticmethod
    def _recent_answer_factor(state: PacingState, probability: float) -> float:
        if state.campaign_answer_rate is None:
            return 1.0
        recent = min(1.0, max(0.0, state.campaign_answer_rate))
        return min(1.0, max(0.5, recent / max(probability, 0.01)))

    def _recent_decision_factor(self, state: PacingState) -> float:
        if not state.recent_pacing_decisions:
            return 1.0
        recent_average = sum(state.recent_pacing_decisions) / len(
            state.recent_pacing_decisions
        )
        reference = max(
            1.0, state.available_agents * self.max_outstanding_per_agent
        )
        return min(1.0, max(0.5, 1.0 - recent_average / (reference * 4.0)))

    def _confidence(
        self, state: PacingState, fallback: bool, health_factor: float
    ) -> float:
        confidence = 0.5 if fallback else 0.8
        if state.campaign_answer_rate is not None:
            confidence += 0.1
        return min(1.0, max(0.0, confidence * health_factor))

    @staticmethod
    def _reasons(
        state: PacingState,
        fallback: bool,
        health: float,
        availability: float,
        deterioration: float,
        decision_factor: float,
    ) -> list[str]:
        reasons = ["capacity-based recommendation"]
        if fallback:
            reasons.append(
                "using conservative historical answer rate; "
                "prediction unavailable"
            )
        if state.ringing_calls:
            reasons.append(f"{state.ringing_calls} calls already ringing")
        if health < 0.99:
            reasons.append("provider latency/failures reduce pacing")
        if availability < 0.99:
            reasons.append("agent availability dropped")
        if deterioration < 0.99:
            reasons.append("recent answer rate is below the estimate")
        if decision_factor < 0.99:
            reasons.append("recent pacing volume is being damped")
        if state.average_talk_time_seconds > 300:
            reasons.append("long talk time reduces capacity")
        return reasons


def calculate_pacing(
    state: PacingState, **kwargs: float | int
) -> PacingDecision:
    """Convenience function for a default configured engine."""
    return PredictivePacingEngine(**kwargs).calculate_pacing(state)
