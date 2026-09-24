import json
from pathlib import Path
from time import perf_counter
from typing import Any

from cloud_incident_response_agent.config import (
    get_settings,
)
from cloud_incident_response_agent.database import (
    initialize_database,
)
from cloud_incident_response_agent.retrieval.runbook_search import (
    rerank_candidates,
    retrieve_candidates,
)


settings = get_settings()

EVALUATION_FILE = Path(
    "data/evaluations/"
    "runbook_retrieval_cases.json"
)

RESULT_DIRECTORY = Path(
    "evaluation_results"
)

RESULT_FILE = (
    RESULT_DIRECTORY
    / "runbook_retrieval_results.json"
)

TOP_K = 5


def load_evaluation_cases() -> list[
    dict[str, Any]
]:
    if not EVALUATION_FILE.exists():
        raise FileNotFoundError(
            "Retrieval evaluation file "
            f"not found: {EVALUATION_FILE}"
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


def normalize(value: str) -> str:
    return " ".join(
        value.casefold().split()
    )


def is_expected_result(
    file_name: str,
    heading: str,
    expected_file_name: str,
    expected_heading: str,
) -> bool:
    return (
        normalize(file_name)
        == normalize(expected_file_name)
        and normalize(heading)
        == normalize(expected_heading)
    )


def find_semantic_rank(
    candidates: list[Any],
    expected_file_name: str,
    expected_heading: str,
) -> int | None:
    for rank, (
        chunk,
        _semantic_score,
    ) in enumerate(
        candidates,
        start=1,
    ):
        if is_expected_result(
            file_name=chunk.file_name,
            heading=chunk.heading,
            expected_file_name=(
                expected_file_name
            ),
            expected_heading=(
                expected_heading
            ),
        ):
            return rank

    return None


def find_reranked_rank(
    results: list[Any],
    expected_file_name: str,
    expected_heading: str,
) -> int | None:
    for rank, result in enumerate(
        results,
        start=1,
    ):
        if is_expected_result(
            file_name=result.file_name,
            heading=result.heading,
            expected_file_name=(
                expected_file_name
            ),
            expected_heading=(
                expected_heading
            ),
        ):
            return rank

    return None


def reciprocal_rank(
    rank: int | None,
) -> float:
    if rank is None:
        return 0.0

    return 1.0 / rank


def evaluate_case(
    case: dict[str, Any],
) -> dict[str, Any]:
    case_id = str(case["id"])
    query = str(case["query"])

    expected_file_name = str(
        case["expected_file_name"]
    )

    expected_heading = str(
        case["expected_heading"]
    )

    candidate_count = max(
        settings.retrieval_candidate_count,
        TOP_K,
    )

    retrieval_started_at = perf_counter()

    candidates = retrieve_candidates(
        query=query,
        candidate_count=candidate_count,
    )

    retrieval_latency_ms = round(
        (
            perf_counter()
            - retrieval_started_at
        )
        * 1000,
        2,
    )

    semantic_rank = find_semantic_rank(
        candidates=candidates,
        expected_file_name=(
            expected_file_name
        ),
        expected_heading=expected_heading,
    )

    reranking_started_at = perf_counter()

    reranked_results = rerank_candidates(
        query=query,
        candidates=candidates,
        top_k=TOP_K,
    )

    reranking_latency_ms = round(
        (
            perf_counter()
            - reranking_started_at
        )
        * 1000,
        2,
    )

    reranked_rank = find_reranked_rank(
        results=reranked_results,
        expected_file_name=(
            expected_file_name
        ),
        expected_heading=expected_heading,
    )

    semantic_hit = (
        semantic_rank is not None
        and semantic_rank <= TOP_K
    )

    reranked_hit = (
        reranked_rank is not None
        and reranked_rank <= TOP_K
    )

    reranker_improved_rank = (
        semantic_rank is not None
        and reranked_rank is not None
        and reranked_rank < semantic_rank
    )

    passed = reranked_hit

    return {
        "id": case_id,
        "query": query,
        "expected_file_name": (
            expected_file_name
        ),
        "expected_heading": (
            expected_heading
        ),
        "semantic_rank": semantic_rank,
        "reranked_rank": reranked_rank,
        "semantic_hit_at_5": semantic_hit,
        "reranked_hit_at_5": reranked_hit,
        "semantic_reciprocal_rank": round(
            reciprocal_rank(
                semantic_rank
            ),
            4,
        ),
        "reranked_reciprocal_rank": round(
            reciprocal_rank(
                reranked_rank
            ),
            4,
        ),
        "reranker_improved_rank": (
            reranker_improved_rank
        ),
        "retrieval_latency_ms": (
            retrieval_latency_ms
        ),
        "reranking_latency_ms": (
            reranking_latency_ms
        ),
        "passed": passed,
        "top_results": [
            result.to_dict()
            for result in reranked_results
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
    case_count = len(results)

    passed_cases = sum(
        1
        for result in results
        if result["passed"]
    )

    semantic_hits = sum(
        1
        for result in results
        if result["semantic_hit_at_5"]
    )

    reranked_hits = sum(
        1
        for result in results
        if result["reranked_hit_at_5"]
    )

    semantic_top_one = sum(
        1
        for result in results
        if result["semantic_rank"] == 1
    )

    reranked_top_one = sum(
        1
        for result in results
        if result["reranked_rank"] == 1
    )

    improved_cases = sum(
        1
        for result in results
        if result[
            "reranker_improved_rank"
        ]
    )

    divisor = case_count or 1

    return {
        "case_count": case_count,
        "passed_cases": passed_cases,
        "pass_rate": round(
            passed_cases / divisor,
            4,
        ),
        "semantic_recall_at_5": round(
            semantic_hits / divisor,
            4,
        ),
        "reranked_recall_at_5": round(
            reranked_hits / divisor,
            4,
        ),
        "semantic_mrr": round(
            average(
                [
                    float(
                        result[
                            "semantic_reciprocal_rank"
                        ]
                    )
                    for result in results
                ]
            ),
            4,
        ),
        "reranked_mrr": round(
            average(
                [
                    float(
                        result[
                            "reranked_reciprocal_rank"
                        ]
                    )
                    for result in results
                ]
            ),
            4,
        ),
        "semantic_top_1_accuracy": round(
            semantic_top_one / divisor,
            4,
        ),
        "reranked_top_1_accuracy": round(
            reranked_top_one / divisor,
            4,
        ),
        "reranker_improved_cases": (
            improved_cases
        ),
        "average_retrieval_latency_ms": round(
            average(
                [
                    float(
                        result[
                            "retrieval_latency_ms"
                        ]
                    )
                    for result in results
                ]
            ),
            2,
        ),
        "average_reranking_latency_ms": round(
            average(
                [
                    float(
                        result[
                            "reranking_latency_ms"
                        ]
                    )
                    for result in results
                ]
            ),
            2,
        ),
    }


def main() -> None:
    initialize_database()

    cases = load_evaluation_cases()

    print(
        f"Running {len(cases)} "
        "retrieval evaluation cases..."
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