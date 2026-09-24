from functools import lru_cache

from sentence_transformers import (
    SentenceTransformer,
)

from cloud_incident_response_agent.config import (
    get_settings,
)


settings = get_settings()


class EmbeddingService:
    def __init__(self) -> None:
        self.model = SentenceTransformer(
            settings.embedding_model
        )

        actual_dimension = (
            self.model
            .get_sentence_embedding_dimension()
        )

        if actual_dimension is None:
            raise ValueError(
                "The model did not report its "
                "embedding dimension."
            )

        if (
            actual_dimension
            != settings.embedding_dimension
        ):
            raise ValueError(
                "Embedding dimension mismatch. "
                f"Configured: "
                f"{settings.embedding_dimension}, "
                f"model: {actual_dimension}."
            )

    def embed_text(
        self,
        text: str,
    ) -> list[float]:
        embedding = self.model.encode(
            text,
            normalize_embeddings=True,
        )

        return embedding.tolist()

    def embed_texts(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )

        return embeddings.tolist()


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()