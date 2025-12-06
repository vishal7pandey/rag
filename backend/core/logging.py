"""Structured JSON logging setup for the RAG backend.

This module configures Python's standard `logging` library to emit
newline-delimited JSON to stdout, enriched with trace context from
:mod:`backend.core.tracing`.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict

from backend.core.tracing import get_trace_context


class JSONFormatter(logging.Formatter):
    """Format log records as structured JSON suitable for shipping to log sinks."""

    def __init__(self, environment: str = "dev") -> None:
        super().__init__()
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "context": getattr(record, "context", {}),
            "environment": self.environment,
        }

        # Attach trace context if available
        trace_ctx = get_trace_context()
        if any(trace_ctx.values()):
            log_data["trace_context"] = trace_ctx

        # Attach basic error info if present
        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            if exc_type is not None and exc_value is not None:
                log_data["error"] = {
                    "type": exc_type.__name__,
                    "message": str(exc_value),
                }

        return json.dumps(log_data)


def setup_logging(
    environment: str = "dev",
    level: str = "INFO",
    logger_name: str = "rag",
) -> logging.Logger:
    """Configure structured JSON logging to stdout.

    Returns the configured root logger for the given ``logger_name``.
    """

    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicate output when reconfiguring
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(environment=environment))
    logger.addHandler(handler)

    # Avoid propagating to ancestor loggers to prevent duplicate logs
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.LoggerAdapter:
    """Return a logger adapter supporting an optional ``context`` mapping.

    The adapter allows callers to pass an extra ``context`` dict which will be
    serialized into the JSON log output.
    """

    base_logger = logging.getLogger(name)
    return logging.LoggerAdapter(base_logger, {"context": {}})
