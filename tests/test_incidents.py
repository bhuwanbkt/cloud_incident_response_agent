from collections.abc import (
    AsyncIterator,
    Iterator,
)
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.types import Command

from cloud_incident_response_agent.api.incidents import (
    router as incidents_router,
)


APPROVAL_REQUEST = {
    "question": (
        "Do you approve this simulated "
        "production remediation?"
    ),
    "proposed_action": {
        "action": "rollback_deployment",
        "service_name": "payment-api",
        "current_version": "2.4.1",
        "target_version": "2.4.0",
        "reason": (
            "Database connection pool exhaustion"
        ),
        "risk_level": "high",
        "requires_human_approval": True,
    },
}


class FakeIncidentGraph:
    """
    Lightweight replacement for LangGraph.

    It lets us test the FastAPI endpoints without
    calling MCP, Ollama or the cross-encoder.
    """

    def __init__(self) -> None:
        self.states: dict[
            str,
            dict[str, Any],
        ] = {}

        self.pending_approvals: set[str] = set()

    @staticmethod
    def get_thread_id(
        config: dict[str, Any],
    ) -> str:
        return config[
            "configurable"
        ]["thread_id"]

    async def ainvoke(
        self,
        graph_input: Any,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        thread_id = self.get_thread_id(
            config
        )

        if isinstance(graph_input, Command):
            return self.resume_workflow(
                thread_id=thread_id,
                command=graph_input,
            )

        return self.start_workflow(
            thread_id=thread_id,
            initial_state=graph_input,
        )

    def start_workflow(
        self,
        thread_id: str,
        initial_state: dict[str, Any],
    ) -> dict[str, Any]:
        incident_state = {
            **initial_state,
            "metrics": {
                "p95_latency_ms": 4200,
                "error_rate_percent": 18.2,
            },
            "logs": [
                {
                    "level": "ERROR",
                    "message": (
                        "Database connection "
                        "pool exhausted"
                    ),
                }
            ],
            "deployments": [
                {
                    "version": "2.4.1",
                    "changes": [
                        (
                            "Reduced database "
                            "pool size"
                        )
                    ],
                }
            ],
            "diagnosis": {
                "service_name": (
                    initial_state[
                        "service_name"
                    ]
                ),
                "severity": "high",
                "suspected_cause": (
                    "Database connection "
                    "pool exhaustion"
                ),
                "recommended_action": (
                    "Roll back deployment "
                    "2.4.1 to 2.4.0"
                ),
                "requires_human_approval": True,
                "confidence": 0.8,
            },
            "diagnosis_attempts": 1,
            "diagnosis_valid": True,
            "proposed_action": (
                APPROVAL_REQUEST[
                    "proposed_action"
                ]
            ),
            "approval_status": "pending",
            "errors": [],
        }

        self.states[thread_id] = (
            incident_state
        )
        self.pending_approvals.add(
            thread_id
        )

        return {
            **incident_state,
            "__interrupt__": (
                SimpleNamespace(
                    value=APPROVAL_REQUEST
                ),
            ),
        }

    def resume_workflow(
        self,
        thread_id: str,
        command: Command,
    ) -> dict[str, Any]:
        incident_state = self.states[
            thread_id
        ]

        decision = command.resume

        if not isinstance(decision, dict):
            raise ValueError(
                "Approval decision must "
                "be a dictionary."
            )

        approved = bool(
            decision.get("approved")
        )

        incident_state.update(
            {
                "approval_status": (
                    "approved"
                    if approved
                    else "rejected"
                ),
                "reviewer": (
                    decision.get("reviewer")
                ),
                "approval_comment": (
                    decision.get("comment")
                ),
                "execution_result": (
                    {
                        "status": (
                            "simulated_success"
                        ),
                        "changes_applied": False,
                        "message": (
                            "Simulated rollback "
                            "completed."
                        ),
                    }
                    if approved
                    else {
                        "status": (
                            "not_executed"
                        ),
                        "changes_applied": False,
                        "message": (
                            "Remediation was "
                            "rejected."
                        ),
                    }
                ),
            }
        )

        self.pending_approvals.discard(
            thread_id
        )

        return dict(incident_state)

    async def aget_state(
        self,
        config: dict[str, Any],
    ) -> SimpleNamespace:
        thread_id = self.get_thread_id(
            config
        )

        incident_state = self.states.get(
            thread_id
        )

        if incident_state is None:
            return SimpleNamespace(
                values={},
                tasks=(),
            )

        if (
            thread_id
            in self.pending_approvals
        ):
            tasks = (
                SimpleNamespace(
                    interrupts=(
                        SimpleNamespace(
                            value=(
                                APPROVAL_REQUEST
                            )
                        ),
                    )
                ),
            )
        else:
            tasks = ()

        return SimpleNamespace(
            values=dict(incident_state),
            tasks=tasks,
        )

    async def aget_state_history(
        self,
        config: dict[str, Any],
    ) -> AsyncIterator[SimpleNamespace]:
        thread_id = self.get_thread_id(
            config
        )

        incident_state = self.states.get(
            thread_id
        )

        if incident_state is None:
            return

        # LangGraph returns newest first.
        yield SimpleNamespace(
            values=dict(incident_state),
            next=("request_approval",),
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": (
                        "checkpoint-2"
                    ),
                }
            },
            metadata={
                "source": "loop",
                "step": 1,
                "writes": {
                    "validate_diagnosis": {
                        "diagnosis_valid": True
                    }
                },
            },
            created_at=(
                "2026-09-23T12:01:00Z"
            ),
        )

        yield SimpleNamespace(
            values={
                "service_name": (
                    incident_state[
                        "service_name"
                    ]
                )
            },
            next=("collect_evidence",),
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": (
                        "checkpoint-1"
                    ),
                }
            },
            metadata={
                "source": "input",
                "step": -1,
                "writes": None,
            },
            created_at=(
                "2026-09-23T12:00:00Z"
            ),
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
    test_app = FastAPI()
    test_app.include_router(
        incidents_router
    )

    test_app.state.incident_graph = (
        FakeIncidentGraph()
    )

    with TestClient(test_app) as test_client:
        yield test_client


