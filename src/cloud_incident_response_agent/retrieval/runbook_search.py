from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer
from sentence_transformers.cross_encoder import (
    CrossEncoder,
)

from cloud_incident_response_agent.config import (
    get_settings,
)
from cloud_incident_response_agent.retrieval.runbook_loader import (
    load_runbooks,
)
from cloud_incident_response_agent.retrieval.schemas import (
    RunbookChunk,
    RunbookSearchResult,
)


settings = get_settings()


@lru_cache
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(
        settings.embedding_model
    )


@lru_cache
def get_reranker_model() -> CrossEncoder:
    return CrossEncoder(
        settings.reranker_model
    )


@lru_cache
def get_runbook_chunks() -> tuple[RunbookChunk, ...]:
    chunks = load_runbooks(
        settings.runbook_directory
    )

    return tuple(chunks)


@lru_cache
def get_runbook_embeddings() -> np.ndarray:
    chunks = get_runbook_chunks()

    if not chunks:
        return np.empty(
            shape=(0, 0),
            dtype=np.float32,
        )

    embedding_texts = [
        (
            f"Runbook: {chunk.runbook_name}\n"
            f"Section: {chunk.heading}\n"
            f"{chunk.content}"
        )
        for chunk in chunks
    ]

    model = get_embedding_model()

    embeddings = model.encode(
        embedding_texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    return np.asarray(
        embeddings,
        dtype=np.float32,
    )


def retrieve_candidates(
    query: str,
    candidate_count: int | None = None,
) -> list[tuple[RunbookChunk, float]]:
    normalized_query = query.strip()

    if not normalized_query:
        raise ValueError(
            "Search query cannot be empty."
        )

    chunks = get_runbook_chunks()

    if not chunks:
        return []

    requested_count = (
        candidate_count
        or settings.retrieval_candidate_count
    )

    if requested_count < 1:
        raise ValueError(
            "Candidate count must be positive."
        )

    model = get_embedding_model()

    query_embedding = model.encode(
        normalized_query,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    chunk_embeddings = get_runbook_embeddings()

    similarity_scores = (
        chunk_embeddings
        @ np.asarray(
            query_embedding,
            dtype=np.float32,
        )
    )

    candidate_indexes = np.argsort(
        similarity_scores
    )[::-1][:requested_count]

    return [
        (
            chunks[int(index)],
            float(similarity_scores[index]),
        )
        for index in candidate_indexes
    ]


def rerank_candidates(
    query: str,
    candidates: list[
        tuple[RunbookChunk, float]
    ],
    top_k: int,
) -> list[RunbookSearchResult]:
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
                f"Runbook: {chunk.runbook_name}\n"
                f"Section: {chunk.heading}\n"
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
        key=lambda result: result.reranker_score,
        reverse=True,
    )[:top_k]


def search_runbooks(
    query: str,
    top_k: int | None = None,
) -> list[RunbookSearchResult]:
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