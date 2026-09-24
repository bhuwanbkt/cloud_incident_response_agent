import asyncio
import logging
from collections.abc import (
    AsyncGenerator,
    Awaitable,
    Callable,
)
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import (
    FastAPI,
    Request,
    Response,
)
from langgraph.checkpoint.sqlite.aio import (
    AsyncSqliteSaver,
)

from cloud_incident_response_agent.agents.graph import (
    build_incident_graph,
)
from cloud_incident_response_agent.api.incidents import (
    router as incidents_router,
)
from cloud_incident_response_agent.config import (
    get_settings,
)
from cloud_incident_response_agent.database import (
    SessionLocal,
    initialize_database,
)
from cloud_incident_response_agent.observability import (
    configure_logging,
    create_request_id,
    reset_request_id,
    set_request_id,
)
from cloud_incident_response_agent.services.runbook_sync import (
    sync_runbooks,
)


settings = get_settings()
configure_logging()

logger = logging.getLogger(__name__)

CHECKPOINT_DIRECTORY = Path(
    "data/checkpoints"
)

CHECKPOINT_DATABASE = (
    CHECKPOINT_DIRECTORY
    / "incidents.sqlite"
)


def initialize_runbook_storage() -> dict[
    str,
    Any,
]:
    """
    Initialize PostgreSQL and synchronize runbooks.

    This function is synchronous because SQLAlchemy and
    the embedding model currently use synchronous APIs.
    FastAPI runs it in a worker thread during startup.
    """
    initialize_database()

    with SessionLocal() as database:
        result = sync_runbooks(
            database=database,
            runbook_directory=(
                settings.runbook_directory
            ),
        )

    return asdict(result)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncGenerator[None, None]:
    CHECKPOINT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger.info(
        "Starting incident response API"
    )

    runbook_sync_result = await asyncio.to_thread(
        initialize_runbook_storage
    )

    logger.info(
        "PostgreSQL runbook storage ready",
        extra={
            "runbook_sync": (
                runbook_sync_result
            ),
        },
    )

    async with (
        AsyncSqliteSaver.from_conn_string(
            str(CHECKPOINT_DATABASE)
        )
    ) as checkpointer:
        await checkpointer.setup()

        app.state.incident_graph = (
            build_incident_graph(
                checkpointer=checkpointer
            )
        )

        logger.info(
            "SQLite checkpoint storage ready"
        )

        yield

    logger.info(
        "Incident response API stopped"
    )


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "MCP-powered cloud incident investigation "
        "and remediation agent."
    ),
    lifespan=lifespan,
)

app.include_router(incidents_router)


@app.middleware("http")
async def log_http_request(
    request: Request,
    call_next: Callable[
        [Request],
        Awaitable[Response],
    ],
) -> Response:
    request_id = create_request_id()

    request_id_token = set_request_id(
        request_id
    )

    started_at = perf_counter()

    log_fields = {
        "method": request.method,
        "path": request.url.path,
    }

    try:
        response = await call_next(request)

        duration_ms = round(
            (
                perf_counter()
                - started_at
            )
            * 1000,
            2,
        )

        response.headers[
            "X-Request-ID"
        ] = request_id

        logger.info(
            "HTTP request completed",
            extra={
                **log_fields,
                "status_code": (
                    response.status_code
                ),
                "duration_ms": duration_ms,
            },
        )

        return response

    except Exception:
        duration_ms = round(
            (
                perf_counter()
                - started_at
            )
            * 1000,
            2,
        )

        logger.exception(
            "HTTP request failed",
            extra={
                **log_fields,
                "status_code": 500,
                "duration_ms": duration_ms,
            },
        )

        raise

    finally:
        reset_request_id(
            request_id_token
        )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": (
            "cloud-incident-response-agent"
        ),
        "environment": (
            settings.app_environment
        ),
    }