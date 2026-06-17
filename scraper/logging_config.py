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
    logger = logging.getLogger(name)
    if any(isinstance(h, logging.StreamHandler) and isinstance(h.formatter, _RenamedJsonFormatter) for h in logger.handlers):
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_make_json_formatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
