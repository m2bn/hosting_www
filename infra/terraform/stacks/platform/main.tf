module "database" {
  source = "../../modules/database"

  environment           = var.environment
  name_prefix           = var.name_prefix
  engine_version        = var.database.engine_version
  instance_class        = var.database.instance_class
  storage_gb            = var.database.storage_gb
  backup_retention_days = var.database.backup_retention_days
  high_availability     = var.database.high_availability
}

module "cache" {
  source = "../../modules/cache"

  environment       = var.environment
  name_prefix       = var.name_prefix
  engine_version    = var.redis.engine_version
  instance_class    = var.redis.instance_class
  high_availability = var.redis.high_availability
}

module "queue" {
  source = "../../modules/queue"

  environment       = var.environment
  name_prefix       = var.name_prefix
  engine_version    = var.rabbitmq.engine_version
  instance_class    = var.rabbitmq.instance_class
  high_availability = var.rabbitmq.high_availability
}

module "object_storage" {
  source = "../../modules/object-storage"

  environment            = var.environment
  bucket_name            = var.object_storage.bucket_name
  versioning_enabled     = var.object_storage.versioning_enabled
  object_lock_enabled    = var.object_storage.object_lock_enabled
  retention_days         = var.object_storage.retention_days
  server_side_encryption = var.object_storage.server_side_encryption
  deployment_prefix      = var.object_storage.deployment_prefix
  backup_prefix          = var.object_storage.backup_prefix
}

module "kubernetes" {
  source = "../../modules/kubernetes"

  environment          = var.environment
  name_prefix          = var.name_prefix
  region               = var.region
  network_cidr         = var.network_cidr
  version              = var.kubernetes.version
  node_pools           = var.kubernetes.node_pools
  private_endpoint     = var.kubernetes.private_endpoint
  audit_logs_enabled   = var.kubernetes.audit_logs_enabled
}

module "registry" {
  source = "../../modules/registry"

  environment            = var.environment
  name                   = var.registry.name
  immutable_tags         = var.registry.immutable_tags
  vulnerability_scanning = var.registry.vulnerability_scanning
  retention_days         = var.registry.retention_days
}

module "dns" {
  source = "../../modules/dns"

  environment = var.environment
  dns_zone    = var.dns_zone
  records     = var.dns_records
}

module "secrets" {
  source = "../../modules/secrets"

  environment              = var.environment
  provider_name            = var.secrets.provider_name
  key_rotation_days        = var.secrets.key_rotation_days
  external_secrets_enabled = var.secrets.external_secrets_enabled
}

module "monitoring" {
  source = "../../modules/monitoring"

  environment        = var.environment
  prometheus_enabled = var.monitoring.prometheus_enabled
  grafana_enabled    = var.monitoring.grafana_enabled
  loki_enabled       = var.monitoring.loki_enabled
  retention_days     = var.monitoring.retention_days
  alert_email        = var.monitoring.alert_email
}
