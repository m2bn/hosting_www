resource "terraform_data" "monitoring" {
  input = {
    resource_type       = "monitoring-stack"
    environment         = var.environment
    prometheus_enabled  = var.prometheus_enabled
    grafana_enabled     = var.grafana_enabled
    loki_enabled        = var.loki_enabled
    retention_days      = var.retention_days
    alert_email         = var.alert_email
    traces_enabled      = true
    metrics_enabled     = true
    logs_enabled        = true
  }
}
