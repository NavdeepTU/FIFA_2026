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

# Same grant, separate identity -- Grafana's custom image (infra/grafana/) also lives
# in this registry now, not just the stock public Docker Hub image it started with.
resource "azurerm_role_assignment" "grafana_acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.grafana.principal_id
}

variable "github_actions_sp_object_id" {
  description = <<-EOT
    Object ID of the service principal behind the "gh-actions-fifa26-deploy" Azure AD
    app registration used for GitHub Actions OIDC (federated credential, no stored
    secret). The app registration and federated credential themselves are bootstrapped
    once via `az ad app create` / `az ad app federated-credential create` -- like the
    Terraform state storage account in infra/README.md, this is one-time identity
    setup, not something that changes often enough to justify pulling in the azuread
    Terraform provider just for it. The RBAC grant below stays in Terraform, though,
    consistent with every other role assignment in this stack.
  EOT
  type        = string
  default     = "28cbf846-e09a-40df-98b4-55808f17ccc5"
}

# Least-privilege grant so CI can push new images without being able to pull/delete
# others' or touch anything else in the resource group -- distinct from the Container
# App's AcrPull role above, which is read-only in the opposite direction.
resource "azurerm_role_assignment" "github_actions_acr_push" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPush"
  principal_id         = var.github_actions_sp_object_id
}

# `az acr build` runs as an ACR Tasks "quick run" under the hood, which needs several
# control-plane actions beyond simple push/pull: reading the registry resource,
# scheduling the task run, and generating a SAS URL to upload the build context
# (Microsoft.ContainerRegistry/registries/{read,scheduleRun,listBuildSourceUploadUrl}
# /action, discovered one at a time from real AuthorizationFailed errors -- Reader
# alone covers only the first of these). Rather than keep hunting down individual
# actions, this uses Contributor -- Microsoft's own documented recommendation for
# running `az acr build` under RBAC -- scoped to only this one registry resource, not
# the resource group or subscription, so the blast radius stays contained to "manage
# this one registry," nothing else. Contributor's `actions` cover every control-plane
# operation on this resource but explicitly exclude `dataActions` (actually pushing
# image bytes), which is why AcrPush above still needs to exist alongside it -- two
# different axes of Azure RBAC (management-plane vs. data-plane), not overlapping.
resource "azurerm_role_assignment" "github_actions_acr_contributor" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "Contributor"
  principal_id         = var.github_actions_sp_object_id
}

output "acr_login_server" {
  value = azurerm_container_registry.this.login_server
}
