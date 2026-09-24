from functools import lru_cache

from sentence_transformers.cross_encoder import (
    CrossEncoder,
)
from sqlalchemy import select

from cloud_incident_response_agent.config import (
    get_settings,
)
from cloud_incident_response_agent.database import (
    SessionLocal,
)
from cloud_incident_response_agent.models.runbook import (
    RunbookChunk as DatabaseRunbookChunk,
)
from cloud_incident_response_agent.models.runbook import (
    RunbookDocument,
)
from cloud_incident_response_agent.retrieval.schemas import (
    RunbookChunk,
    RunbookSearchResult,
)
from cloud_incident_response_agent.services.embeddings import (
    get_embedding_service,
)


settings = get_settings()


@lru_cache(maxsize=1)
def get_reranker_model() -> CrossEncoder:
    return CrossEncoder(
        settings.reranker_model
    )


def retrieve_candidates(
    query: str,
    candidate_count: int | None = None,
) -> list[tuple[RunbookChunk, float]]:
    """
    Retrieve candidate chunks from PostgreSQL
    using pgvector cosine distance.
    """
    normalized_query = query.strip()

    if not normalized_query:
        raise ValueError(
            "Search query cannot be empty."
        )

    requested_count = (
        candidate_count
        or settings.retrieval_candidate_count
    )

    if requested_count < 1:
        raise ValueError(
            "Candidate count must be positive."
        )

    embedding_service = (
        get_embedding_service()
    )

    query_embedding = (
        embedding_service.embed_text(
            normalized_query
        )
    )

    cosine_distance = (
        DatabaseRunbookChunk.embedding
        .cosine_distance(query_embedding)
    )

    statement = (
        select(
            DatabaseRunbookChunk,
            RunbookDocument,
            cosine_distance.label(
                "cosine_distance"
            ),
        )
        .join(
            RunbookDocument,
            DatabaseRunbookChunk.document_id
            == RunbookDocument.id,
        )
        .order_by(cosine_distance)
        .limit(requested_count)
    )

    with SessionLocal() as database:
        rows = database.execute(
            statement
        ).all()

    candidates: list[
        tuple[RunbookChunk, float]
    ] = []

    for (
        database_chunk,
        document,
        distance,
    ) in rows:
        semantic_score = (
            1.0 - float(distance)
        )

        candidates.append(
            (
                RunbookChunk(
                    runbook_name=(
                        document.runbook_name
                    ),
                    file_name=(
                        document.file_name
                    ),
                    heading=(
                        database_chunk.heading
                        or "Overview"
                    ),
                    content=(
                        database_chunk.content
                    ),
                ),
                semantic_score,
            )
        )

    return candidates


def rerank_candidates(
    query: str,
    candidates: list[
        tuple[RunbookChunk, float]
    ],
    top_k: int,
) -> list[RunbookSearchResult]:
    """
    Rerank pgvector candidates with a
    cross-encoder model.
    """
    if top_k < 1:
        raise ValueError(
            "Top K must be positive."
        )

    if not candidates:
        return []

    pairs = [
        [
            query,
            (
                f"Runbook: "
                f"{chunk.runbook_name}\n"
                f"Section: "
                f"{chunk.heading}\n"
                f"{chunk.content}"
            ),
        ]
        for chunk, _semantic_score in candidates
    ]

    reranker = get_reranker_model()

    reranker_scores = reranker.predict(
        pairs
    )

    scored_results = [
        RunbookSearchResult(
            runbook_name=chunk.runbook_name,
            file_name=chunk.file_name,
            heading=chunk.heading,
            content=chunk.content,
            semantic_score=semantic_score,
            reranker_score=float(
                reranker_score
            ),
        )
        for (
            chunk,
            semantic_score,
        ), reranker_score in zip(
            candidates,
            reranker_scores,
            strict=True,
        )
    ]

    return sorted(
        scored_results,
        key=lambda result: (
            result.reranker_score
        ),
        reverse=True,
    )[:top_k]


def search_runbooks(
    query: str,
    top_k: int | None = None,
) -> list[RunbookSearchResult]:
    """
    Perform two-stage runbook retrieval:

    1. pgvector semantic candidate retrieval
    2. Cross-encoder reranking
    """
    final_top_k = (
        top_k
        or settings.retrieval_top_k
    )

    if final_top_k < 1 or final_top_k > 20:
        raise ValueError(
            "Top K must be between 1 and 20."
        )

    candidate_count = max(
        settings.retrieval_candidate_count,
        final_top_k,
    )

    candidates = retrieve_candidates(
        query=query,
        candidate_count=candidate_count,
    )

    return rerank_candidates(
        query=query,
        candidates=candidates,
        top_k=final_top_k,
    )