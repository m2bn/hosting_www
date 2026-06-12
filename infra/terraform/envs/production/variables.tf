variable "environment" { type = string }
variable "region" { type = string }
variable "name_prefix" { type = string }
variable "network_cidr" { type = string }
variable "dns_zone" { type = string }
variable "dns_records" {
  type = list(object({
    name  = string
    type  = string
    value = string
    ttl   = number
  }))
}
variable "database" {
  type = object({
    engine_version        = string
    instance_class        = string
    storage_gb            = number
    backup_retention_days = number
    high_availability     = bool
  })
}
variable "redis" {
  type = object({
    engine_version    = string
    instance_class    = string
    high_availability = bool
  })
}
variable "rabbitmq" {
  type = object({
    engine_version    = string
    instance_class    = string
    high_availability = bool
  })
}
variable "object_storage" {
  type = object({
    bucket_name            = string
    versioning_enabled     = bool
    object_lock_enabled    = bool
    retention_days         = number
    server_side_encryption = bool
    deployment_prefix      = string
    backup_prefix          = string
  })
}
variable "kubernetes" {
  type = object({
    version            = string
    node_pools         = map(object({
      instance_type = string
      min_size      = number
      max_size      = number
      desired_size  = number
    }))
    private_endpoint   = bool
    audit_logs_enabled = bool
  })
}
variable "registry" {
  type = object({
    name                   = string
    immutable_tags         = bool
    vulnerability_scanning = bool
    retention_days         = number
  })
}
variable "secrets" {
  type = object({
    provider_name            = string
    key_rotation_days        = number
    external_secrets_enabled = bool
  })
}
variable "monitoring" {
  type = object({
    prometheus_enabled = bool
    grafana_enabled    = bool
    loki_enabled       = bool
    retention_days     = number
    alert_email        = string
  })
}
