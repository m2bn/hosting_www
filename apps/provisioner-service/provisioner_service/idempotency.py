from dataclasses import dataclass
from threading import Lock


@dataclass
class IdempotencyRecord:
    key: str
    status: str
    result: dict | None = None


class InMemoryIdempotencyStore:
    """Local store for tests/dev. Production should use DB or Redis with TTL/locking."""

    def __init__(self):
        self._records = {}
        self._lock = Lock()

    def begin(self, key):
        with self._lock:
            record = self._records.get(key)
            if record and record.status == "succeeded":
                return record, False
            record = record or IdempotencyRecord(key=key, status="running")
            record.status = "running"
            self._records[key] = record
            return record, True

    def complete(self, key, result):
        with self._lock:
            record = self._records.setdefault(key, IdempotencyRecord(key=key, status="running"))
            record.status = "succeeded"
            record.result = result
            return record

    def fail(self, key, result):
        with self._lock:
            record = self._records.setdefault(key, IdempotencyRecord(key=key, status="running"))
            record.status = "failed"
            record.result = result
            return record

    def clear(self):
        with self._lock:
            self._records.clear()


store = InMemoryIdempotencyStore()

