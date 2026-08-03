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

5. **Automated backend deploy** (`.github/workflows/ci.yml`'s `terraform-apply` job): after
   `build-push-image` pushes a new image, this job deploys it to the live Container App —
   but gated behind a required manual approval (a GitHub Environment named `production`
   with a required reviewer), not fully automatic. Same reused OIDC identity as the build
   job above; it just needs more permissions, granted via Terraform itself (see
   `github_actions_container_app_contributor` in `container_apps.tf` and
   `github_actions_kv_secrets_officer` in `keyvault.tf`) plus one thing that can't live in
   Terraform (chicken-and-egg: the state backend needs auth before any Terraform-managed
   resource can apply):
   ```
   az role assignment create --assignee <github_actions app's object id> \
     --role "Storage Blob Data Contributor" \
     --scope "$(az storage account show -n <tfstate storage account> -g rg-fifa-tfstate --query id -o tsv)"
   ```
   (Grant the same role to your own account's object ID too — `versions.tf`'s backend
   block switched from a storage account key to `use_azuread_auth = true`, Azure AD-based
   auth for *both* local and CI applies, consistent with this project's "no long-lived
   Azure secrets" pattern elsewhere. `az ad signed-in-user show` / `az ad sp show` gets
   either identity's object ID.)

   **Deliberately scoped to `-target=azurerm_container_app.api`, not a full apply** — see
   the comment on `github_actions_container_app_contributor` for the concrete reason:
   `terraform.tfvars` (with this laptop's real dev IP, for
   `azurerm_postgresql_flexible_server_firewall_rule.allow_dev_ip`) is gitignored and never
   reaches CI. An untargeted apply in CI would resolve `TF_VAR_dev_ip_address` to its empty
   default and delete that firewall rule — a real, verified-before-shipping risk, not a
   hypothetical one. `-target` is HashiCorp's own documented "exceptional situations only,"
   not a routine pattern — the trade-off here is deliberate: CI's job is narrowly "deploy
   the backend image," not "reconcile the whole stack." A genuine full-stack config change
   (new resources, SKU changes, etc.) still goes through a manual `terraform apply` from a
   more-privileged local session, same as always.

   **Same "current identity" trap almost bit twice**: `deployer_kv_admin`
   (`keyvault.tf`) originally granted Key Vault Secrets Officer to
   `data.azurerm_client_config.current.object_id` — "whoever's running terraform right
   now." Once CI started running `terraform apply` too, that data source would resolve
   to the CI identity instead of the human administrator depending on who applied last,
   and Terraform would try to *replace* the grant (revoking human access) rather than add
   a second one. Fixed by hardcoding the human's object ID into a real variable
   (`key_vault_admin_object_id`) instead of tracking "current," and adding the CI
   identity's own grant as a separate, additive resource
   (`github_actions_kv_secrets_officer`) — verified via a real `terraform plan` showing
   zero changes to the existing grant after the fix, confirming it resolved to the exact
   same value as before.

   Add three more **environment-scoped GitHub secrets** (Settings → Environments →
   `production` → Secrets), not repository-wide ones — extra protection since these are
   real credentials, distinct from the plain repository secrets above: `TF_POSTGRES_ADMIN_PASSWORD`,
   `TF_GROQ_API_KEY`, `TF_GRAFANA_ADMIN_PASSWORD` (same real values as
   `infra/.env.secrets`). One more repository **variable** (not scoped to the environment,
   not sensitive — same reasoning as `NEXT_PUBLIC_SENTRY_DSN`): `TF_VAR_SENTRY_DSN_BACKEND`.

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
