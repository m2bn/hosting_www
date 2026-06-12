variable "environment" { type = string }
variable "name_prefix" { type = string }
variable "engine_version" { type = string }
variable "instance_class" { type = string }
variable "storage_gb" {
  type = number
  validation {
    condition     = var.storage_gb >= 20
    error_message = "PostgreSQL storage must be at least 20 GB."
  }
}
variable "backup_retention_days" {
  type = number
  validation {
    condition     = var.backup_retention_days >= 7
    error_message = "PostgreSQL backup retention must be at least 7 days."
  }
}
variable "high_availability" { type = bool }
