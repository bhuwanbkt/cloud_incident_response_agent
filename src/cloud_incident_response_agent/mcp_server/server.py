from typing import Any

from mcp.server import MCPServer

from cloud_incident_response_agent.retrieval.runbook_search import (
    search_runbooks as retrieve_runbooks,
)
from cloud_incident_response_agent.services.operational_data import (
    get_recent_deployments as load_recent_deployments,
)
from cloud_incident_response_agent.services.operational_data import (
    get_service_metrics as load_service_metrics,
)
from cloud_incident_response_agent.services.operational_data import (
    search_application_logs as load_application_logs,
)
from cloud_incident_response_agent.services.remediation import (
    simulate_rollback as run_simulated_rollback,
)

mcp = MCPServer(
    "Cloud Incident Operations"
)


@mcp.tool()
def get_service_metrics(
    service_name: str,
) -> dict[str, Any]:
    """
    Return the latest operational metrics for a service.

    Use this tool to inspect latency, error rate, CPU,
    memory, instance health, and request volume.
    """
    return load_service_metrics(service_name)


@mcp.tool()
def search_application_logs(
    service_name: str,
    search_text: str | None = None,
    level: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Search application logs for a service.

    Search by optional message text, log level, or both.
    """
    return load_application_logs(
        service_name=service_name,
        search_text=search_text,
        level=level,
        limit=limit,
    )


@mcp.tool()
def get_recent_deployments(
    service_name: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Return recent deployments for a service.

    Use this tool to identify configuration or code
    changes that happened before an incident.
    """
    return load_recent_deployments(
        service_name=service_name,
        limit=limit,
    )


@mcp.tool()
def search_runbooks(
    query: str,
    top_k: int = 5,
) -> list[dict[str, str | float]]:
    """
    Search operational runbooks for incident guidance.

    This tool performs semantic candidate retrieval and
    then applies cross-encoder reranking.
    """
    results = retrieve_runbooks(
        query=query,
        top_k=top_k,
    )

    return [
        result.to_dict()
        for result in results
    ]

@mcp.tool()
def simulate_rollback(
    service_name: str,
    current_version: str,
    target_version: str,
) -> dict[str, Any]:
    """
    Simulate rolling a service back to an earlier version.

    This tool does not modify a real service. It validates
    the versions and returns a simulated execution result.
    It must only be called after human approval.
    """
    return run_simulated_rollback(
        service_name=service_name,
        current_version=current_version,
        target_version=target_version,
    )