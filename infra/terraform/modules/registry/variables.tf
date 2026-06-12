variable "environment" { type = string }
variable "name" { type = string }
variable "immutable_tags" { type = bool }
variable "vulnerability_scanning" { type = bool }
variable "retention_days" {
  type = number
  validation {
    condition     = var.retention_days >= 7
    error_message = "Registry retention must be at least 7 days."
  }
}
