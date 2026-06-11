# Observability Baseline

This directory contains example configuration for the platform observability stack:

- `prometheus.yml`: scrape config for API, workers, provisioner, RabbitMQ, PostgreSQL exporter and cert-manager.
- `platform-alerts.yml`: baseline Prometheus alert rules.
- `loki-config.yml`: minimal Loki config for application logs.
- `promtail-config.yml`: Kubernetes log collection with JSON parsing.
- `otel-collector.yml`: OTLP receiver with trace, metric and log pipelines.
- `grafana-dashboard-platform.json`: starter dashboard for platform technical and business metrics.

These files are examples and should be deployed through Helm/Kustomize with production storage, authentication and retention settings.