def start_incident(
    client: TestClient,
) -> dict[str, Any]:
    response = client.post(
        "/incidents",
        json={
            "incident_description": (
                "The payment API has high "
                "latency, database connection "
                "timeouts, and HTTP 500 errors."
            ),
            "service_name": "payment-api",
        },
    )

    assert response.status_code == 201

    return response.json()


def test_create_incident_waits_for_approval(
    client: TestClient,
) -> None:
    response_data = start_incident(client)

    assert response_data["thread_id"].startswith(
        "incident-"
    )
    assert (
        response_data["status"]
        == "waiting_for_approval"
    )
    assert (
        response_data["state"][
            "diagnosis_valid"
        ]
        is True
    )
    assert (
        response_data["approval_request"][
            "proposed_action"
        ]["action"]
        == "rollback_deployment"
    )


def test_get_incident(
    client: TestClient,
) -> None:
    created = start_incident(client)
    thread_id = created["thread_id"]

    response = client.get(
        f"/incidents/{thread_id}"
    )

    assert response.status_code == 200

    response_data = response.json()

    assert (
        response_data["thread_id"]
        == thread_id
    )
    assert (
        response_data["status"]
        == "waiting_for_approval"
    )


def test_approve_incident(
    client: TestClient,
) -> None:
    created = start_incident(client)
    thread_id = created["thread_id"]

    response = client.post(
        f"/incidents/{thread_id}/approve",
        json={
            "reviewer": "bhuwan",
            "comment": (
                "Approved for simulation"
            ),
        },
    )

    assert response.status_code == 200

    response_data = response.json()
    incident_state = response_data["state"]

    assert (
        response_data["status"]
        == "completed"
    )
    assert (
        incident_state["approval_status"]
        == "approved"
    )
    assert (
        incident_state["reviewer"]
        == "bhuwan"
    )
    assert (
        incident_state[
            "execution_result"
        ]["status"]
        == "simulated_success"
    )
    assert (
        incident_state[
            "execution_result"
        ]["changes_applied"]
        is False
    )


def test_reject_incident(
    client: TestClient,
) -> None:
    created = start_incident(client)
    thread_id = created["thread_id"]

    response = client.post(
        f"/incidents/{thread_id}/reject",
        json={
            "reviewer": "bhuwan",
            "comment": "Risk is too high",
        },
    )

    assert response.status_code == 200

    response_data = response.json()
    incident_state = response_data["state"]

    assert (
        response_data["status"]
        == "completed"
    )
    assert (
        incident_state["approval_status"]
        == "rejected"
    )
    assert (
        incident_state[
            "execution_result"
        ]["status"]
        == "not_executed"
    )


def test_unknown_incident_returns_404(
    client: TestClient,
) -> None:
    response = client.get(
        "/incidents/incident-does-not-exist"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Incident was not found."
    }


def test_completed_incident_cannot_be_approved_again(
    client: TestClient,
) -> None:
    created = start_incident(client)
    thread_id = created["thread_id"]

    first_response = client.post(
        f"/incidents/{thread_id}/approve",
        json={
            "reviewer": "bhuwan",
            "comment": "Approved",
        },
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/incidents/{thread_id}/approve",
        json={
            "reviewer": "bhuwan",
            "comment": "Approve again",
        },
    )

    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": (
            "This incident is not waiting "
            "for approval."
        )
    }


def test_short_incident_description_returns_422(
    client: TestClient,
) -> None:
    response = client.post(
        "/incidents",
        json={
            "incident_description": "short",
            "service_name": "payment-api",
        },
    )

    assert response.status_code == 422

def test_get_incident_history(
    client: TestClient,
) -> None:
    created = start_incident(client)
    thread_id = created["thread_id"]

    response = client.get(
        f"/incidents/{thread_id}/history"
    )

    assert response.status_code == 200

    response_data = response.json()

    assert (
        response_data["thread_id"]
        == thread_id
    )
    assert (
        response_data["checkpoint_count"]
        == 2
    )

    checkpoints = response_data[
        "checkpoints"
    ]

    # The API reverses LangGraph's newest-first
    # output into oldest-first order.
    assert checkpoints[0]["step"] == -1
    assert (
        checkpoints[0]["checkpoint_id"]
        == "checkpoint-1"
    )
    assert checkpoints[0]["next_nodes"] == [
        "collect_evidence"
    ]

    assert checkpoints[1]["step"] == 1
    assert (
        checkpoints[1]["completed_nodes"]
        == ["validate_diagnosis"]
    )
    assert checkpoints[1]["next_nodes"] == [
        "request_approval"
    ]


def test_unknown_incident_history_returns_404(
    client: TestClient,
) -> None:
    response = client.get(
        "/incidents/"
        "incident-does-not-exist/history"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Incident was not found."
    }