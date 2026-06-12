# Staging Environment Configuration

This directory contains non-secret staging configuration examples.

- `namespace.yaml` creates the isolated staging namespace.
- `external-secrets.example.yaml` shows the External Secrets integration shape.
- `stripe-webhooks.example.json` documents Stripe test-mode webhook configuration.
- `e2e.env.example` defines the environment contract for dashboard e2e tests.

Do not commit real credentials, Stripe keys, webhook secrets, database URLs, kubeconfigs, or user passwords.
