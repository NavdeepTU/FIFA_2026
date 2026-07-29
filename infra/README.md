# Infra (Terraform, azurerm)

Provisions the minimal-cost Azure stack: resource group, Postgres Flexible Server (B1MS,
free-tier eligible), Blob Storage (data lake + static frontend hosting, no CDN), Key Vault,
Container Apps Environment (API + self-hosted Grafana, consumption plan / always-free grant),
and a Budget + cost alert.

Terraform itself is **not** installed locally (kept off this machine to save disk space) —
`terraform init/plan/apply` run either from GitHub Actions, or manually on a machine/Cloud
Shell that has it, per the plan's cost/storage constraints.

## One-time bootstrap (do this via Azure Cloud Shell — no local install needed)

1. `az login` and `az account set --subscription <sub-id>`.
2. Create a resource group + storage account for Terraform remote state (so your laptop and
   CI share the same state):
   ```
   az group create -n rg-fifa-tfstate -l eastus
   az storage account create -n fifatfstate<yourunique> -g rg-fifa-tfstate -l eastus --sku Standard_LRS
   az storage container create -n tfstate --account-name fifatfstate<yourunique>
   ```
3. Uncomment the `backend "azurerm" {}` block in `versions.tf` with those exact names.
4. Set up a GitHub Actions OIDC federated credential (no long-lived secret) so CI can run
   `terraform apply` — see `.github/workflows/deploy.yml`.

## Running a plan/apply

```
terraform init
terraform plan  -var-file=terraform.tfvars   # copy from terraform.tfvars.example first
terraform apply -var-file=terraform.tfvars
```

Required sensitive vars (set as env vars, not in the tfvars file, so they never touch disk):
```
export TF_VAR_postgres_admin_password="..."
export TF_VAR_groq_api_key="..."
```

## Cost notes

Every resource here is sized to stay inside Azure's free allowances (see the comments in each
`.tf` file for the specific limits). The budget alert in `budget.tf` fires at 50/80/100% of
`monthly_budget_usd` (default $10) regardless — treat that as the real backstop, not the SKU
choices alone. `terraform destroy` tears everything down if you want to pause spend entirely
between working sessions.
