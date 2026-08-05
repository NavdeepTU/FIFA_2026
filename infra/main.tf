locals {
  name_prefix = "${var.project}-${var.environment}"
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name_prefix}"
  location = var.location
}

data "azurerm_client_config" "current" {}

# Read-only, not Contributor: virtually every resource in this stack references
# `azurerm_resource_group.this.name`, so even a `-target`-scoped CI apply (see
# github_actions_container_app_contributor in container_apps.tf) needs to read this
# one resource to refresh state -- discovered from a real AuthorizationFailed on
# `Microsoft.Resources/subscriptions/resourceGroups/read` in CI's first live run,
# not assumed upfront. Reader can't write or delete anything; CI's actual write
# access stays scoped to the specific child resources granted elsewhere (the API
# container app, the Key Vault secrets it references).
resource "azurerm_role_assignment" "github_actions_rg_reader" {
  scope                = azurerm_resource_group.this.id
  role_definition_name = "Reader"
  principal_id         = var.github_actions_sp_object_id
}
