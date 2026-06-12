import importlib
import os
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase


class StagingEnvironmentTests(TestCase):
    def test_seed_staging_requires_staging_environment(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "STAGING_ALLOW_SEED": "true"}, clear=False):
            with self.assertRaises(CommandError):
                call_command("seed_staging")

    def test_seed_staging_requires_explicit_allow_flag(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}, clear=False):
            os.environ.pop("STAGING_ALLOW_SEED", None)
            with self.assertRaises(CommandError):
                call_command("seed_staging")

    def test_staging_settings_reject_live_stripe_key(self):
        with patch.dict(
            os.environ,
            {
                "DJANGO_SECRET_KEY": "test-secret",
                "DJANGO_ALLOWED_HOSTS": "api.staging.example.com",
                "STRIPE_TEST_MODE": "true",
                "STRIPE_SECRET_KEY": "sk_live_forbidden",
            },
            clear=False,
        ):
            with self.assertRaisesMessage(Exception, "Stripe live secret key"):
                import config.settings.staging as staging_settings

                importlib.reload(staging_settings)
