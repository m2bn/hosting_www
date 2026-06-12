variable "environment" { type = string }
variable "provider_name" { type = string }
variable "key_rotation_days" {
  type = number
  validation {
    condition     = var.key_rotation_days <= 180
    error_message = "Secrets key rotation must be at most 180 days."
  }
}
variable "external_secrets_enabled" { type = bool }
