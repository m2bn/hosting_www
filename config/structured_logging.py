import json
import logging
from datetime import datetime, timezone

from config.request_id import request_id_var


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        request_id = getattr(record, "request_id", None) or request_id_var.get()
        if request_id:
            record.request_id = request_id
            record.correlation_id = getattr(record, "correlation_id", None) or request_id
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in [
            "request_id",
            "correlation_id",
            "operation",
            "organization_public_id",
            "project_public_id",
            "environment_public_id",
            "deployment_public_id",
            "build_job_public_id",
            "task_name",
            "webhook_provider",
            "status",
            "error_code",
        ]:
            value = getattr(record, key, None)
            if value not in [None, ""]:
                payload[key] = str(value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True)
