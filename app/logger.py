"""
Structured logging for TDM.
Provides a consistent logger with configurable level and format.
"""

import logging
import sys
from app.config import get_log_config


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module).
    """
    config = get_log_config()
    level = getattr(logging, config["level"].upper(), logging.INFO)

    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if config["format"] == "json":
        formatter = logging.Formatter(
            '{"time": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}'
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

    return logger
