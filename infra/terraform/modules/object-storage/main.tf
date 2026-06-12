resource "terraform_data" "bucket" {
  input = {
    resource_type            = "s3-compatible-bucket"
    environment              = var.environment
    bucket_name              = var.bucket_name
    versioning_enabled       = var.versioning_enabled
    object_lock_enabled      = var.object_lock_enabled
    retention_days           = var.retention_days
    server_side_encryption   = var.server_side_encryption
    public_access_blocked    = true
    deployment_prefix        = var.deployment_prefix
    backup_prefix            = var.backup_prefix
  }
}
