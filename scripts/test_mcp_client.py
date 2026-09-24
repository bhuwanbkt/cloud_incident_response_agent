import asyncio
import json
from typing import Any

from mcp import Client


def unwrap_result(
    structured_content: Any,
) -> Any:
    if (
        isinstance(structured_content, dict)
        and "result" in structured_content
    ):
        return structured_content["result"]

    return structured_content


def display_result(
    tool_name: str,
    structured_content: Any,
) -> None:
    result = unwrap_result(
        structured_content
    )

    print(f"\n--- {tool_name} ---")

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


async def main() -> None:
    async with Client(
        "http://127.0.0.1:8000/mcp"
    ) as client:
        print("Connected to MCP server.")

        print(
            "\nCalling get_service_metrics..."
        )

        metrics_result = await client.call_tool(
            "get_service_metrics",
            {
                "service_name": "payment-api",
            },
        )

        display_result(
            "get_service_metrics",
            metrics_result.structured_content,
        )

        print(
            "\nCalling search_application_logs..."
        )

        logs_result = await client.call_tool(
            "search_application_logs",
            {
                "service_name": "payment-api",
                "level": "ERROR",
                "limit": 20,
            },
        )

        display_result(
            "search_application_logs",
            logs_result.structured_content,
        )

        print(
            "\nCalling get_recent_deployments..."
        )

        deployments_result = await client.call_tool(
            "get_recent_deployments",
            {
                "service_name": "payment-api",
                "limit": 5,
            },
        )

        display_result(
            "get_recent_deployments",
            deployments_result.structured_content,
        )

        print(
            "\nCalling search_runbooks..."
        )

        runbooks_result = await client.call_tool(
            "search_runbooks",
            {
                "query": (
                    "The payment API has high latency, "
                    "database connection timeouts, and "
                    "HTTP 500 errors."
                ),
                "top_k": 5,
            },
        )

        display_result(
            "search_runbooks",
            runbooks_result.structured_content,
        )

        print(
            "\nAll MCP tools completed successfully."
        )


if __name__ == "__main__":
    asyncio.run(main())