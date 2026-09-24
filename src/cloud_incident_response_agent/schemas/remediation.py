from typing import Literal

from pydantic import BaseModel, Field


class RemediationProposal(BaseModel):
    action: Literal["rollback_deployment"]

    service_name: str

    current_version: str

    target_version: str

    reason: str = Field(
        min_length=5
    )

    risk_level: Literal[
        "low",
        "medium",
        "high",
    ]

    requires_human_approval: bool = True


class ApprovalDecision(BaseModel):
    approved: bool
    reviewer: str
    comment: str | None = None