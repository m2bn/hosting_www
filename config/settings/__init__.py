import os


settings_module = os.getenv("DJANGO_ENV", "development")

if settings_module == "production":
    from .production import *  # noqa: F403
elif settings_module == "test":
    from .test import *  # noqa: F403
else:
    from .development import *  # noqa: F403
