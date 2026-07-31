variable "api_image" {
  description = "Overridden via TF_VAR_api_image after each manual build/push (az acr build); until CI automates this, the default here is the source of truth for 'what's actually live' so a plain `terraform apply` can't silently roll the deployment back to an older image."
  type        = string
  default     = "acrfifa26dev6q3jm1.azurecr.io/fifa26-api:v2"
}

# Azure Monitor's free monthly data ingestion allowance (5GB) comfortably covers a
# low-traffic portfolio project's logs/metrics.
resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${local.name_prefix}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "this" {
  name                = "appi-${local.name_prefix}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.this.id
}

resource "azurerm_user_assigned_identity" "container_apps" {
  name                = "id-${local.name_prefix}-apps"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
}

resource "azurerm_role_assignment" "container_apps_kv_reader" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.container_apps.principal_id
}

# Consumption plan: scales to zero when idle, billed on the always-free monthly grant
# (180K vCPU-seconds / 360K GiB-seconds / 2M requests) for low-traffic use.
resource "azurerm_container_app_environment" "this" {
  name                       = "cae-${local.name_prefix}"
  resource_group_name        = azurerm_resource_group.this.name
  location                   = azurerm_resource_group.this.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
}

resource "azurerm_container_app" "api" {
  name                         = "ca-${local.name_prefix}-api"
  resource_group_name         = azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_apps.id]
  }

  # Credential-free pull: Container Apps authenticates to ACR using the same managed
  # identity already granted the "AcrPull" role (infra/container_registry.tf), rather
  # than a stored username/password. Only needed for *private* registries -- the
  # placeholder mcr.microsoft.com image (var.api_image's default) is public and pulls
  # fine regardless of this block, so this is safe to apply before a real image
  # exists in this registry.
  registry {
    server   = azurerm_container_registry.this.login_server
    identity = azurerm_user_assigned_identity.container_apps.id
  }

  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.postgres_url.id
    identity            = azurerm_user_assigned_identity.container_apps.id
  }

  secret {
    name                = "groq-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.groq_api_key.id
    identity            = azurerm_user_assigned_identity.container_apps.id
  }

  template {
    min_replicas = 0
    max_replicas = 2

    container {
      name   = "api"
      image  = var.api_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "GROQ_API_KEY"
        secret_name = "groq-api-key"
      }
      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.this.connection_string
      }
      env {
        # The deployed frontend (Blob Storage static site) and this API are on
        # different hostnames, so browser requests from one to the other are
        # cross-origin -- FastAPI's CORSMiddleware only allows origins in this list.
        # `trimsuffix` strips the trailing slash Azure's endpoint URL includes, since
        # a browser's `Origin` header never has one (exact string match, no path).
        # localhost:3000 stays too, for testing `npm run dev` against this live API.
        name = "CORS_ORIGINS"
        value = jsonencode([
          trimsuffix(azurerm_storage_account.this.primary_web_endpoint, "/"),
          "http://localhost:3000",
        ])
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

# Self-hosted Grafana (instead of paid Azure Managed Grafana). Scales to zero when
# not actively being viewed -- wake it up before a demo. Uses the same free grant as
# the API app; persisted dashboards are provisioned from infra/grafana/ via its own
# image build rather than relying on a paid persistent-disk add-on.
resource "azurerm_container_app" "grafana" {
  name                         = "ca-${local.name_prefix}-grafana"
  resource_group_name         = azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "grafana"
      image  = "grafana/grafana-oss:11.3.0"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "GF_AUTH_ANONYMOUS_ENABLED"
        value = "false"
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 3000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

output "api_fqdn" {
  # `latest_revision_fqdn` (the resource's top-level attribute) is scoped to a specific
  # revision and only resolves if that revision has an explicit traffic label assigned
  # -- this stack doesn't use per-revision labels, so hitting that hostname returns
  # Azure's generic "This Container App is stopped or does not exist" page even though
  # the app is running fine. `ingress[0].fqdn` is the stable, app-level hostname that
  # always routes to whichever revision currently holds 100% traffic -- the one to
  # actually use. Found this the hard way verifying the real image was live.
  value = azurerm_container_app.api.ingress[0].fqdn
}

output "grafana_fqdn" {
  value = azurerm_container_app.grafana.ingress[0].fqdn
}
