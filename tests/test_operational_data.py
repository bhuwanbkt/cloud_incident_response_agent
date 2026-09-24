import pytest

from cloud_incident_response_agent.services.operational_data import (
    ServiceNotFoundError,
    get_recent_deployments,
    get_service_metrics,
    search_application_logs,
)


def test_get_service_metrics() -> None:
    metrics = get_service_metrics(
        "payment-api"
    )

    assert metrics["service_name"] == "payment-api"
    assert metrics["status"] == "degraded"
    assert metrics["error_rate_percent"] == 18.2
    assert metrics["p95_latency_ms"] == 4200


def test_search_error_logs() -> None:
    logs = search_application_logs(
        service_name="payment-api",
        level="ERROR",
    )

    assert len(logs) == 4

    assert all(
        log["level"] == "ERROR"
        for log in logs
    )


def test_search_logs_by_text() -> None:
    logs = search_application_logs(
        service_name="payment-api",
        search_text="connection pool",
    )

    assert len(logs) == 2

    assert all(
        "connection pool"
        in log["message"].casefold()
        for log in logs
    )


def test_search_logs_with_limit() -> None:
    logs = search_application_logs(
        service_name="payment-api",
        limit=2,
    )

    assert len(logs) == 2


def test_get_recent_deployments() -> None:
    deployments = get_recent_deployments(
        "payment-api"
    )

    assert len(deployments) == 2
    assert deployments[0]["version"] == "2.4.1"
    assert (
        deployments[0]["configuration"][
            "database_pool_size"
        ]
        == 10
    )


def test_unknown_service_raises_error() -> None:
    with pytest.raises(ServiceNotFoundError):
        get_service_metrics(
            "unknown-api"
        )


def test_invalid_service_name_raises_error() -> None:
    with pytest.raises(ValueError):
        get_service_metrics(
            "../../private"
        )


def test_invalid_log_limit_raises_error() -> None:
    with pytest.raises(ValueError):
        search_application_logs(
            service_name="payment-api",
            limit=0,
        )