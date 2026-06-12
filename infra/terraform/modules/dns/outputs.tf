output "summary" {
  value = {
    zone    = terraform_data.zone.output
    records = [for record in terraform_data.records : record.output]
  }
}
