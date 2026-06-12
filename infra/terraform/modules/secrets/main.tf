resource "terraform_data" "secrets_manager" {
  input = {
    resource_type             = "secrets-manager-integration"
    environment               = var.environment
    provider_name             = var.provider_name
    key_rotation_days         = var.key_rotation_days
    external_secrets_enabled  = var.external_secrets_enabled
    encryption_at_rest        = true
    audit_logging             = true
  }
}
