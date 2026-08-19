import logging
from logging.handlers import RotatingFileHandler

from app.config import WorkerSettings


def configure_logging(settings: WorkerSettings) -> None:
    settings.log_directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    file_handler = RotatingFileHandler(
        settings.log_directory / "worker.log",
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler],
        force=True,
    )
