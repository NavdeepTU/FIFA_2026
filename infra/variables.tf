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

variable "groq_api_key" {
  description = "Stored in Key Vault, not in state-visible plain resources where avoidable. Set via TF_VAR_groq_api_key."
  type        = string
  sensitive   = true
  default     = ""
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
