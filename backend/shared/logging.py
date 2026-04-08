"""Shared JSON log formatter for all ddstore microservices."""
import json
import logging
import os
from datetime import datetime, timezone

# Keys that belong to the LogRecord itself — everything else is treated as
# a structured attribute and promoted to the top level of the JSON output.
_BUILTIN_ATTRS = frozenset({
    "name", "msg", "args", "created", "relativeCreated", "exc_info",
    "exc_text", "stack_info", "lineno", "funcName", "pathname", "filename",
    "module", "thread", "threadName", "process", "processName", "levelname",
    "levelno", "message", "msecs", "taskName",
})


class JSONFormatter(logging.Formatter):
    """Produces one valid JSON object per log line, compatible with Datadog log intake.

    Any extra kwargs passed via logger.info("msg", extra={...}) are promoted
    to top-level keys in the JSON output, making them searchable as Datadog
    log attributes.
    """

    def format(self, record):
        trace_id = getattr(record, "dd.trace_id", "0")
        span_id = getattr(record, "dd.span_id", "0")

        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "dd": {
                "trace_id": str(trace_id),
                "span_id": str(span_id),
            },
        }

        # Promote any extra keys to top-level attributes
        for key, val in record.__dict__.items():
            if key not in _BUILTIN_ATTRS and not key.startswith("_") and key not in ("dd.trace_id", "dd.span_id"):
                log_entry[key] = val

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["error"] = {
                "kind": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "stack": self.formatException(record.exc_info),
            }

        return json.dumps(log_entry, default=str)


def setup_logging(service_name):
    """Configure root logger with JSON formatting to stdout + file.

    Returns the service-specific logger.
    """
    formatter = JSONFormatter()

    # Stdout handler
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(formatter)

    # File handler
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)
    file_handler = logging.FileHandler(os.path.join(log_dir, f"{service_name}.log"))
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(stdout_handler)
    root.addHandler(file_handler)

    # Suppress noisy werkzeug request logs (we log requests ourselves)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    return logging.getLogger(f"ddstore.{service_name}")
