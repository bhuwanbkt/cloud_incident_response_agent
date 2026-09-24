from typing import (
    Any,
    Literal,
    TypedDict,
)


ApprovalStatus = Literal[
    "not_required",
    "pending",
    "approved",
    "rejected",
]


class IncidentState(TypedDict):
    incident_description: str
    service_name: str

    metrics: dict[str, Any]
    logs: list[dict[str, Any]]
    deployments: list[dict[str, Any]]
    runbook_results: list[dict[str, Any]]

    # Store JSON-compatible dictionaries in checkpoints.
    diagnosis: dict[str, Any] | None
    diagnosis_attempts: int
    diagnosis_valid: bool
    validation_errors: list[str]

    proposed_action: dict[str, Any] | None
    approval_status: ApprovalStatus
    reviewer: str | None
    approval_comment: str | None

    execution_result: dict[str, Any] | None

    errors: list[str]