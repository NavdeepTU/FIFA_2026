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
  principal_id         = data.azurerm_client_config.current.object_id
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
