import logging
from typing import Any
from uuid import uuid4

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    status,
)
from langgraph.types import Command

from cloud_incident_response_agent.schemas.incident import (
    IncidentCreate,
    IncidentHistoryItem,
    IncidentHistoryResponse,
    IncidentResponse,
    IncidentReview,
    IncidentStatus,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/incidents",
    tags=["incidents"],
)


def get_incident_graph(
    request: Request,
) -> Any:
    """
    Return the SQLite-backed graph created
    during FastAPI startup.
    """

    graph = getattr(
        request.app.state,
        "incident_graph",
        None,
    )

    if graph is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "The incident workflow is "
                "not available."
            ),
        )

    return graph


def create_graph_config(
    thread_id: str,
) -> dict[str, Any]:
    return {
        "configurable": {
            "thread_id": thread_id,
        }
    }


def create_initial_state(
    incident: IncidentCreate,
) -> dict[str, Any]:
    return {
        "incident_description": (
            incident.incident_description
        ),
        "service_name": (
            incident.service_name
        ),
        "metrics": {},
        "logs": [],
        "deployments": [],
        "runbook_results": [],
        "diagnosis": None,
        "diagnosis_attempts": 0,
        "diagnosis_valid": False,
        "validation_errors": [],
        "proposed_action": None,
        "approval_status": "pending",
        "reviewer": None,
        "approval_comment": None,
        "execution_result": None,
        "errors": [],
    }


def extract_approval_request(
    result: dict[str, Any],
) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__")

    if not interrupts:
        return None

    first_interrupt = interrupts[0]

    interrupt_value = getattr(
        first_interrupt,
        "value",
        None,
    )

    if isinstance(interrupt_value, dict):
        return interrupt_value

    if interrupt_value is None:
        return None

    return {
        "message": str(interrupt_value),
    }


def remove_internal_fields(
    result: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if not key.startswith("__")
    }


def determine_status(
    incident_state: dict[str, Any],
    approval_request: dict[str, Any] | None,
) -> IncidentStatus:
    if approval_request is not None:
        return "waiting_for_approval"

    if incident_state.get("errors"):
        return "failed"

    approval_status = incident_state.get(
        "approval_status"
    )

    if approval_status in {
        "approved",
        "rejected",
    }:
        return "completed"

    if incident_state.get(
        "execution_result"
    ):
        return "completed"

    return "running"


def get_snapshot_approval_request(
    snapshot: Any,
) -> dict[str, Any] | None:
    """
    Read a pending human interrupt from a
    saved LangGraph state snapshot.
    """

    for task in snapshot.tasks:
        interrupts = getattr(
            task,
            "interrupts",
            (),
        )

        for interrupt_item in interrupts:
            value = getattr(
                interrupt_item,
                "value",
                None,
            )

            if isinstance(value, dict):
                return value

            if value is not None:
                return {
                    "message": str(value),
                }

    return None


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident(
    incident: IncidentCreate,
    request: Request,
) -> IncidentResponse:
    graph = get_incident_graph(request)

    thread_id = f"incident-{uuid4()}"
    config = create_graph_config(thread_id)

    logger.info(
        "Incident investigation started",
        extra={
            "thread_id": thread_id,
            "service_name": (
                incident.service_name
            ),
            "operation": (
                "create_incident"
            ),
        },
    )

    try:
        result = await graph.ainvoke(
            create_initial_state(incident),
            config=config,
        )
    except Exception as exception:
        logger.exception(
            "Incident investigation failed",
            extra={
                "thread_id": thread_id,
                "service_name": (
                    incident.service_name
                ),
                "operation": (
                    "create_incident"
                ),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Incident investigation failed: "
                f"{exception}"
            ),
        ) from exception

    approval_request = (
        extract_approval_request(result)
    )

    clean_state = remove_internal_fields(
        result
    )

    incident_status = determine_status(
        clean_state,
        approval_request,
    )

    logger.info(
        "Incident investigation checkpoint reached",
        extra={
            "thread_id": thread_id,
            "service_name": (
                incident.service_name
            ),
            "operation": (
                "request_approval"
                if incident_status
                == "waiting_for_approval"
                else "investigation_finished"
            ),
        },
    )

    return IncidentResponse(
        thread_id=thread_id,
        status=incident_status,
        state=clean_state,
        approval_request=approval_request,
    )


@router.get(
    "/{thread_id}",
    response_model=IncidentResponse,
)
async def get_incident(
    thread_id: str,
    request: Request,
) -> IncidentResponse:
    graph = get_incident_graph(request)
    config = create_graph_config(thread_id)

    snapshot = await graph.aget_state(
        config
    )

    if not snapshot.values:
        raise HTTPException(
            status_code=404,
            detail="Incident was not found.",
        )

    incident_state = dict(
        snapshot.values
    )

    approval_request = (
        get_snapshot_approval_request(
            snapshot
        )
    )

    return IncidentResponse(
        thread_id=thread_id,
        status=determine_status(
            incident_state,
            approval_request,
        ),
        state=incident_state,
        approval_request=approval_request,
    )


