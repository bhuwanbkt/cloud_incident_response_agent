from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)

from cloud_incident_response_agent.config import (
    get_settings,
)


settings = get_settings()


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_database() -> Generator[
    Session,
    None,
    None,
]:
    """
    Provide a database session and always close it.
    """
    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()


def initialize_database() -> None:
    """
    Verify that PostgreSQL, pgvector, and the required
    Alembic-managed tables are available.

    This function does not create or modify tables.
    """
    with engine.connect() as connection:
        database_status = (
            connection.execute(
                text(
                    """
                    SELECT
                        EXISTS (
                            SELECT 1
                            FROM pg_extension
                            WHERE extname = 'vector'
                        ) AS vector_enabled,
                        (
                            to_regclass(
                                'public.runbook_documents'
                            ) IS NOT NULL
                        ) AS documents_table_exists,
                        (
                            to_regclass(
                                'public.runbook_chunks'
                            ) IS NOT NULL
                        ) AS chunks_table_exists
                    """
                )
            )
            .mappings()
            .one()
        )

    if not database_status[
        "vector_enabled"
    ]:
        raise RuntimeError(
            "The pgvector extension is not enabled. "
            "Run: uv run alembic upgrade head"
        )

    if not database_status[
        "documents_table_exists"
    ]:
        raise RuntimeError(
            "The runbook_documents table is missing. "
            "Run: uv run alembic upgrade head"
        )

    if not database_status[
        "chunks_table_exists"
    ]:
        raise RuntimeError(
            "The runbook_chunks table is missing. "
            "Run: uv run alembic upgrade head"
        )