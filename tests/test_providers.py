from app.providers.base import OutboundCall, TelecomProvider
from app.providers.manager import ProviderManager
from app.providers.provider_a import ProviderA
from app.providers.provider_b import ProviderB


def test_provider_a_success_and_failure():
    success = ProviderA(failure_probability=0, seed=1).initiate_call(
        OutboundCall("CALL-1", "ACC-1"),
    )
    failure = ProviderA(failure_probability=1, seed=1).initiate_call(
        OutboundCall("CALL-2", "ACC-2"),
    )
    assert success.accepted and success.provider_name == "provider_a"
    assert not failure.accepted and failure.error


def test_provider_b_timeout_is_reported():
    provider = ProviderB(timeout_probability=1, failure_probability=0, seed=1)
    response = provider.initiate_call(OutboundCall("CALL-1", "ACC-1"))
    assert not response.accepted
    assert response.error == "PROVIDER_B_TIMEOUT"


def test_provider_b_supports_bad_event_sequences():
    provider = ProviderB(failure_probability=0, timeout_probability=0, seed=1)
    call = OutboundCall("CALL-1", "ACC-1")
    response = provider.initiate_call(call)
    duplicate = provider.events_for(call, response, "duplicate_answered")
    out_of_order = provider.events_for(call, response, "out_of_order")
    assert [event.event_type.value for event in duplicate].count(
        "ANSWERED"
    ) == 2
    assert out_of_order[0].event_type.value == "COMPLETED"


def test_manager_selects_fast_healthy_provider():
    slow = ProviderB(
        latency_ms=5000, failure_probability=0, timeout_probability=0
    )
    fast = ProviderA(latency_ms=50, failure_probability=0)
    manager = ProviderManager([slow, fast])
    assert manager.select_healthy() is fast


def test_manager_does_not_select_unhealthy_provider():
    unhealthy = ProviderA(failure_probability=1, seed=1)
    unhealthy.initiate_call(OutboundCall("1", "A"))
    manager = ProviderManager([unhealthy])
    assert manager.select_healthy() is None


def test_provider_specific_implementation_is_behind_interface():
    assert isinstance(ProviderA(), TelecomProvider)
    assert isinstance(ProviderB(), TelecomProvider)
