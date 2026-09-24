from typing import Any, Literal

from pydantic import BaseModel, Field


IncidentStatus = Literal[
    "running",
    "waiting_for_approval",
    "completed",
    "failed",
]


class IncidentCreate(BaseModel):
    """Request used to start an investigation."""

    incident_description: str = Field(
        min_length=10,
        max_length=2000,
    )

    service_name: str = Field(
        min_length=1,
        max_length=100,
    )


class IncidentReview(BaseModel):
    """Human approval or rejection details."""

    reviewer: str = Field(
        min_length=1,
        max_length=100,
    )

    comment: str = Field(
        default="",
        max_length=1000,
    )


class IncidentResponse(BaseModel):
    """Current incident workflow state."""

    thread_id: str
    status: IncidentStatus
    state: dict[str, Any]

    approval_request: (
        dict[str, Any] | None
    ) = None


class IncidentHistoryItem(BaseModel):
    """One saved LangGraph checkpoint."""

    checkpoint_id: str | None = None
    created_at: str | None = None
    step: int | None = None
    source: str | None = None

    completed_nodes: list[str] = Field(
        default_factory=list
    )

    next_nodes: list[str] = Field(
        default_factory=list
    )

    state: dict[str, Any] = Field(
        default_factory=dict
    )


class IncidentHistoryResponse(BaseModel):
    """Checkpoint history for one incident."""

    thread_id: str
    checkpoint_count: int

    checkpoints: list[
        IncidentHistoryItem
    ]