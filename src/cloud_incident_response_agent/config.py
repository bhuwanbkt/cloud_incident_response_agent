from functools import lru_cache
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    app_name: str = "Cloud Incident Response Agent"
    app_environment: str = "development"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    mcp_server_url: str = (
        "http://127.0.0.1:8001/mcp"
    )

    data_directory: Path = Path("data")
    runbook_directory: Path = Path("data/runbooks")
    log_directory: Path = Path("data/logs")
    metric_directory: Path = Path("data/metrics")
    deployment_directory: Path = Path(
        "data/deployments"
    )

    embedding_model: str = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )
    reranker_model: str = (
        "cross-encoder/ms-marco-MiniLM-L6-v2"
    )

    retrieval_candidate_count: int = 30
    retrieval_top_k: int = 5

    database_url: str
    embedding_dimension: int = 384

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()