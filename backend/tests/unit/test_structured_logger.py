import io
import json
import logging

from backend.core.logging import JSONFormatter, setup_logging


def test_json_formatter_outputs_valid_json() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter(environment="test"))

    logger = logging.getLogger("test_json_logger")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("test_event", extra={"context": {"key": "value"}})

    output = stream.getvalue().strip().splitlines()[-1]
    data = json.loads(output)

    assert data["message"] == "test_event"
    assert data["context"]["key"] == "value"
    assert data["environment"] == "test"


def test_setup_logging_configures_logger() -> None:
    logger = setup_logging(environment="test", level="INFO", logger_name="rag_test")
    assert logger.handlers
