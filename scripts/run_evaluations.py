import asyncio
import json
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from cloud_incident_response_agent.agents.graph import (
    incident_graph,
)


EVALUATION_DATASET = Path(
    "data/evaluations/incidents.json"
)

EVALUATION_RESULTS = Path(
    "data/evaluations/results.json"
)


def load_evaluation_cases() -> list[
    dict[str, Any]
]:
    with EVALUATION_DATASET.open(
        "r",
        encoding="utf-8",
    ) as dataset_file:
        evaluation_cases = json.load(
            dataset_file
        )

    if not isinstance(
        evaluation_cases,
        list,
    ):
        raise ValueError(
            "Evaluation dataset must "
            "contain a JSON list."
        )

    return evaluation_cases


def create_initial_state(
    evaluation_case: dict[str, Any],
) -> dict[str, Any]:
    return {
        "incident_description": (
            evaluation_case[
                "incident_description"
            ]
        ),
        "service_name": (
            evaluation_case[
                "service_name"
            ]
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


def normalize_text(value: str) -> str:
    return " ".join(
        value.casefold().split()
    )


def calculate_keyword_coverage(
    actual_text: str,
    expected_keywords: list[str],
) -> float:
    if not expected_keywords:
        return 1.0

    normalized_actual = normalize_text(
        actual_text
    )

    matched_keywords = sum(
        1
        for keyword in expected_keywords
        if normalize_text(keyword)
        in normalized_actual
    )

    return (
        matched_keywords
        / len(expected_keywords)
    )


def get_evidence_types(
    diagnosis: dict[str, Any],
) -> set[str]:
    evidence_items = diagnosis.get(
        "supporting_evidence",
        [],
    )

    evidence_types: set[str] = set()

    for evidence_item in evidence_items:
        if not isinstance(
            evidence_item,
            dict,
        ):
            continue

        source_type = evidence_item.get(
            "source_type"
        )

        if isinstance(source_type, str):
            evidence_types.add(
                source_type
            )

    return evidence_types


def calculate_evidence_coverage(
    actual_types: set[str],
    expected_types: list[str],
) -> float:
    if not expected_types:
        return 1.0

    expected_type_set = set(
        expected_types
    )

    matched_types = (
        actual_types
        & expected_type_set
    )

    return (
        len(matched_types)
        / len(expected_type_set)
    )


async def evaluate_case(
    evaluation_case: dict[str, Any],
) -> dict[str, Any]:
    thread_id = (
        f"evaluation-{uuid4()}"
    )

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    started_at = perf_counter()

    try:
        result = await incident_graph.ainvoke(
            create_initial_state(
                evaluation_case
            ),
            config=config,
        )

        latency_ms = round(
            (
                perf_counter()
                - started_at
            )
            * 1000,
            2,
        )

        diagnosis = result.get(
            "diagnosis"
        )

        if not isinstance(
            diagnosis,
            dict,
        ):
            return {
                "id": evaluation_case["id"],
                "thread_id": thread_id,
                "passed": False,
                "diagnosis_present": False,
                "latency_ms": latency_ms,
                "error": (
                    "The workflow did not "
                    "produce a diagnosis."
                ),
            }

        suspected_cause = str(
            diagnosis.get(
                "suspected_cause",
                "",
            )
        )

        expected_keywords = (
            evaluation_case[
                "expected_cause_keywords"
            ]
        )

        keyword_coverage = (
            calculate_keyword_coverage(
                actual_text=suspected_cause,
                expected_keywords=(
                    expected_keywords
                ),
            )
        )

        cause_correct = (
            keyword_coverage == 1.0
        )

        actual_severity = diagnosis.get(
            "severity"
        )
        expected_severity = (
            evaluation_case[
                "expected_severity"
            ]
        )

        severity_correct = (
            actual_severity
            == expected_severity
        )

        actual_evidence_types = (
            get_evidence_types(
                diagnosis
            )
        )

        expected_evidence_types = (
            evaluation_case[
                "expected_evidence_types"
            ]
        )

        evidence_coverage = (
            calculate_evidence_coverage(
                actual_types=(
                    actual_evidence_types
                ),
                expected_types=(
                    expected_evidence_types
                ),
            )
        )

        actual_human_approval = (
            diagnosis.get(
                "requires_human_approval"
            )
        )

        expected_human_approval = (
            evaluation_case[
                "expected_human_approval"
            ]
        )

        approval_correct = (
            actual_human_approval
            == expected_human_approval
        )

        diagnosis_valid = bool(
            result.get(
                "diagnosis_valid"
            )
        )

        passed = all(
            [
                cause_correct,
                severity_correct,
                evidence_coverage == 1.0,
                approval_correct,
                diagnosis_valid,
            ]
        )

        return {
            "id": evaluation_case["id"],
            "thread_id": thread_id,
            "passed": passed,
            "diagnosis_present": True,
            "suspected_cause": (
                suspected_cause
            ),
            "expected_cause_keywords": (
                expected_keywords
            ),
            "keyword_coverage": round(
                keyword_coverage,
                4,
            ),
            "cause_correct": (
                cause_correct
            ),
            "actual_severity": (
                actual_severity
            ),
            "expected_severity": (
                expected_severity
            ),
            "severity_correct": (
                severity_correct
            ),
            "actual_evidence_types": (
                sorted(
                    actual_evidence_types
                )
            ),
            "expected_evidence_types": (
                expected_evidence_types
            ),
            "evidence_coverage": round(
                evidence_coverage,
                4,
            ),
            "actual_human_approval": (
                actual_human_approval
            ),
            "expected_human_approval": (
                expected_human_approval
            ),
            "approval_correct": (
                approval_correct
            ),
            "diagnosis_valid": (
                diagnosis_valid
            ),
            "diagnosis_attempts": (
                result.get(
                    "diagnosis_attempts"
                )
            ),
            "latency_ms": latency_ms,
            "validation_errors": (
                result.get(
                    "validation_errors",
                    [],
                )
            ),
            "workflow_errors": (
                result.get(
                    "errors",
                    [],
                )
            ),
            "error": None,
        }

    except Exception as exception:
        latency_ms = round(
            (
                perf_counter()
                - started_at
            )
            * 1000,
            2,
        )

        return {
            "id": evaluation_case["id"],
            "thread_id": thread_id,
            "passed": False,
            "diagnosis_present": False,
            "latency_ms": latency_ms,
            "error": str(exception),
        }


def calculate_rate(
    results: list[dict[str, Any]],
    field_name: str,
) -> float:
    if not results:
        return 0.0

    successful_items = sum(
        1
        for result in results
        if result.get(field_name) is True
    )

    return round(
        successful_items / len(results),
        4,
    )


def calculate_average(
    results: list[dict[str, Any]],
    field_name: str,
) -> float:
    if not results:
        return 0.0

    values = [
        float(result.get(field_name, 0))
        for result in results
    ]

    return round(
        sum(values) / len(values),
        2,
    )


async def main() -> None:
    evaluation_cases = (
        load_evaluation_cases()
    )

    print(
        f"Running {len(evaluation_cases)} "
        "incident evaluation cases..."
    )

    results: list[
        dict[str, Any]
    ] = []

    # Run sequentially to avoid overwhelming
    # Ollama and the local MCP server.
    for evaluation_case in (
        evaluation_cases
    ):
        print(
            "Evaluating: "
            f"{evaluation_case['id']}"
        )

        case_result = await evaluate_case(
            evaluation_case
        )

        results.append(case_result)

        result_label = (
            "PASS"
            if case_result["passed"]
            else "FAIL"
        )

        print(
            f"Result: {result_label}"
        )

    summary = {
        "case_count": len(results),
        "passed_cases": sum(
            1
            for result in results
            if result["passed"]
        ),
        "overall_pass_rate": (
            calculate_rate(
                results,
                "passed",
            )
        ),
        "cause_accuracy": (
            calculate_rate(
                results,
                "cause_correct",
            )
        ),
        "average_keyword_coverage": (
            calculate_average(
                results,
                "keyword_coverage",
            )
        ),
        "severity_accuracy": (
            calculate_rate(
                results,
                "severity_correct",
            )
        ),
        "average_evidence_coverage": (
            calculate_average(
                results,
                "evidence_coverage",
            )
        ),
        "approval_gate_accuracy": (
            calculate_rate(
                results,
                "approval_correct",
            )
        ),
        "diagnosis_validation_rate": (
            calculate_rate(
                results,
                "diagnosis_valid",
            )
        ),
        "average_latency_ms": (
            calculate_average(
                results,
                "latency_ms",
            )
        ),
        "error_count": sum(
            1
            for result in results
            if result.get("error")
        ),
    }

    evaluation_report = {
        "summary": summary,
        "cases": results,
    }

    EVALUATION_RESULTS.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    EVALUATION_RESULTS.write_text(
        json.dumps(
            evaluation_report,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        json.dumps(
            summary,
            indent=2,
        )
    )
    print()
    print(
        "Full results saved to: "
        f"{EVALUATION_RESULTS}"
    )


if __name__ == "__main__":
    asyncio.run(main())