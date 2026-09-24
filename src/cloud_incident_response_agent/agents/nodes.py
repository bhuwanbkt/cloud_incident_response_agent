import json
import traceback
from typing import Any, Literal

from langchain_ollama import ChatOllama
from langgraph.types import (
    Command,
    interrupt,
)
from mcp import Client

from cloud_incident_response_agent.agents.state import (
    IncidentState,
)
from cloud_incident_response_agent.config import (
    get_settings,
)
from cloud_incident_response_agent.schemas.diagnosis import (
    IncidentDiagnosis,
)
from cloud_incident_response_agent.schemas.remediation import (
    RemediationProposal,
)


settings = get_settings()


def unwrap_tool_result(
    structured_content: Any,
) -> Any:
    """
    Extract the original Python result from an MCP
    structured response.
    """
    if (
        isinstance(structured_content, dict)
        and "result" in structured_content
    ):
        return structured_content["result"]

    return structured_content


async def collect_evidence(
    state: IncidentState,
) -> dict[str, Any]:
    """
    Collect metrics, logs, deployments, and runbook
    evidence using MCP tools.
    """
    service_name = state["service_name"]

    incident_description = state[
        "incident_description"
    ]

    try:
        async with Client(
            settings.mcp_server_url
        ) as client:
            metrics_result = await client.call_tool(
                "get_service_metrics",
                {
                    "service_name": service_name,
                },
            )

            logs_result = await client.call_tool(
                "search_application_logs",
                {
                    "service_name": service_name,
                    "level": "ERROR",
                    "limit": 20,
                },
            )

            deployments_result = (
                await client.call_tool(
                    "get_recent_deployments",
                    {
                        "service_name": service_name,
                        "limit": 5,
                    },
                )
            )

            runbook_result = await client.call_tool(
                "search_runbooks",
                {
                    "query": incident_description,
                    "top_k": 5,
                },
            )

        return {
            "metrics": unwrap_tool_result(
                metrics_result.structured_content
            ),
            "logs": unwrap_tool_result(
                logs_result.structured_content
            ),
            "deployments": unwrap_tool_result(
                deployments_result
                .structured_content
            ),
            "runbook_results": unwrap_tool_result(
                runbook_result.structured_content
            ),
        }

    except Exception as error:
        error_details = "".join(
            traceback.format_exception(error)
        )

        return {
            "metrics": {},
            "logs": [],
            "deployments": [],
            "runbook_results": [],
            "errors": [
                *state.get("errors", []),
                error_details,
            ],
        }


