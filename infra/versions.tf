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
  # what's deployed. Create this storage account/container manually once (az cli),
  # then uncomment. Left commented so a first `terraform init` doesn't fail before
  # that bootstrap step exists.
  # backend "azurerm" {
  #   resource_group_name  = "rg-fifa-tfstate"
  #   storage_account_name = "fifatfstate<unique>"
  #   container_name       = "tfstate"
  #   key                  = "fifa.tfstate"
  # }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = true
      recover_soft_deleted_key_vaults = true
    }
  }
}
