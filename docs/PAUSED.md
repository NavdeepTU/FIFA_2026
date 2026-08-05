# Project paused (indefinite)

Paused: 2026-08-05. `terraform destroy` was run against `infra/` and the entire
`rg-fifa26-dev` resource group was deleted — Postgres, both Container Apps, the
Container Registry, Storage account, Key Vault, Log Analytics, Application Insights,
budget alert, all managed identities and role assignments. **Azure spend for this
project is $0** as of this pause.

What's still there and why:
- `rg-fifa-tfstate` (a separate resource group holding Terraform's remote state
  storage account) — untouched, costs effectively nothing (a few KB of blob storage),
  and needs to exist so `terraform apply` below can find its bearings.
- The GitHub Actions OIDC app registration + federated credential (`gh-actions-fifa26-deploy`)
  — a one-time, out-of-band `az ad` setup, not managed by Terraform, not touched by the
  destroy. CI can still authenticate once resumed without redoing `infra/README.md`'s
  bootstrap steps.
- Everything needed to rebuild is already in the repo: Terraform config (`infra/*.tf`),
  ETL scripts (`etl/`), and trained ML models (`backend/ml/artifacts/*.joblib`, checked
  into git — no retraining needed).

## What was NOT preserved (rebuilds from scratch on resume)

- **Postgres data** — the database itself was destroyed. Reload it from the local CSV
  (see step 3 below). Make sure `data/raw/fifa_world_cup_2026_player_performance.csv`
  is still present on this machine before resuming — it's gitignored, never pushed.
- **Docker images in ACR** — the registry itself was destroyed, so both the API and
  Grafana images need rebuilding and pushing again.
- **Blob storage contents** — the raw/curated data lake containers and the deployed
  frontend static site are gone; the frontend needs rebuilding and re-uploading.
- **Key Vault secrets** — recreated automatically by `terraform apply` from the same
  `terraform.tfvars` / `.env.secrets` values, nothing to redo by hand.

## Resume checklist

Run from `infra/` unless noted otherwise.

1. **Recreate the infrastructure**
   ```
   source .env.secrets
   terraform init          # re-links to the still-existing rg-fifa-tfstate backend
   terraform apply -var-file=terraform.tfvars
   ```
   This recreates all 37 resources — Postgres, Container Apps, ACR, Storage, Key Vault,
   monitoring, budget alert, and all the RBAC role assignments (including the ones CI
   needs) — from the same config as before the pause.

2. **Rebuild and push the Docker images**
   ```
   az acr build --registry <new acr name from terraform output acr_login_server> \
     --resource-group rg-fifa26-dev --image fifa26-api:v7 \
     --file backend/Dockerfile backend
   ```
   Same for the Grafana custom image (`infra/grafana/Dockerfile`). Then update
   `var.api_image` / `var.grafana_image` defaults in `infra/container_apps.tf` (or pass
   `-var`) to point at the new tag, and re-apply — same pattern as every manual deploy
   this project did before CI/CD automation existed.

3. **Reload the database**
   ```
   cd ../etl
   DATABASE_URL=<from terraform output postgres_fqdn, built into the Key Vault secret>
   python load.py ../data/raw/fifa_world_cup_2026_player_performance.csv
   ```

4. **Rebuild and redeploy the frontend**
   ```
   cd ../frontend
   npm ci && npm run build
   az storage blob upload-batch -d '$web' -s out \
     --account-name <new storage account name from terraform output>
   ```

5. **Sanity check**
   - Hit the API's `/health` and `/health/ready`.
   - Load the frontend static site URL (`terraform output frontend_static_site_url`),
     confirm real data renders.
   - Confirm Grafana dashboards load and Sentry is still reporting (DSNs/keys carry
     over unchanged via `terraform.tfvars`/`.env.secrets`, nothing to reconfigure there).

6. Update `docs/project_status.md`'s "Last updated" line to note the resume, and delete
   this file (`docs/PAUSED.md`) once back up and verified.
