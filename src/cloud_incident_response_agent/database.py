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
    Create a database session and always close it.
    """
    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()


def initialize_database() -> None:
    """
    Enable pgvector and create application tables.

    Alembic migrations will replace create_all later.
    """
    from cloud_incident_response_agent import models

    # This import registers the model classes with
    # SQLAlchemy's Base metadata.
    _ = models

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE EXTENSION IF NOT EXISTS vector"
            )
        )

    Base.metadata.create_all(bind=engine)