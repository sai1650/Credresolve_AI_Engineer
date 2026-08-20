import pytest

from app.dialer.progressive import ProgressiveDialer
from app.state.agent_state import AgentState, AgentStateMachine


def test_progressive_is_bounded_by_agents_and_queue():
    assert ProgressiveDialer().recommend(60, 100).requested_calls == 60
    assert ProgressiveDialer().recommend(100, 30).requested_calls == 30


def test_full_agent_state_machine_transitions():
    machine = AgentStateMachine(1)
    machine.make_available()
    for target in (
        AgentState.RESERVED,
        AgentState.DIALING,
        AgentState.CONNECTED,
        AgentState.WRAP_UP,
        AgentState.AVAILABLE,
        AgentState.PAUSED,
        AgentState.AVAILABLE,
    ):
        machine.transition(target)
    assert machine.state == AgentState.AVAILABLE


def test_full_agent_state_machine_rejects_invalid_transition():
    machine = AgentStateMachine(1)
    with pytest.raises(ValueError):
        machine.transition(AgentState.CONNECTED)
