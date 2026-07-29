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
