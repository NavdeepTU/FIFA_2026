variable "api_image" {
  description = "Set by CI after each build/push. Placeholder here so the first apply succeeds before any image exists."
  type        = string
  default     = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
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
  value = azurerm_container_app.api.latest_revision_fqdn
}

output "grafana_fqdn" {
  value = azurerm_container_app.grafana.latest_revision_fqdn
}
