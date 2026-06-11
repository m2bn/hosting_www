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
            "correlation_id",
            "request_id",
            "operation",
            "organization_public_id",
            "project_public_id",
            "environment_public_id",
            "build_job_public_id",
            "deployment_public_id",
            "attempt",
            "status",
            "error_code",
        ]:
            value = getattr(record, key, None)
            if value not in [None, ""]:
                payload[key] = value
        return json.dumps(payload, sort_keys=True)

