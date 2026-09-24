import json
from pathlib import Path
from time import perf_counter
from typing import Any

from cloud_incident_response_agent.database import (
    initialize_database,
)
from cloud_incident_response_agent.retrieval.runbook_search import (
    search_runbooks,
)


EVALUATION_FILE = Path(
    "data/evaluations/"
    "runbook_relevance_cases.json"
)

RESULT_DIRECTORY = Path(
    "evaluation_results"
)

RESULT_FILE = (
    RESULT_DIRECTORY
    / "runbook_relevance_results.json"
)

TOP_K = 5


def normalize(value: str) -> str:
    return " ".join(
        value.casefold().split()
    )


def load_cases() -> list[dict[str, Any]]:
    if not EVALUATION_FILE.exists():
        raise FileNotFoundError(
            "Evaluation file not found: "
            f"{EVALUATION_FILE}"
        )

    with EVALUATION_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        cases = json.load(file)

    if not isinstance(cases, list):
        raise ValueError(
            "Evaluation data must be a JSON array."
        )

    return cases


def find_expected_rank(
    results: list[Any],
    expected_file_name: str,
    expected_heading: str,
) -> int | None:
    for rank, result in enumerate(
        results,
        start=1,
    ):
        file_matches = (
            normalize(result.file_name)
            == normalize(expected_file_name)
        )

        heading_matches = (
            normalize(result.heading)
            == normalize(expected_heading)
        )

        if file_matches and heading_matches:
            return rank

    return None


def evaluate_case(
    case: dict[str, Any],
) -> dict[str, Any]:
    query = str(case["query"])

    expected_relevant = bool(
        case["expected_relevant"]
    )

    started_at = perf_counter()

    results = search_runbooks(
        query=query,
        top_k=TOP_K,
    )

    latency_ms = round(
        (
            perf_counter()
            - started_at
        )
        * 1000,
        2,
    )

    if not expected_relevant:
        rejected = len(results) == 0

        return {
            "id": case["id"],
            "query": query,
            "expected_relevant": False,
            "result_count": len(results),
            "rejected": rejected,
            "passed": rejected,
            "latency_ms": latency_ms,
            "results": [
                result.to_dict()
                for result in results
            ],
        }

    expected_file_name = str(
        case["expected_file_name"]
    )

    expected_heading = str(
        case["expected_heading"]
    )

    expected_rank = find_expected_rank(
        results=results,
        expected_file_name=(
            expected_file_name
        ),
        expected_heading=(
            expected_heading
        ),
    )

    retrieval_hit = (
        expected_rank is not None
    )

    return {
        "id": case["id"],
        "query": query,
        "expected_relevant": True,
        "expected_file_name": (
            expected_file_name
        ),
        "expected_heading": (
            expected_heading
        ),
        "result_count": len(results),
        "expected_rank": expected_rank,
        "retrieval_hit": retrieval_hit,
        "passed": retrieval_hit,
        "latency_ms": latency_ms,
        "results": [
            result.to_dict()
            for result in results
        ],
    }


def average(
    values: list[float],
) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)


def create_summary(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    relevant_results = [
        result
        for result in results
        if result["expected_relevant"]
    ]

    unsupported_results = [
        result
        for result in results
        if not result["expected_relevant"]
    ]

    relevant_passes = sum(
        1
        for result in relevant_results
        if result["passed"]
    )

    rejection_passes = sum(
        1
        for result in unsupported_results
        if result["passed"]
    )

    total_passes = sum(
        1
        for result in results
        if result["passed"]
    )

    relevant_count = (
        len(relevant_results)
    )

    unsupported_count = (
        len(unsupported_results)
    )

    total_count = len(results)

    return {
        "case_count": total_count,
        "passed_cases": total_passes,
        "overall_accuracy": round(
            total_passes
            / (total_count or 1),
            4,
        ),
        "relevant_case_count": (
            relevant_count
        ),
        "relevant_retrieval_accuracy": round(
            relevant_passes
            / (relevant_count or 1),
            4,
        ),
        "unsupported_case_count": (
            unsupported_count
        ),
        "rejection_accuracy": round(
            rejection_passes
            / (unsupported_count or 1),
            4,
        ),
        "average_latency_ms": round(
            average(
                [
                    float(
                        result["latency_ms"]
                    )
                    for result in results
                ]
            ),
            2,
        ),
    }


def main() -> None:
    initialize_database()

    cases = load_cases()

    print(
        f"Running {len(cases)} "
        "relevance evaluation cases..."
    )

    results: list[dict[str, Any]] = []

    for case in cases:
        print(
            f"\nEvaluating: {case['id']}"
        )

        try:
            result = evaluate_case(case)
        except Exception as error:
            result = {
                "id": case.get(
                    "id",
                    "unknown",
                ),
                "query": case.get(
                    "query",
                    "",
                ),
                "expected_relevant": (
                    case.get(
                        "expected_relevant",
                        False,
                    )
                ),
                "passed": False,
                "error": str(error),
            }

        results.append(result)

        status = (
            "PASS"
            if result.get("passed")
            else "FAIL"
        )

        print(f"Result: {status}")

    report = {
        "summary": create_summary(
            results
        ),
        "cases": results,
    }

    RESULT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    RESULT_FILE.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "\n"
        + json.dumps(
            report["summary"],
            indent=2,
        )
    )

    print(
        "\nFull results saved to: "
        f"{RESULT_FILE}"
    )


if __name__ == "__main__":
    main()