import logging

from app.core.logging.request import RequestLoggingMiddleware


def configure_dependency_logging() -> None:
    for logger_name in ("httpx", "httpcore"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


configure_dependency_logging()

__all__ = ["RequestLoggingMiddleware", "configure_dependency_logging"]
