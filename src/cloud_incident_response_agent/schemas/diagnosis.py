from typing import Literal

from pydantic import BaseModel, Field


EvidenceSource = Literal[
    "metric",
    "log",
    "deployment",
    "runbook",
]


class EvidenceItem(BaseModel):
    source_type: EvidenceSource = Field(
        description=(
            "The type of evidence supporting the fact."
        )
    )

    fact: str = Field(
        min_length=5,
        description=(
            "A specific fact taken from the supplied "
            "operational evidence."
        ),
    )


class IncidentDiagnosis(BaseModel):
    service_name: str = Field(
        description="Name of the affected service."
    )

    severity: Literal[
        "low",
        "medium",
        "high",
        "critical",
    ]

    suspected_cause: str = Field(
        min_length=5,
        description=(
            "Most likely cause supported by evidence."
        ),
    )

    supporting_evidence: list[EvidenceItem] = Field(
        min_length=3,
        description=(
            "Specific facts supporting the diagnosis."
        ),
    )

    recommended_action: str = Field(
        min_length=5,
        description=(
            "Recommended remediation action."
        ),
    )

    requires_human_approval: bool = Field(
        description=(
            "True when the recommendation changes a "
            "production system."
        )
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Confidence in the diagnosis from 0 to 1."
        ),
    )