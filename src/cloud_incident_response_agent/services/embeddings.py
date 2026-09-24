from functools import lru_cache

from sentence_transformers import (
    SentenceTransformer,
)

from cloud_incident_response_agent.config import (
    get_settings,
)


settings = get_settings()


class EmbeddingService:
    """
    Generate normalized embeddings for runbook
    ingestion and pgvector retrieval.
    """

    def __init__(self) -> None:
        self.model = SentenceTransformer(
            settings.embedding_model
        )

        actual_dimension = (
            self.model.get_embedding_dimension()
        )

        if actual_dimension is None:
            raise ValueError(
                "The embedding model did not report "
                "its embedding dimension."
            )

        if (
            actual_dimension
            != settings.embedding_dimension
        ):
            raise ValueError(
                "Embedding dimension mismatch. "
                f"Configured dimension: "
                f"{settings.embedding_dimension}. "
                f"Model dimension: "
                f"{actual_dimension}."
            )

    def embed_text(
        self,
        text: str,
    ) -> list[float]:
        """
        Generate one normalized embedding.
        """
        normalized_text = text.strip()

        if not normalized_text:
            raise ValueError(
                "Text cannot be empty."
            )

        embedding = self.model.encode(
            normalized_text,
            normalize_embeddings=True,
        )

        return embedding.tolist()

    def embed_texts(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """
        Generate normalized embeddings in batches.
        """
        if not texts:
            return []

        normalized_texts = [
            text.strip()
            for text in texts
        ]

        if any(
            not text
            for text in normalized_texts
        ):
            raise ValueError(
                "Embedding input cannot contain "
                "empty text."
            )

        embeddings = self.model.encode(
            normalized_texts,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )

        return embeddings.tolist()


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()