async def diagnose_incident(
    state: IncidentState,
) -> dict[str, Any]:
    """
    Generate a structured diagnosis with LangChain
    and Ollama.
    """
    attempt_number = (
        state.get("diagnosis_attempts", 0) + 1
    )

    if state.get("errors"):
        return {
            "diagnosis": None,
            "diagnosis_attempts": attempt_number,
        }

    evidence = {
        "incident_description": state[
            "incident_description"
        ],
        "service_name": state["service_name"],
        "metrics": state["metrics"],
        "error_logs": state["logs"],
        "recent_deployments": state[
            "deployments"
        ],
        "runbook_results": state[
            "runbook_results"
        ],
    }

    previous_feedback = state.get(
        "validation_errors",
        [],
    )

    model = ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0,
    )

    structured_model = (
        model.with_structured_output(
            IncidentDiagnosis
        )
    )

    prompt = f"""
You are a site reliability incident investigator.

Analyze only the supplied evidence. Do not invent facts.

Create a structured incident diagnosis.

Requirements:

1. Identify the most likely incident cause.
2. Include at least one specific metric fact.
3. Include at least one specific log fact.
4. Include at least one specific deployment fact.
5. Include relevant runbook guidance when available.
6. Every evidence fact must be understandable to a
   human and must include its relevant value.
7. Do not use a general statement such as "updated
   dependencies" unless it directly supports the cause.
8. If error rate is at least 10 percent or P95 latency
   is at least 3000 milliseconds, severity must be high
   or critical.
9. recommended_action must describe an actual action,
   such as rolling back a version or restoring a
   configuration. It cannot be an approval status.
10. For rollback, identify the current version and the
    target version when both are available.
11. Mark requires_human_approval as true for rollback,
    restart, scaling, or configuration changes.
12. Use a confidence from 0 to 1.
13. Every evidence item must contain source_type and
    a specific fact.

Previous validation feedback:

{json.dumps(previous_feedback, indent=2)}

Operational evidence:

{json.dumps(evidence, indent=2)}
"""

    try:
        diagnosis = await structured_model.ainvoke(
            prompt
        )

        diagnosis_payload = diagnosis.model_dump(
            mode="json"
        )

        supporting_evidence = diagnosis_payload.get(
            "supporting_evidence",
            [],
        )

        existing_source_types = {
            str(
                evidence.get(
                    "source_type",
                    "",
                )
            ).casefold()
            for evidence in supporting_evidence
            if isinstance(evidence, dict)
        }

        runbook_results = state.get(
            "runbook_results",
            [],
        )

        relevant_runbooks: list[
            tuple[float, dict[str, Any]]
        ] = []

        for runbook_result in runbook_results:
            if not isinstance(
                runbook_result,
                dict,
            ):
                continue

            try:
                reranker_score = float(
                    runbook_result.get(
                        "reranker_score",
                        float("-inf"),
                    )
                )
            except (TypeError, ValueError):
                continue

            if reranker_score >= 0:
                relevant_runbooks.append(
                    (
                        reranker_score,
                        runbook_result,
                    )
                )

        if (
            relevant_runbooks
            and "runbook"
            not in existing_source_types
        ):
            relevant_runbooks.sort(
                key=lambda item: item[0],
                reverse=True,
            )

            best_runbook = (
                relevant_runbooks[0][1]
            )

            runbook_name = str(
                best_runbook.get(
                    "runbook_name",
                    "Relevant runbook",
                )
            )

            heading = str(
                best_runbook.get(
                    "heading",
                    "",
                )
            ).strip()

            content = str(
                best_runbook.get(
                    "content",
                    "",
                )
            ).strip()

            runbook_fact_parts = [
                runbook_name,
            ]

            if heading:
                runbook_fact_parts.append(
                    heading
                )

            if content:
                runbook_fact_parts.append(
                    content
                )

            supporting_evidence.append(
                {
                    "source_type": "runbook",
                    "fact": ": ".join(
                        runbook_fact_parts
                    ),
                }
            )

        diagnosis_payload[
            "supporting_evidence"
        ] = supporting_evidence

        return {
            "diagnosis": diagnosis_payload,
            "diagnosis_attempts": attempt_number,
        }

    except Exception as error:
        return {
            "diagnosis": None,
            "diagnosis_attempts": attempt_number,
            "errors": [
                *state.get("errors", []),
                f"Diagnosis failed: {error}",
            ],
        }


