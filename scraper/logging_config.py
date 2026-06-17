import logging
import sys
from pythonjsonlogger import json as jsonlogger

# Field rename map: native name -> desired name in JSON output
_RENAME = {
    "levelname": "level",
    "asctime": "timestamp",
    "message": "event",
}


class _RenamedJsonFormatter(jsonlogger.JsonFormatter):
    """JsonFormatter that renames levelname→level, asctime→timestamp, message→event."""

    def process_log_record(self, log_record: dict) -> dict:
        for old, new in _RENAME.items():
            if old in log_record:
                log_record[new] = log_record.pop(old)
        return log_record


def _make_json_formatter() -> _RenamedJsonFormatter:
    return _RenamedJsonFormatter(fmt="%(asctime)s %(levelname)s %(message)s")


def setup_logging(name: str = "scraper") -> logging.Logger:
    # Always configure the root "scraper" logger with the JSON handler.
    # Child loggers (e.g. "scraper.batch") inherit the handler via propagation
    # and must NOT add their own handler to avoid duplicate log lines.
    root_scraper = logging.getLogger("scraper")
    if not any(isinstance(h, logging.StreamHandler) and isinstance(h.formatter, _RenamedJsonFormatter) for h in root_scraper.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_make_json_formatter())
        root_scraper.addHandler(handler)
        root_scraper.setLevel(logging.INFO)

    logger = logging.getLogger(name)
    if name != "scraper":
        # Child loggers propagate to the root scraper logger; no extra handler needed.
        logger.setLevel(logging.INFO)
        logger.propagate = True
    return logger
