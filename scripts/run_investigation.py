import asyncio
import json
from typing import Any
from uuid import uuid4

from langgraph.types import Command

from cloud_incident_response_agent.agents.graph import (
    incident_graph,
)
from cloud_incident_response_agent.agents.state import (
    IncidentState,
)


def print_json(
    value: Any,
) -> None:
    print(
        json.dumps(
            value,
            indent=2,
        )
    )


async def main() -> None:
    thread_id = f"incident-{uuid4()}"

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    initial_state: IncidentState = {
        "incident_description": (
            "The payment API has high latency, "
            "database connection timeouts, and "
            "HTTP 500 errors."
        ),
        "service_name": "payment-api",
        "metrics": {},
        "logs": [],
        "deployments": [],
        "runbook_results": [],
        "diagnosis": None,
        "diagnosis_attempts": 0,
        "diagnosis_valid": False,
        "validation_errors": [],
        "proposed_action": None,
        "approval_status": "not_required",
        "reviewer": None,
        "approval_comment": None,
        "execution_result": None,
        "errors": [],
    }

    print(f"Thread ID: {thread_id}")
    print("Starting incident investigation...")

    result = await incident_graph.ainvoke(
        initial_state,
        config=config,
    )

    interrupts = result.get(
        "__interrupt__",
        (),
    )

    if not interrupts:
        print(
            "The graph completed without requesting "
            "approval."
        )

        print_json(result)
        return

    interrupt_payload = interrupts[0].value

    print("\nApproval required:")
    print_json(interrupt_payload)

    response = input(
        "\nApprove remediation? Type yes or no: "
    ).strip().casefold()

    approved = response in {
        "yes",
        "y",
        "approve",
        "approved",
    }

    reviewer = input(
        "Reviewer name: "
    ).strip()

    comment = input(
        "Optional comment: "
    ).strip()

    decision = {
        "approved": approved,
        "reviewer": (
            reviewer
            or "local-reviewer"
        ),
        "comment": comment or None,
    }

    final_result = await incident_graph.ainvoke(
        Command(
            resume=decision
        ),
        config=config,
    )

    print("\nFinal workflow result:")
    print_json(final_result)


if __name__ == "__main__":
    asyncio.run(main())