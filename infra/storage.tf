# Blob Storage: raw/curated data lake layers + static website hosting for the built
# Next.js export. Standard LRS is the cheapest redundancy tier; usage here (a ~17MB
# CSV + a small static site) stays well inside the 5GB/month free allowance.
resource "azurerm_storage_account" "this" {
  name                     = "st${var.project}${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.this.name
  location                 = azurerm_resource_group.this.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  static_website {
    index_document     = "index.html"
    error_404_document = "404.html"
  }
}

resource "azurerm_storage_container" "raw" {
  name                  = "raw"
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "curated" {
  name                  = "curated"
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "model_artifacts" {
  name                  = "model-artifacts"
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

output "frontend_static_site_url" {
  value = azurerm_storage_account.this.primary_web_endpoint
}

# "Reader and Data Access", not plain Reader: the API container app's CORS_ORIGINS
# env var (container_apps.tf) references azurerm_storage_account.this.primary_web_endpoint
# -- the azurerm provider's storage account read populates that (and other computed
# attributes) via a listKeys call under the hood, which plain Reader doesn't grant
# (listKeys is gated separately since it can return real account keys, even though
# this specific attribute doesn't need one). Discovered from a second real
# AuthorizationFailed in CI, same pattern as github_actions_rg_reader above --
# scoped to just this one storage account, not the resource group.
resource "azurerm_role_assignment" "github_actions_storage_reader" {
  scope                = azurerm_storage_account.this.id
  role_definition_name = "Reader and Data Access"
  principal_id         = var.github_actions_sp_object_id
}
