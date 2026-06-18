# scraper/tests/test_logging.py
import json
import logging
import io


def _make_stream_logger(name):
    from scraper.logging_config import _make_json_formatter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(_make_json_formatter())
    log = logging.getLogger(name)
    log.handlers = []
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    return log, stream


def test_info_emits_json_with_level_event_timestamp():
    log, stream = _make_stream_logger("scraper.t1")
    log.info("scrape_complete", extra={"chars": 1420})
    record = json.loads(stream.getvalue().strip())
    assert record["level"] == "INFO"
    assert record["event"] == "scrape_complete"
    assert record["chars"] == 1420
    assert "timestamp" in record


def test_warning_level_field():
    log, stream = _make_stream_logger("scraper.t2")
    log.warning("duplicate_blocked", extra={"text_hash": "abc"})
    record = json.loads(stream.getvalue().strip())
    assert record["level"] == "WARNING"


def test_error_level_field():
    log, stream = _make_stream_logger("scraper.t3")
    log.error("scrape_failed", extra={"error": "timeout"})
    record = json.loads(stream.getvalue().strip())
    assert record["level"] == "ERROR"
    assert record["error"] == "timeout"
