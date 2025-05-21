
terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "azurerm" {
  features {}
}

variable "prefix" { type = string }
variable "location" { type = string default = "eastus" }

resource "random_string" "sa_suffix" {
  length  = 13
  upper   = false
  special = false
}

locals {
  sa_prefix = substr(lower(var.prefix), 0, 9)
  lower_prefix = lower(var.prefix)
}

resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-rg"
  location = var.location
}

resource "azurerm_search_service" "search" {
  name                = "${local.lower_prefix}search"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
  sku                 = "basic"
  replica_count       = 1
  partition_count     = 1
}

resource "azurerm_cognitive_account" "openai" {
  name                = "${local.lower_prefix}openai"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
  kind                = "OpenAI"
  sku_name            = "S0"
}

resource "azurerm_storage_account" "sa" {
  name                     = "${local.sa_prefix}sa${random_string.sa_suffix.result}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  is_hns_enabled           = true
}

# Note: Azure AI Foundry currently provisioned via portal; create resource placeholder
resource "azurerm_ai_foundry_workspace" "foundry" {
  name                = "${local.lower_prefix}-foundry"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
}

output "search_endpoint" {
  value = azurerm_search_service.search.primary_endpoint
}
