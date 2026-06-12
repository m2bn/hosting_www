resource "terraform_data" "zone" {
  input = {
    resource_type = "dns-zone"
    environment   = var.environment
    dns_zone      = var.dns_zone
  }
}

resource "terraform_data" "records" {
  for_each = { for record in var.records : "${record.name}-${record.type}" => record }

  input = {
    resource_type = "dns-record"
    environment   = var.environment
    zone          = var.dns_zone
    name          = each.value.name
    type          = each.value.type
    value         = each.value.value
    ttl           = each.value.ttl
  }
}
