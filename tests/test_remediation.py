import pytest

from cloud_incident_response_agent.services.remediation import (
    RemediationError,
    simulate_rollback,
)


def test_simulate_rollback() -> None:
    result = simulate_rollback(
        service_name="payment-api",
        current_version="2.4.1",
        target_version="2.4.0",
    )

    assert result["status"] == "simulated_success"
    assert result["changes_applied"] is False
    assert result["current_version"] == "2.4.1"
    assert result["target_version"] == "2.4.0"


def test_unknown_target_version() -> None:
    with pytest.raises(RemediationError):
        simulate_rollback(
            service_name="payment-api",
            current_version="2.4.1",
            target_version="1.0.0",
        )


def test_same_version_is_rejected() -> None:
    with pytest.raises(RemediationError):
        simulate_rollback(
            service_name="payment-api",
            current_version="2.4.1",
            target_version="2.4.1",
        )