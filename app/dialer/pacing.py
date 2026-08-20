"""Predictive pacing recommendations; this module never places calls."""

from __future__ import annotations

from dataclasses import dataclass

from app.dialer.estimators import AnswerRateEstimator, TalkTimeEstimator


@dataclass(frozen=True)
class PacingRecommendation:
    calls_to_offer: int
    answer_rate: float
    expected_talk_time_seconds: float


class PredictivePacing:
    def __init__(
        self,
        answer_rate: AnswerRateEstimator,
        talk_time: TalkTimeEstimator,
        pacing_factor: float = 1.0,
    ) -> None:
        if pacing_factor <= 0:
            raise ValueError("pacing_factor must be positive")
        self.answer_rate = answer_rate
        self.talk_time = talk_time
        self.pacing_factor = pacing_factor

    def recommend(
        self, available_agents: int, queued_calls: int
    ) -> PacingRecommendation:
        if available_agents < 0 or queued_calls < 0:
            raise ValueError("agent and queue counts cannot be negative")
        desired = round(available_agents * self.pacing_factor)
        return PacingRecommendation(
            calls_to_offer=min(desired, queued_calls),
            answer_rate=self.answer_rate.answer_rate,
            expected_talk_time_seconds=self.talk_time.talk_time_seconds,
        )
