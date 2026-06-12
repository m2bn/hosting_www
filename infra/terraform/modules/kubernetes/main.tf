resource "terraform_data" "cluster" {
  input = {
    resource_type          = "kubernetes-cluster"
    environment            = var.environment
    name                   = "${var.name_prefix}-${var.environment}-cluster"
    region                 = var.region
    network_cidr           = var.network_cidr
    version                = var.version
    node_pools             = var.node_pools
    private_endpoint       = var.private_endpoint
    audit_logs_enabled     = var.audit_logs_enabled
    pod_security_standard  = "restricted"
    network_policies       = true
    secrets_encryption     = true
  }
}