def validate_diagnosis(
    state: IncidentState,
) -> dict[str, Any]:
    """
    Apply deterministic validation rules to the
    model-generated diagnosis.
    """
    diagnosis_data = state.get("diagnosis")

    validation_errors: list[str] = []

    if diagnosis_data is None:
        return {
            "diagnosis_valid": False,
            "validation_errors": [
                "The diagnosis was not generated."
            ],
        }

    try:
        diagnosis = (
            IncidentDiagnosis.model_validate(
                diagnosis_data
            )
        )
    except Exception as error:
        return {
            "diagnosis_valid": False,
            "validation_errors": [
                f"The diagnosis is invalid: {error}"
            ],
        }

    if (
        diagnosis.service_name
        != state["service_name"]
    ):
        validation_errors.append(
            "The diagnosis service name does not "
            "match the requested service."
        )

    source_types = {
        evidence.source_type
        for evidence
        in diagnosis.supporting_evidence
    }

    required_sources = {
        "metric",
        "log",
        "deployment",
    }

    missing_sources = (
        required_sources - source_types
    )

    if missing_sources:
        validation_errors.append(
            "Supporting evidence is missing these "
            f"source types: "
            f"{', '.join(sorted(missing_sources))}."
        )

    runbook_results = state.get(
        "runbook_results",
        [],
    )

    relevant_runbook_available = False

    for runbook_result in runbook_results:
        if not isinstance(runbook_result, dict):
            continue

        try:
            reranker_score = float(
                runbook_result.get(
                    "reranker_score",
                    float("-inf"),
                )
            )
        except (TypeError, ValueError):
            continue

        if reranker_score >= 0:
            relevant_runbook_available = True
            break

    if (
        relevant_runbook_available
        and "runbook" not in source_types
    ):
        validation_errors.append(
            "A relevant runbook was retrieved, "
            "but the diagnosis did not include "
            "runbook evidence."
        )

    if len(
        diagnosis.supporting_evidence
    ) < 3:
        validation_errors.append(
            "At least three evidence items are "
            "required."
        )

    metrics = state.get(
        "metrics",
        {},
    )

    error_rate = float(
        metrics.get(
            "error_rate_percent",
            0,
        )
    )

    p95_latency = float(
        metrics.get(
            "p95_latency_ms",
            0,
        )
    )

    severe_metric_condition = (
        error_rate >= 10
        or p95_latency >= 3000
    )

    if (
        severe_metric_condition
        and diagnosis.severity
        not in {"high", "critical"}
    ):
        validation_errors.append(
            "Severity must be high or critical "
            f"because the error rate is "
            f"{error_rate} percent and P95 latency "
            f"is {p95_latency} milliseconds."
        )

    normalized_action = (
        diagnosis.recommended_action
        .strip()
        .casefold()
    )

    invalid_action_values = {
        "requires_human_approval",
        "human approval",
        "approval required",
        "requires approval",
        "true",
        "false",
    }

    if normalized_action in invalid_action_values:
        validation_errors.append(
            "recommended_action must describe an "
            "actual remediation action, not an "
            "approval status."
        )

    remediation_verbs = {
        "rollback",
        "roll back",
        "restore",
        "restart",
        "scale",
        "increase",
        "decrease",
        "revert",
        "change",
        "disable",
        "enable",
    }

    has_remediation_action = any(
        verb in normalized_action
        for verb in remediation_verbs
    )

    if not has_remediation_action:
        validation_errors.append(
            "recommended_action must contain a clear "
            "remediation action such as rollback, "
            "restore, restart, or scale."
        )

    changes_production = any(
        word in normalized_action
        for word in remediation_verbs
    )

    if (
        changes_production
        and not diagnosis.requires_human_approval
    ):
        validation_errors.append(
            "The proposed production action requires "
            "human approval."
        )

    normalized_cause = (
        diagnosis.suspected_cause.casefold()
    )

    pool_exhaustion_diagnosis = (
        "connection pool" in normalized_cause
        or "pool exhaustion" in normalized_cause
    )

    deployment_evidence = [
        evidence.fact.casefold()
        for evidence
        in diagnosis.supporting_evidence
        if evidence.source_type == "deployment"
    ]

    if pool_exhaustion_diagnosis:
        mentions_pool_reduction = any(
            (
                "pool" in fact
                and (
                    "10" in fact
                    or "reduced" in fact
                )
            )
            for fact in deployment_evidence
        )

        if not mentions_pool_reduction:
            validation_errors.append(
                "The deployment evidence must "
                "mention that the database pool "
                "size was reduced to 10."
            )

    return {
        "diagnosis_valid": not validation_errors,
        "validation_errors": validation_errors,
    }


