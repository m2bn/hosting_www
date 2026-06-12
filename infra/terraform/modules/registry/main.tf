resource "terraform_data" "registry" {
  input = {
    resource_type           = "container-registry"
    environment             = var.environment
    name                    = var.name
    immutable_tags          = var.immutable_tags
    vulnerability_scanning  = var.vulnerability_scanning
    retention_days          = var.retention_days
    encryption_at_rest      = true
    public_access           = false
  }
}
