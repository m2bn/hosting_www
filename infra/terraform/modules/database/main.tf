resource "terraform_data" "postgresql" {
  input = {
    resource_type          = "postgresql"
    environment            = var.environment
    name                   = "${var.name_prefix}-${var.environment}-postgresql"
    engine_version         = var.engine_version
    instance_class         = var.instance_class
    storage_gb             = var.storage_gb
    backup_retention_days  = var.backup_retention_days
    high_availability      = var.high_availability
    encryption_at_rest     = true
    public_access          = false
    deletion_protection    = var.environment == "production"
  }
}
