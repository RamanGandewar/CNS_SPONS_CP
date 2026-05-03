import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


class JsonLogFormatter(logging.Formatter):
    """Small structured logger without extra dependencies."""

    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": ANSI_ESCAPE_RE.sub("", record.getMessage()),
        }

        for field in (
            "request_id",
            "job_id",
            "user_id",
            "duration_ms",
            "verdict",
            "event",
            "role",
            "method",
            "path",
            "status_code",
            "ip",
            "query_string",
            "content_length",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging():
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def log_event(logger, level, message, **fields):
    logger.log(level, message, extra=fields)
