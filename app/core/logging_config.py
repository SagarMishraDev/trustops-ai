"""Logging configuration.

WHAT: One place that sets up application logging.
WHY:  Print/console debugging does not scale. Logs must never contain
      passwords, API keys or full sensitive conversation content.
HOW:  Standard logging with a readable format, level from settings.
"""
import logging
import sys


def setup_logging(debug: bool = False) -> logging.Logger:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    return logging.getLogger("trustops")
