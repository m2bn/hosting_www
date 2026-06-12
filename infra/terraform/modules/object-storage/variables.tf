variable "environment" { type = string }
variable "bucket_name" { type = string }
variable "versioning_enabled" { type = bool }
variable "object_lock_enabled" { type = bool }
variable "retention_days" {
  type = number
  validation {
    condition     = var.retention_days >= 7
    error_message = "Object storage retention must be at least 7 days."
  }
}
variable "server_side_encryption" { type = bool }
variable "deployment_prefix" { type = string }
variable "backup_prefix" { type = string }
