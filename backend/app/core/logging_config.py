"""
Application-wide logging configuration.

We use the standard library logging module with a structured, single-line
format that includes a request ID (see middleware.py) so that every log line
emitted while handling a request can be correlated, even across the worker
processes started by gunicorn.

Trade-off: this is plain-text structured logging, not JSON. For LMH's scale
(small team, moderate traffic) this is readable directly in `docker logs` /
CloudWatch without extra tooling. If/when this feeds into a log aggregation
platform (e.g. Grafana Loki, CloudWatch Logs Insights), switching the
Formatter below to emit JSON (e.g. via python-json-logger) is a small,
isolated change — nothing else in the codebase needs to know about it.
"""

import logging
import sys

REQUEST_ID_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | request_id=%(request_id)s | %(message)s"
)
DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


class RequestIdFilter(logging.Filter):
    """Injects a default request_id so the formatter never KeyErrors.

    The middleware overrides this value per-request via a LoggerAdapter,
    but library code (SQLAlchemy, uvicorn, etc.) logs without that context,
    so we provide a fallback here.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


def configure_logging(log_level: str = "INFO") -> None:
    """Configure root logging. Call once at process startup."""
    root = logging.getLogger()
    root.setLevel(log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(REQUEST_ID_LOG_FORMAT))
    handler.addFilter(RequestIdFilter())

    # Avoid duplicate handlers if configure_logging() is called more than
    # once (e.g. under gunicorn's --preload + multiple workers).
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet down noisy third-party loggers unless we're debugging.
    if log_level.upper() != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)