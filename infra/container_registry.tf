# Basic SKU: no free tier exists for ACR (unlike Postgres/Container Apps/Storage
# elsewhere in this stack) -- flat ~$5/month for having the registry provisioned at
# all, independent of image count, up to the 10GiB storage it includes. Confirmed
# with the user before provisioning given the real ongoing cost. Standard/Premium add
# geo-replication and private networking this single low-traffic app doesn't need.
resource "azurerm_container_registry" "this" {
  name                = "acr${replace(local.name_prefix, "-", "")}${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = "Basic"
  admin_enabled       = false
}

# Lets the Container App environment pull images using its existing managed identity
# instead of a stored username/password -- no registry credential exists anywhere in
# Terraform state or Key Vault to leak. The AcrPull role is the least-privilege grant
# for "pull images," distinct from AcrPush (used by whatever builds/pushes images).
resource "azurerm_role_assignment" "container_apps_acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.container_apps.principal_id
}

output "acr_login_server" {
  value = azurerm_container_registry.this.login_server
}
