terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # State is kept remote so GitHub Actions and your machine share the same view of
  # what's deployed. Bootstrapped once via az cli (resource group + storage account +
  # container) -- see infra/README.md.
  backend "azurerm" {
    resource_group_name  = "rg-fifa-tfstate"
    storage_account_name = "fifatfstatend26"
    container_name       = "tfstate"
    key                  = "fifa.tfstate"
    # Authenticates with the caller's own Azure AD identity (via `az login` locally,
    # or ARM_USE_OIDC + the federated credential in CI) instead of a storage account
    # access key -- keeps this consistent with "no long-lived Azure secrets" the rest
    # of this project's auth already follows. Needs the caller to hold a data-plane
    # role (Storage Blob Data Contributor) on the state storage account specifically
    # -- granted once via `az role assignment create`, documented in infra/README.md,
    # not via Terraform itself (this backend block has to already be authenticated
    # before any Terraform-managed resource, including a role assignment, can apply).
    use_azuread_auth = true
  }
}

provider "azurerm" {
  # By default the provider tries to auto-register every Azure resource provider it
  # supports (~200 of them), not just the ones this config uses -- on a brand-new
  # subscription one of those unrelated registrations (Microsoft.DataMigration, which
  # this project never touches) hung for hours waiting on a slow ARM response. The
  # providers this project actually needs (Storage, DBforPostgreSQL, KeyVault, App,
  # OperationalInsights, ContainerRegistry, Consumption) were already registered
  # manually via `az provider register`, so skip Terraform's auto-registration.
  resource_provider_registrations = "none"

  features {
    key_vault {
      purge_soft_delete_on_destroy    = true
      recover_soft_deleted_key_vaults = true
    }
  }
}
