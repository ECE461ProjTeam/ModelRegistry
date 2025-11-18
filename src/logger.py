"""Logger configuration module for the ECE461 project."""
import logging
import os
import sys


def get_logger(name: str = "team4hope") -> logging.Logger:
    """Configure and return a logger that respects env variables."""
    logger = logging.getLogger(name)

    if logger.hasHandlers():
        logger.handlers.clear()

    log_level_env = int(os.getenv("LOG_LEVEL", "0"))
    log_file = os.getenv("LOG_FILE")

    try:
        level = int(log_level_env)
    except ValueError:
        level = logging.WARNING

    if level <= 0:
        logger.setLevel(logging.CRITICAL + 1)
    elif level == 1:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Console handler
    if level > 0:
        ch = logging.StreamHandler()
        ch.setLevel(logger.level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    # File handler - only write to existing files
    if log_file and level > 0 and os.path.exists(log_file):
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logger.level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger
