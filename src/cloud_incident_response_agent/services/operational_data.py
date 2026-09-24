import json
from pathlib import Path
from typing import Any

from cloud_incident_response_agent.config import (
    get_settings,
)


settings = get_settings()


class OperationalDataError(Exception):
    """Base exception for operational-data failures."""


class ServiceNotFoundError(OperationalDataError):
    """Raised when data for a service does not exist."""


def validate_service_name(
    service_name: str,
) -> str:
    normalized_name = service_name.strip().casefold()

    if not normalized_name:
        raise ValueError(
            "Service name cannot be empty."
        )

    allowed_characters = set(
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789-_"
    )

    if not set(normalized_name).issubset(
        allowed_characters
    ):
        raise ValueError(
            "Service name contains unsupported characters."
        )

    return normalized_name


def load_json_file(
    file_path: Path,
) -> Any:
    if not file_path.exists():
        raise ServiceNotFoundError(
            f"Operational data was not found: "
            f"{file_path.name}"
        )

    try:
        with file_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)
    except json.JSONDecodeError as error:
        raise OperationalDataError(
            f"Invalid JSON in {file_path.name}."
        ) from error


def get_service_metrics(
    service_name: str,
) -> dict[str, Any]:
    normalized_name = validate_service_name(
        service_name
    )

    file_path = (
        settings.metric_directory
        / f"{normalized_name}.json"
    )

    data = load_json_file(file_path)

    if not isinstance(data, dict):
        raise OperationalDataError(
            "Metric data must be a JSON object."
        )

    return data


def search_application_logs(
    service_name: str,
    search_text: str | None = None,
    level: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    normalized_name = validate_service_name(
        service_name
    )

    if limit < 1 or limit > 100:
        raise ValueError(
            "Limit must be between 1 and 100."
        )

    file_path = (
        settings.log_directory
        / f"{normalized_name}.json"
    )

    data = load_json_file(file_path)

    if not isinstance(data, list):
        raise OperationalDataError(
            "Log data must be a JSON array."
        )

    filtered_logs = data

    if level:
        normalized_level = level.strip().casefold()

        filtered_logs = [
            log
            for log in filtered_logs
            if str(
                log.get("level", "")
            ).casefold()
            == normalized_level
        ]

    if search_text:
        normalized_search = (
            search_text.strip().casefold()
        )

        filtered_logs = [
            log
            for log in filtered_logs
            if normalized_search
            in str(
                log.get("message", "")
            ).casefold()
        ]

    sorted_logs = sorted(
        filtered_logs,
        key=lambda log: str(
            log.get("timestamp", "")
        ),
        reverse=True,
    )

    return sorted_logs[:limit]


def get_recent_deployments(
    service_name: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    normalized_name = validate_service_name(
        service_name
    )

    if limit < 1 or limit > 20:
        raise ValueError(
            "Limit must be between 1 and 20."
        )

    file_path = (
        settings.deployment_directory
        / f"{normalized_name}.json"
    )

    data = load_json_file(file_path)

    if not isinstance(data, list):
        raise OperationalDataError(
            "Deployment data must be a JSON array."
        )

    sorted_deployments = sorted(
        data,
        key=lambda deployment: str(
            deployment.get("deployed_at", "")
        ),
        reverse=True,
    )

    return sorted_deployments[:limit]