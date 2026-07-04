"""Structured logging configuration."""

import logging
import sys
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
) -> logging.Logger:
    """Configure structured logging for the application.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to write log output in addition to stderr.

    Returns:
        The root application logger.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger("tg_admin_watch")
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("telethon").setLevel(logging.WARNING)

    return root_logger
