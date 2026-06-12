variable "environment" {
  description = "Environment name, for example staging or production."
  type        = string
}

variable "region" {
  description = "Primary deployment region."
  type        = string
}

variable "name_prefix" {
  description = "Prefix used for platform infrastructure resources."
  type        = string
}

variable "network_cidr" {
  description = "Provider-specific network CIDR placeholder."
  type        = string
}

variable "dns_zone" {
  description = "Public DNS zone for platform records."
  type        = string
}

variable "dns_records" {
  description = "DNS records managed for the platform."
  type = list(object({
    name  = string
    type  = string
    value = string
    ttl   = number
  }))
  default = []
}

variable "database" {
  description = "PostgreSQL configuration."
  type = object({
    engine_version        = string
    instance_class        = string
    storage_gb            = number
    backup_retention_days = number
    high_availability     = bool
  })
}

variable "redis" {
  description = "Redis configuration."
  type = object({
    engine_version    = string
    instance_class    = string
    high_availability = bool
  })
}

variable "rabbitmq" {
  description = "RabbitMQ configuration."
  type = object({
    engine_version    = string
    instance_class    = string
    high_availability = bool
  })
}

variable "object_storage" {
  description = "S3-compatible storage configuration."
  type = object({
    bucket_name              = string
    versioning_enabled       = bool
    object_lock_enabled      = bool
    retention_days           = number
    server_side_encryption   = bool
    deployment_prefix        = string
    backup_prefix            = string
  })
}

variable "kubernetes" {
  description = "Kubernetes cluster configuration."
  type = object({
    version             = string
    node_pools          = map(object({
      instance_type = string
      min_size      = number
      max_size      = number
      desired_size  = number
    }))
    private_endpoint    = bool
    audit_logs_enabled  = bool
  })
}

variable "registry" {
  description = "Private container registry configuration."
  type = object({
    name                     = string
    immutable_tags           = bool
    vulnerability_scanning   = bool
    retention_days           = number
  })
}

variable "secrets" {
  description = "Secrets management integration configuration."
  type = object({
    provider_name             = string
    key_rotation_days         = number
    external_secrets_enabled  = bool
  })
}

variable "monitoring" {
  description = "Monitoring stack configuration."
  type = object({
    prometheus_enabled = bool
    grafana_enabled    = bool
    loki_enabled       = bool
    retention_days     = number
    alert_email        = string
  })
}
