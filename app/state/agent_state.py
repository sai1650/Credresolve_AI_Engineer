"""Thread-safe full agent lifecycle state machine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock


class AgentState(str, Enum):
    OFFLINE = "OFFLINE"
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    DIALING = "DIALING"
    CONNECTED = "CONNECTED"
    WRAP_UP = "WRAP_UP"
    PAUSED = "PAUSED"


@dataclass
class AgentStateMachine:
    agent_id: int
    state: AgentState = AgentState.OFFLINE

    def __post_init__(self) -> None:
        self._lock = Lock()

    def transition(self, target: AgentState) -> None:
        allowed = {
            AgentState.OFFLINE: {AgentState.AVAILABLE},
            AgentState.AVAILABLE: {
                AgentState.RESERVED,
                AgentState.PAUSED,
                AgentState.OFFLINE,
            },
            AgentState.RESERVED: {AgentState.DIALING, AgentState.AVAILABLE},
            AgentState.DIALING: {AgentState.CONNECTED, AgentState.AVAILABLE},
            AgentState.CONNECTED: {AgentState.WRAP_UP},
            AgentState.WRAP_UP: {AgentState.AVAILABLE},
            AgentState.PAUSED: {AgentState.AVAILABLE, AgentState.OFFLINE},
        }
        with self._lock:
            if target not in allowed[self.state]:
                raise ValueError(
                    f"invalid agent transition: {self.state} -> {target}"
                )
            self.state = target

    def make_available(self) -> None:
        self.transition(AgentState.AVAILABLE)
