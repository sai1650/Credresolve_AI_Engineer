"""Explainable historical estimators built from canonical call events."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Iterable

from app.data.normalization import CanonicalEvent


@dataclass
class AnswerRateEstimator:
    """Estimate answer probability with a smoothed historical rate."""

    prior_answered: float = 1.0
    prior_calls: float = 2.0

    def fit(self, events: Iterable[CanonicalEvent]) -> None:
        calls = [event for event in events if event.event_type == "CALL"]
        answered = sum(event.outcome == "ANSWERED" for event in calls)
        self.prior_answered += answered
        self.prior_calls += len(calls)

    @property
    def answer_rate(self) -> float:
        return self.prior_answered / self.prior_calls


@dataclass
class TalkTimeEstimator:
    """Estimate average connected talk time from answered calls."""

    default_seconds: float = 300.0
    average_seconds: float | None = None

    def fit(self, events: Iterable[CanonicalEvent]) -> None:
        durations = [
            event.duration_sec
            for event in events
            if event.event_type == "CALL"
            and event.outcome == "ANSWERED"
            and event.duration_sec is not None
            and event.duration_sec > 0
        ]
        if durations:
            self.average_seconds = fmean(durations)

    @property
    def talk_time_seconds(self) -> float:
        return self.average_seconds or self.default_seconds
