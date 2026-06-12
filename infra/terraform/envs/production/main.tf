terraform {
  required_version = ">= 1.6.0"
}

module "platform" {
  source = "../../stacks/platform"

  environment    = var.environment
  region         = var.region
  name_prefix    = var.name_prefix
  network_cidr   = var.network_cidr
  dns_zone       = var.dns_zone
  dns_records    = var.dns_records
  database       = var.database
  redis          = var.redis
  rabbitmq       = var.rabbitmq
  object_storage = var.object_storage
  kubernetes     = var.kubernetes
  registry       = var.registry
  secrets        = var.secrets
  monitoring     = var.monitoring
}
