resource "terraform_data" "rabbitmq" {
  input = {
    resource_type          = "rabbitmq"
    environment            = var.environment
    name                   = "${var.name_prefix}-${var.environment}-rabbitmq"
    engine_version         = var.engine_version
    instance_class         = var.instance_class
    high_availability      = var.high_availability
    encryption_at_rest     = true
    encryption_in_transit  = true
    public_access          = false
  }
}
