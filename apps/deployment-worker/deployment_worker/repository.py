from dataclasses import dataclass
from threading import Lock


@dataclass
class WorkerEvent:
    event_type: str
    payload: dict


class InMemoryDeploymentRepository:
    """Development/test repository. Production should call control plane API or outbox."""

    def __init__(self):
        self._lock = Lock()
        self.build_jobs = {}
        self.deployments = {}
        self.events = []

    def update_build_job(self, build_job_public_id, status, metadata=None):
        with self._lock:
            current = self.build_jobs.setdefault(build_job_public_id, {})
            current.update({"status": status, **(metadata or {})})
            return current

    def update_deployment(self, deployment_public_id, status, metadata=None):
        with self._lock:
            current = self.deployments.setdefault(deployment_public_id, {})
            current.update({"status": status, **(metadata or {})})
            return current

    def record_event(self, event_type, payload):
        with self._lock:
            self.events.append(WorkerEvent(event_type=event_type, payload=dict(payload)))

    def clear(self):
        with self._lock:
            self.build_jobs.clear()
            self.deployments.clear()
            self.events.clear()


repository = InMemoryDeploymentRepository()
