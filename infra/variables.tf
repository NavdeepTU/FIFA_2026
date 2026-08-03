variable "project" {
  description = "Short name used as a prefix for all resource names."
  type        = string
  default     = "fifa26"
}

variable "location" {
  description = "Azure region. Pick one close to you with Flexible Server + Container Apps support."
  type        = string
  default     = "eastus"
}

variable "postgres_location" {
  description = "Region for Postgres Flexible Server specifically -- separate from `location` because Azure restricts brand-new subscriptions from provisioning Postgres Flexible Server in some high-demand regions (eastus included, error LocationIsOfferRestricted). Everything else stays in `location`; only the database moves if it hits this."
  type        = string
  default     = "eastus2"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "postgres_admin_username" {
  type    = string
  default = "fifaadmin"
}

variable "postgres_admin_password" {
  description = "Set via TF_VAR_postgres_admin_password env var or a .tfvars file that is gitignored. Never commit this."
  type        = string
  sensitive   = true
}

variable "grafana_admin_password" {
  description = "Set via TF_VAR_grafana_admin_password (openssl rand, same pattern as postgres_admin_password). Grafana's Container App has no persistent disk, so leaving this at the default admin/admin and 'changing it' via the UI would be silently lost on every scale-to-zero cycle -- setting it via env var/Key Vault is the only setting that actually sticks."
  type        = string
  sensitive   = true
}

variable "groq_api_key" {
  description = "Stored in Key Vault, not in state-visible plain resources where avoidable. Set via TF_VAR_groq_api_key."
  type        = string
  sensitive   = true
  default     = ""
}

variable "sentry_dsn_backend" {
  description = "Backend (Python/FastAPI) Sentry project's DSN. Not marked sensitive: a DSN is meant to be embeddable/public (it's a write-only ingest endpoint, not a credential -- the same value ends up baked directly into the frontend's public JS bundle for the Next.js project), unlike groq_api_key or the Postgres password above. Set via TF_VAR_sentry_dsn_backend."
  type        = string
  default     = ""
}

variable "key_vault_admin_object_id" {
  description = "Azure AD object ID of the human Key Vault administrator (the user, via `az ad signed-in-user show`). Hardcoded rather than `data.azurerm_client_config.current.object_id` deliberately: that data source resolves to whoever is currently *running* terraform, which now includes the GitHub Actions CI identity for automated deploys (see `github_actions_sp_object_id` in container_registry.tf) -- if the admin grant tracked \"current\" instead of a stable value, a CI-run apply would try to replace the grant (revoking human access) rather than just adding the CI identity's own, separate grant alongside it."
  type        = string
  default     = "f6b8d8f3-4665-40d8-93be-654412397ee7"
}

variable "alert_email" {
  description = "Where budget-threshold alert emails go."
  type        = string
}

variable "dev_ip_address" {
  description = "Your current public IP, so the ETL/local backend can reach Postgres directly. Find it with `curl -s ifconfig.me`."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Total monthly Azure spend cap for alerting. Actual resources are sized to stay well under this."
  type        = number
  default     = 10
}
