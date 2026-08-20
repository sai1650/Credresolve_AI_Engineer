"""Agent state used by the dialer allocator."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class Agent:
    agent_id: int
    current_call_id: str | None = None

    def __post_init__(self) -> None:
        self.state = "AVAILABLE"
        self._lock = Lock()

    def reserve(self, call_id: str) -> None:
        with self._lock:
            if self.state != "AVAILABLE" or self.current_call_id is not None:
                raise RuntimeError("agent is already reserved")
            self.current_call_id = call_id
            self.state = "RESERVED"

    def start_call(self) -> None:
        with self._lock:
            if self.state != "RESERVED":
                raise RuntimeError("agent is not reserved")
            self.state = "DIALING"

    def release(self) -> None:
        with self._lock:
            self.current_call_id = None
            self.state = "AVAILABLE"
