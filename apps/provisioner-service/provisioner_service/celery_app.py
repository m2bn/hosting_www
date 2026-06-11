from provisioner_service.config import settings


try:
    from celery import Celery
except ImportError:  # pragma: no cover - fallback for minimal local test environments
    Celery = None


if Celery:
    celery_app = Celery(
        "provisioner_service",
        broker=settings.broker_url,
        backend=settings.result_backend,
    )
    celery_app.conf.task_serializer = "json"
    celery_app.conf.result_serializer = "json"
    celery_app.conf.accept_content = ["json"]
else:
    class _InlineTask:
        def __init__(self, func):
            self.func = func
            self.__name__ = getattr(func, "__name__", "inline_task")

        def __call__(self, *args, **kwargs):
            return self.func(None, *args, **kwargs)

        def run(self, *args, **kwargs):
            return self.func(None, *args, **kwargs)

    class _InlineCelery:
        def task(self, *task_args, **task_kwargs):
            def decorator(func):
                return _InlineTask(func)
            return decorator

    celery_app = _InlineCelery()

