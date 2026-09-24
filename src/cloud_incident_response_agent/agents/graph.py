from typing import Any, Literal

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
)
from langgraph.checkpoint.memory import (
    InMemorySaver,
)
from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from cloud_incident_response_agent.agents.nodes import (
    cancel_remediation,
    collect_evidence,
    diagnose_incident,
    execute_remediation,
    prepare_remediation,
    request_approval,
    validate_diagnosis,
)
from cloud_incident_response_agent.agents.state import (
    IncidentState,
)


MAXIMUM_DIAGNOSIS_ATTEMPTS = 2


def route_after_validation(
    state: IncidentState,
) -> Literal[
    "retry_diagnosis",
    "prepare_remediation",
    "finish",
]:
    if state["diagnosis_valid"]:
        return "prepare_remediation"

    if (
        state["diagnosis_attempts"]
        < MAXIMUM_DIAGNOSIS_ATTEMPTS
    ):
        return "retry_diagnosis"

    return "finish"


def build_incident_graph(
    checkpointer: BaseCheckpointSaver[Any],
):
    """
    Build the incident-response workflow using
    the supplied checkpoint storage.

    FastAPI will provide AsyncSqliteSaver.

    The command-line script uses InMemorySaver.
    """

    builder = StateGraph(IncidentState)

    builder.add_node(
        "collect_evidence",
        collect_evidence,
    )

    builder.add_node(
        "diagnose_incident",
        diagnose_incident,
    )

    builder.add_node(
        "validate_diagnosis",
        validate_diagnosis,
    )

    builder.add_node(
        "prepare_remediation",
        prepare_remediation,
    )

    builder.add_node(
        "request_approval",
        request_approval,
    )

    builder.add_node(
        "execute_remediation",
        execute_remediation,
    )

    builder.add_node(
        "cancel_remediation",
        cancel_remediation,
    )

    builder.add_edge(
        START,
        "collect_evidence",
    )

    builder.add_edge(
        "collect_evidence",
        "diagnose_incident",
    )

    builder.add_edge(
        "diagnose_incident",
        "validate_diagnosis",
    )

    builder.add_conditional_edges(
        "validate_diagnosis",
        route_after_validation,
        {
            "retry_diagnosis": (
                "diagnose_incident"
            ),
            "prepare_remediation": (
                "prepare_remediation"
            ),
            "finish": END,
        },
    )

    builder.add_edge(
        "prepare_remediation",
        "request_approval",
    )

    builder.add_edge(
        "execute_remediation",
        END,
    )

    builder.add_edge(
        "cancel_remediation",
        END,
    )

    return builder.compile(
        checkpointer=checkpointer
    )


# This graph keeps the existing terminal script
# working without any changes.
incident_graph = build_incident_graph(
    checkpointer=InMemorySaver()
)