def prepare_remediation(
    state: IncidentState,
) -> dict[str, Any]:
    """
    Build a deterministic rollback proposal from the
    validated diagnosis and deployment history.
    """
    diagnosis_data = state.get("diagnosis")

    if (
        diagnosis_data is None
        or not state.get("diagnosis_valid")
    ):
        return {
            "proposed_action": None,
            "approval_status": "not_required",
        }

    diagnosis = IncidentDiagnosis.model_validate(
        diagnosis_data
    )

    deployments = state.get(
        "deployments",
        [],
    )

    if len(deployments) < 2:
        return {
            "proposed_action": None,
            "approval_status": "not_required",
            "errors": [
                *state.get("errors", []),
                "A rollback requires at least two "
                "deployment versions.",
            ],
        }

    active_deployment = next(
        (
            deployment
            for deployment in deployments
            if deployment.get("status") == "active"
        ),
        deployments[0],
    )

    target_deployment = next(
        (
            deployment
            for deployment in deployments
            if deployment.get("version")
            != active_deployment.get("version")
        ),
        None,
    )

    if target_deployment is None:
        return {
            "proposed_action": None,
            "approval_status": "not_required",
            "errors": [
                *state.get("errors", []),
                "No rollback target was found.",
            ],
        }

    proposal = RemediationProposal(
        action="rollback_deployment",
        service_name=state["service_name"],
        current_version=str(
            active_deployment["version"]
        ),
        target_version=str(
            target_deployment["version"]
        ),
        reason=diagnosis.suspected_cause,
        risk_level="high",
        requires_human_approval=True,
    )

    return {
        "proposed_action": proposal.model_dump(
            mode="json"
        ),
        "approval_status": "pending",
    }


def request_approval(
    state: IncidentState,
) -> Command[
    Literal[
        "execute_remediation",
        "cancel_remediation",
    ]
]:
    """
    Pause the graph and wait for a human decision.
    """
    proposal_data = state.get(
        "proposed_action"
    )

    if proposal_data is None:
        return Command(
            goto="cancel_remediation",
            update={
                "approval_status": "not_required",
            },
        )

    proposal = RemediationProposal.model_validate(
        proposal_data
    )

    decision = interrupt(
        {
            "question": (
                "Do you approve this simulated "
                "production remediation?"
            ),
            "proposed_action": proposal.model_dump(
                mode="json"
            ),
            "diagnosis": state.get("diagnosis"),
        }
    )

    if isinstance(decision, bool):
        approved = decision
        reviewer = "local-reviewer"
        comment = None

    elif isinstance(decision, dict):
        approved = bool(
            decision.get(
                "approved",
                False,
            )
        )

        reviewer = str(
            decision.get(
                "reviewer",
                "local-reviewer",
            )
        )

        comment_value = decision.get(
            "comment"
        )

        comment = (
            str(comment_value)
            if comment_value is not None
            else None
        )

    else:
        approved = False
        reviewer = "unknown"
        comment = "Invalid approval response."

    if approved:
        return Command(
            goto="execute_remediation",
            update={
                "approval_status": "approved",
                "reviewer": reviewer,
                "approval_comment": comment,
            },
        )

    return Command(
        goto="cancel_remediation",
        update={
            "approval_status": "rejected",
            "reviewer": reviewer,
            "approval_comment": comment,
        },
    )


async def execute_remediation(
    state: IncidentState,
) -> dict[str, Any]:
    """
    Call the simulated rollback MCP tool after approval.
    """
    proposal_data = state.get(
        "proposed_action"
    )

    if proposal_data is None:
        return {
            "execution_result": None,
            "errors": [
                *state.get("errors", []),
                "No remediation proposal exists.",
            ],
        }

    proposal = RemediationProposal.model_validate(
        proposal_data
    )

    if state.get("approval_status") != "approved":
        return {
            "execution_result": None,
            "errors": [
                *state.get("errors", []),
                "Remediation cannot execute without "
                "human approval.",
            ],
        }

    try:
        async with Client(
            settings.mcp_server_url
        ) as client:
            result = await client.call_tool(
                "simulate_rollback",
                {
                    "service_name": (
                        proposal.service_name
                    ),
                    "current_version": (
                        proposal.current_version
                    ),
                    "target_version": (
                        proposal.target_version
                    ),
                },
            )

        return {
            "execution_result": unwrap_tool_result(
                result.structured_content
            ),
        }

    except Exception as error:
        return {
            "execution_result": None,
            "errors": [
                *state.get("errors", []),
                "Remediation execution failed: "
                f"{error}",
            ],
        }


def cancel_remediation(
    state: IncidentState,
) -> dict[str, Any]:
    """
    Finish without executing the rollback.
    """
    status = state.get("approval_status")

    message = (
        "Remediation was rejected by the reviewer."
        if status == "rejected"
        else "No remediation was executed."
    )

    return {
        "execution_result": {
            "status": "not_executed",
            "changes_applied": False,
            "message": message,
        },
    }
