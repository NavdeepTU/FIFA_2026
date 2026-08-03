# Standard tier is pay-per-operation and effectively $0 at dev-project volume.
resource "azurerm_key_vault" "this" {
  name                = "kv-${var.project}-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  rbac_authorization_enabled = true
}

resource "azurerm_role_assignment" "deployer_kv_admin" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.key_vault_admin_object_id
}

# Separate, additive grant for the CI identity -- deliberately not folded into
# deployer_kv_admin above (see that variable's description for why "current
# identity" and "the CI identity" must be two independent, stable grants, not
# one that silently reassigns depending on who's running terraform). Needed
# because the API container app's env vars reference two Key Vault secrets
# (database-url, groq-api-key) -- even a `-target`-scoped apply that only
# touches the container app still pulls those secret resources into its
# dependency closure, and reading/reconciling them needs this.
resource "azurerm_role_assignment" "github_actions_kv_secrets_officer" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.github_actions_sp_object_id
}

resource "azurerm_key_vault_secret" "postgres_url" {
  name         = "database-url"
  key_vault_id = azurerm_key_vault.this.id
  value        = "postgresql://${var.postgres_admin_username}:${var.postgres_admin_password}@${azurerm_postgresql_flexible_server.this.fqdn}:5432/fifa?sslmode=require"

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "groq_api_key" {
  name         = "groq-api-key"
  key_vault_id = azurerm_key_vault.this.id
  value        = var.groq_api_key != "" ? var.groq_api_key : "unset"

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "grafana_admin_password" {
  name         = "grafana-admin-password"
  key_vault_id = azurerm_key_vault.this.id
  value        = var.grafana_admin_password

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}
