# B1MS burstable is the SKU eligible for Azure's 12-months-free allowance (750 hrs/month,
# 32GB storage) -- running one instance continuously stays inside that free amount.
resource "azurerm_postgresql_flexible_server" "this" {
  # "-eus2" suffix: a first attempt at this name failed in eastus (LocationIsOfferRestricted)
  # and Azure held onto the name in ARM's naming cache even though the resource itself
  # doesn't exist (confirmed via `az postgres flexible-server show` -> ResourceNotFound) --
  # rather than wait an unknown amount of time for that reservation to clear, use a
  # distinct name for the retry in postgres_location.
  name                = "psql-${local.name_prefix}-${random_string.suffix.result}-eus2"
  resource_group_name = azurerm_resource_group.this.name
  # Deliberately not azurerm_resource_group.this.location -- see var.postgres_location.
  location = var.postgres_location

  sku_name = "B_Standard_B1ms"
  version  = "16"
  storage_mb = 32768

  administrator_login    = var.postgres_admin_username
  administrator_password = var.postgres_admin_password

  backup_retention_days        = 7
  geo_redundant_backup_enabled = false

  # Public access is simplest/cheapest for a portfolio project (no VNet/NAT gateway
  # costs). Locked down to Azure services + your own IP below rather than the world.
  public_network_access_enabled = true

  lifecycle {
    ignore_changes = [zone]
  }
}

# 0.0.0.0/0.0.0.0 is an Azure-specific convention meaning "allow other Azure resources
# (Container Apps)" -- it is NOT open to the public internet, despite how it looks.
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.this.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# For running the ETL / local dev backend directly against this instance from your
# laptop. Set TF_VAR_dev_ip_address to your current public IP; leave unset to skip.
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_dev_ip" {
  count            = var.dev_ip_address != "" ? 1 : 0
  name             = "allow-dev-ip"
  server_id        = azurerm_postgresql_flexible_server.this.id
  start_ip_address = var.dev_ip_address
  end_ip_address   = var.dev_ip_address
}

resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "VECTOR"
}

resource "azurerm_postgresql_flexible_server_database" "fifa" {
  name      = "fifa"
  server_id = azurerm_postgresql_flexible_server.this.id
  collation = "en_US.utf8"
  charset   = "utf8"
}

output "postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.this.fqdn
}
