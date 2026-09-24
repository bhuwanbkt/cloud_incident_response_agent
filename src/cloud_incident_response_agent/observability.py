import json
import logging
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


request_id_context: ContextVar[str] = (
    ContextVar(
        "request_id",
        default="not-available",
    )
)


def create_request_id() -> str:
    return f"request-{uuid4()}"


def set_request_id(
    request_id: str,
) -> Token[str]:
    return request_id_context.set(
        request_id
    )


def reset_request_id(
    token: Token[str],
) -> None:
    request_id_context.reset(token)


def get_request_id() -> str:
    return request_id_context.get()


class JsonLogFormatter(logging.Formatter):
    """Format application logs as JSON."""

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }

        additional_fields = (
            "method",
            "path",
            "status_code",
            "duration_ms",
            "thread_id",
            "service_name",
            "operation",
        )

        for field_name in additional_fields:
            field_value = getattr(
                record,
                field_name,
                None,
            )

            if field_value is not None:
                log_data[field_name] = (
                    field_value
                )

        if record.exc_info:
            log_data["exception"] = (
                self.formatException(
                    record.exc_info
                )
            )

        return json.dumps(
            log_data,
            default=str,
        )


def configure_logging() -> None:
    """Configure one JSON console handler."""

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonLogFormatter()
    )

    root_logger.handlers.clear()
    root_logger.addHandler(handler)