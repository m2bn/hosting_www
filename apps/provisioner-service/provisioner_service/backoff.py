import random

from provisioner_service.config import settings


def retry_countdown(attempt, *, jitter=True):
    exponent = max(attempt - 1, 0)
    countdown = min(settings.retry_base_seconds * (2**exponent), settings.retry_max_seconds)
    if jitter:
        countdown = int(countdown * random.uniform(0.8, 1.2))
    return max(countdown, 1)

