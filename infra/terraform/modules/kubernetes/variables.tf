variable "environment" { type = string }
variable "name_prefix" { type = string }
variable "region" { type = string }
variable "network_cidr" { type = string }
variable "version" { type = string }
variable "node_pools" {
  type = map(object({
    instance_type = string
    min_size      = number
    max_size      = number
    desired_size  = number
  }))
  validation {
    condition = alltrue([
      for pool in values(var.node_pools) : pool.min_size <= pool.desired_size && pool.desired_size <= pool.max_size
    ])
    error_message = "Each node pool must satisfy min_size <= desired_size <= max_size."
  }
}
variable "private_endpoint" { type = bool }
variable "audit_logs_enabled" { type = bool }
