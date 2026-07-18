"""Logging setup shared by every entry point.

Diagnostics go through `logging` (rich console handler + rotating file);
Yuna's actual dialogue output stays as plain prints in the chat UIs —
that's presentation, not logging.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_CONSOLE_FORMAT = "%(message)s"
_FILE_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(verbosity: int = 0, log_dir: Path | None = None) -> None:
    """Configure the root 'yuna' logger.

    verbosity: 0 = INFO console, 1+ = DEBUG console. File log is always DEBUG.
    """
    logger = logging.getLogger("yuna")
    if logger.handlers:  # already configured (e.g. tests calling twice)
        return
    logger.setLevel(logging.DEBUG)

    level = logging.DEBUG if verbosity > 0 else logging.INFO
    try:
        from rich.logging import RichHandler

        console = RichHandler(show_time=False, show_path=verbosity > 0, markup=False)
        console.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
    except ImportError:
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)-7s %(name)s: %(message)s"))
    console.setLevel(level)
    logger.addHandler(console)

    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_dir / "yuna.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(logging.Formatter(_FILE_FORMAT))
            file_handler.setLevel(logging.DEBUG)
            logger.addHandler(file_handler)
        except OSError as e:  # unwritable log dir must never kill a pipeline
            logger.warning("File logging disabled: %s", e)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"yuna.{name}")
