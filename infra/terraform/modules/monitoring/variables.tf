variable "environment" { type = string }
variable "prometheus_enabled" { type = bool }
variable "grafana_enabled" { type = bool }
variable "loki_enabled" { type = bool }
variable "retention_days" {
  type = number
  validation {
    condition     = var.retention_days >= 7
    error_message = "Monitoring retention must be at least 7 days."
  }
}
variable "alert_email" { type = string }
