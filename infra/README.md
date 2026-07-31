# Infra (Terraform, azurerm)

Provisions the minimal-cost Azure stack: resource group, Postgres Flexible Server (B1MS,
free-tier eligible), Blob Storage (data lake + static frontend hosting, no CDN), Key Vault,
Container Apps Environment (API + self-hosted Grafana, consumption plan / always-free grant),
and a Budget + cost alert.

Local tooling (Azure CLI + Terraform, via `brew`/`hashicorp/tap`) is fine to install now —
the disk-space constraint that originally kept this Cloud-Shell-only has eased (see root
`CLAUDE.md`). `terraform init/plan/apply` run from a laptop today; automating them from
GitHub Actions is still a manual, deliberate step (see "Cost notes" and the CI/CD status
in `docs/project_status.md`).

## One-time bootstrap

These are one-off identity/state setup steps, done via `az cli` rather than Terraform
itself — deliberately, to avoid a chicken-and-egg problem (Terraform's own remote state
backend can't exist before *something* creates it) and, for the OIDC piece, to avoid
pulling in a whole extra Terraform provider (`azuread`) just for a setup that essentially
never changes once done.

1. `az login` and `az account set --subscription <sub-id>`.
2. Create a resource group + storage account for Terraform remote state (so your laptop and
   CI share the same state):
   ```
   az group create -n rg-fifa-tfstate -l eastus
   az storage account create -n fifatfstate<yourunique> -g rg-fifa-tfstate -l eastus --sku Standard_LRS
   az storage container create -n tfstate --account-name fifatfstate<yourunique>
   ```
3. Uncomment the `backend "azurerm" {}` block in `versions.tf` with those exact names.
4. **GitHub Actions OIDC** (so CI can build/push a Docker image without any stored Azure
   secret): create an Azure AD app registration + federated credential trusting this
   repo's `master` branch specifically, one-time:
   ```
   az ad app create --display-name "gh-actions-fifa26-deploy"
   az ad sp create --id <appId from above>
   az ad app federated-credential create --id <appId> --parameters '{
     "name": "github-actions-master-branch",
     "issuer": "https://token.actions.githubusercontent.com",
     "subject": "repo:<owner>/<repo>:ref:refs/heads/master",
     "audiences": ["api://AzureADTokenExchange"]
   }'
   ```
   **Real gotcha hit setting this up**: the plain `repo:<owner>/<repo>:ref:refs/heads/<branch>`
   subject above is what Microsoft's own docs show, but the actual token GitHub presented
   used a newer format with stable numeric IDs attached —
   `repo:<owner>@<owner_id>/<repo>@<repo_id>:ref:refs/heads/<branch>` (this exists so the
   trust relationship survives a repo/owner rename). The federated credential's `subject`
   must match the *exact* string GitHub sends, not the docs' example — if `azure/login`
   fails with `AADSTS700213: No matching federated identity record found`, the fix is to
   read the exact subject claim straight out of that failed run's own logs (`azure/login`
   prints it before the error) and update the federated credential to match verbatim,
   rather than guessing at the format.
   The resulting service principal's object ID (`az ad sp show --id <appId>`) is fed into
   Terraform as `github_actions_sp_object_id` (`container_registry.tf`), which grants it
   `AcrPush` **and** `Contributor`, both scoped to only this one registry resource — see
   the next gotcha for why it needs both, not just `AcrPush`.

   **Second real gotcha**: `AcrPush` alone isn't enough to run `az acr build`. Azure splits
   ACR permissions into two independent axes — *data-plane* (`AcrPush`/`AcrPull`: actually
   pushing/pulling image bytes) and *management-plane* (reading the registry resource
   itself via ARM, scheduling an ACR Tasks run, generating a SAS URL to upload the build
   context). `az acr build` needs both. Hunting the specific management-plane actions one
   `AuthorizationFailed` at a time (`registries/read`, then `registries/scheduleRun`, then
   `registries/listBuildSourceUploadUrl`, ...) doesn't converge — go straight to
   `Contributor` scoped to the one registry resource, Microsoft's own documented
   recommendation for `az acr build` under RBAC. It's still least-privilege in the sense
   that matters (contained to this one resource, and `Contributor`'s `actions` explicitly
   exclude `dataActions`, so it still can't push an image byte on its own — `AcrPush` does
   that half).

   Finally, add three **GitHub repository secrets** (Settings → Secrets and variables →
   Actions, "Secrets" tab) so the `build-push-image` job in `.github/workflows/ci.yml` can
   log in: `AZURE_CLIENT_ID` (the app's `appId`), `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
   No client secret is ever created or stored — the whole point of federated credentials.
   Also add one **repository *variable*** (same page, "Variables" tab — not a secret, it's
   a public URL): `NEXT_PUBLIC_API_URL` set to the real deployed API's URL. The frontend CI
   job needs it too, for an unrelated reason: `next build` in static-export mode
   (`frontend/next.config.ts`) pre-renders every player/team page at build time, which
   means it needs a real, reachable backend right then, not just the `localhost:8000`
   fallback in `lib/api.ts`.

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
