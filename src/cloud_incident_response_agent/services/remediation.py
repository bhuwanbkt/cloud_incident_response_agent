from typing import Any

from cloud_incident_response_agent.services.operational_data import (
    get_recent_deployments,
    validate_service_name,
)


class RemediationError(Exception):
    """Raised when remediation cannot be performed."""


def simulate_rollback(
    service_name: str,
    current_version: str,
    target_version: str,
) -> dict[str, Any]:
    normalized_service = validate_service_name(
        service_name
    )

    deployments = get_recent_deployments(
        service_name=normalized_service,
        limit=20,
    )

    available_versions = {
        str(deployment.get("version"))
        for deployment in deployments
    }

    if current_version not in available_versions:
        raise RemediationError(
            f"Current version {current_version} "
            "was not found."
        )

    if target_version not in available_versions:
        raise RemediationError(
            f"Target version {target_version} "
            "was not found."
        )

    if current_version == target_version:
        raise RemediationError(
            "Current and target versions must differ."
        )

    return {
        "service_name": normalized_service,
        "action": "rollback_deployment",
        "current_version": current_version,
        "target_version": target_version,
        "status": "simulated_success",
        "changes_applied": False,
        "message": (
            f"Simulated rollback of "
            f"{normalized_service} from "
            f"{current_version} to "
            f"{target_version}."
        ),
    }