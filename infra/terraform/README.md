# Terraform infrastructure

This directory contains a provider-agnostic Terraform baseline for the SaaS hosting platform.

The current implementation is intentionally a scaffold. It defines environments, module boundaries, inputs, outputs, and security expectations without selecting a cloud provider. Replace the placeholder `terraform_data` resources in `modules/*` with cloud-specific resources when the provider is chosen.

## Layout

- `envs/staging` - staging environment entrypoint.
- `envs/production` - production environment entrypoint.
- `stacks/platform` - shared platform stack composed from modules.
- `modules/database` - PostgreSQL contract.
- `modules/cache` - Redis contract.
- `modules/queue` - RabbitMQ contract.
- `modules/object-storage` - S3-compatible bucket/storage contract.
- `modules/kubernetes` - Kubernetes cluster contract.
- `modules/registry` - private container registry contract.
- `modules/dns` - DNS zone and records contract.
- `modules/secrets` - external secrets manager integration contract.
- `modules/monitoring` - monitoring stack contract.

## Usage

1. Choose a remote state backend and copy `backend.tf.example` to `backend.tf` in the target environment.
2. Copy `terraform.tfvars.example` to a secure local or CI-managed tfvars file.
3. Fill only non-secret configuration in tfvars. Pass secrets through CI secrets or an external secrets manager.
4. Run:

```bash
cd infra/terraform/envs/staging
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

For production, repeat the same process in `envs/production` and require peer review for the plan.

## Security Notes

- Do not commit real secrets, credentials, database passwords, kubeconfigs, or private keys.
- Use encrypted remote state with locking.
- Restrict state access by least privilege.
- Treat Terraform outputs as sensitive unless explicitly proven otherwise.
- Production applies must run from CI with protected branches and approval gates.
