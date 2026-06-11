import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in [
            "request_id",
            "correlation_id",
            "job_id",
            "idempotency_key",
            "operation",
            "organization_public_id",
            "project_public_id",
            "environment_public_id",
            "domain_public_id",
            "attempt",
            "status",
            "error_code",
        ]:
            value = getattr(record, key, None)
            if value not in [None, ""]:
                payload[key] = value
        return json.dumps(payload, sort_keys=True)


def configure_logging(level=logging.INFO):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

