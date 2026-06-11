import logging
import re


SECRET_PATTERNS = [
    re.compile(r"(?i)(password|token|secret|api[_-]?key|authorization|recovery[_-]?code|totp)(=|:)\s*[^,\s]+"),
]


class RedactSecretsFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        for pattern in SECRET_PATTERNS:
            message = pattern.sub(r"\1\2 [REDACTED]", message)
        record.msg = message
        record.args = ()
        return True
