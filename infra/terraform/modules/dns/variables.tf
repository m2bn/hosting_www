variable "environment" { type = string }
variable "dns_zone" { type = string }
variable "records" {
  type = list(object({
    name  = string
    type  = string
    value = string
    ttl   = number
  }))
  default = []
}
