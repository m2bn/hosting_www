output "database" {
  value = module.database.summary
}

output "redis" {
  value = module.cache.summary
}

output "rabbitmq" {
  value = module.queue.summary
}

output "object_storage" {
  value = module.object_storage.summary
}

output "kubernetes" {
  value = module.kubernetes.summary
}

output "registry" {
  value = module.registry.summary
}

output "dns" {
  value = module.dns.summary
}

output "secrets" {
  value = module.secrets.summary
}

output "monitoring" {
  value = module.monitoring.summary
}