@router.get(
    "/{thread_id}/history",
    response_model=IncidentHistoryResponse,
)
async def get_incident_history(
    thread_id: str,
    request: Request,
) -> IncidentHistoryResponse:
    graph = get_incident_graph(request)
    config = create_graph_config(thread_id)

    current_snapshot = (
        await graph.aget_state(config)
    )

    if not current_snapshot.values:
        raise HTTPException(
            status_code=404,
            detail="Incident was not found.",
        )

    checkpoints: list[
        IncidentHistoryItem
    ] = []

    async for snapshot in (
        graph.aget_state_history(config)
    ):
        metadata = dict(
            snapshot.metadata or {}
        )

        writes = metadata.get("writes")

        if isinstance(writes, dict):
            completed_nodes = list(
                writes.keys()
            )
        else:
            completed_nodes = []

        configurable = snapshot.config.get(
            "configurable",
            {},
        )

        checkpoint_id = configurable.get(
            "checkpoint_id"
        )

        checkpoints.append(
            IncidentHistoryItem(
                checkpoint_id=checkpoint_id,
                created_at=(
                    snapshot.created_at
                ),
                step=metadata.get("step"),
                source=metadata.get(
                    "source"
                ),
                completed_nodes=(
                    completed_nodes
                ),
                next_nodes=list(
                    snapshot.next
                ),
                state=dict(
                    snapshot.values
                ),
            )
        )

    # LangGraph returns the newest checkpoint
    # first. The API returns oldest first.
    checkpoints.reverse()

    logger.info(
        "Incident history retrieved",
        extra={
            "thread_id": thread_id,
            "service_name": (
                current_snapshot.values.get(
                    "service_name"
                )
            ),
            "operation": (
                "get_incident_history"
            ),
        },
    )

    return IncidentHistoryResponse(
        thread_id=thread_id,
        checkpoint_count=len(
            checkpoints
        ),
        checkpoints=checkpoints,
    )


async def resume_incident(
    thread_id: str,
    review: IncidentReview,
    approved: bool,
    request: Request,
) -> IncidentResponse:
    graph = get_incident_graph(request)
    config = create_graph_config(thread_id)

    snapshot = await graph.aget_state(
        config
    )

    if not snapshot.values:
        raise HTTPException(
            status_code=404,
            detail="Incident was not found.",
        )

    approval_request = (
        get_snapshot_approval_request(
            snapshot
        )
    )

    if approval_request is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "This incident is not waiting "
                "for approval."
            ),
        )

    decision = {
        "approved": approved,
        "reviewer": review.reviewer,
        "comment": review.comment,
    }

    logger.info(
        "Human review received",
        extra={
            "thread_id": thread_id,
            "service_name": (
                snapshot.values.get(
                    "service_name"
                )
            ),
            "operation": (
                "approve_incident"
                if approved
                else "reject_incident"
            ),
        },
    )

    try:
        result = await graph.ainvoke(
            Command(resume=decision),
            config=config,
        )
    except Exception as exception:
        logger.exception(
            "Could not resume incident workflow",
            extra={
                "thread_id": thread_id,
                "service_name": (
                    snapshot.values.get(
                        "service_name"
                    )
                ),
                "operation": (
                    "resume_incident"
                ),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not resume incident: "
                f"{exception}"
            ),
        ) from exception

    next_approval_request = (
        extract_approval_request(result)
    )

    clean_state = remove_internal_fields(
        result
    )

    incident_status = determine_status(
        clean_state,
        next_approval_request,
    )

    logger.info(
        "Incident workflow completed",
        extra={
            "thread_id": thread_id,
            "service_name": (
                clean_state.get(
                    "service_name"
                )
            ),
            "operation": (
                "remediation_approved"
                if approved
                else "remediation_rejected"
            ),
        },
    )

    return IncidentResponse(
        thread_id=thread_id,
        status=incident_status,
        state=clean_state,
        approval_request=(
            next_approval_request
        ),
    )


@router.post(
    "/{thread_id}/approve",
    response_model=IncidentResponse,
)
async def approve_incident(
    thread_id: str,
    review: IncidentReview,
    request: Request,
) -> IncidentResponse:
    return await resume_incident(
        thread_id=thread_id,
        review=review,
        approved=True,
        request=request,
    )


@router.post(
    "/{thread_id}/reject",
    response_model=IncidentResponse,
)
async def reject_incident(
    thread_id: str,
    review: IncidentReview,
    request: Request,
) -> IncidentResponse:
    return await resume_incident(
        thread_id=thread_id,
        review=review,
        approved=False,
        request=request,
    )