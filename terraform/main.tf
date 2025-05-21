
terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

provider "azurerm" {
  features {}
}

variable "prefix" { type = string }
variable "location" { type = string default = "eastus" }

resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-rg"
  location = var.location
}

resource "azurerm_search_service" "search" {
  name                = "${var.prefix}search"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
  sku                 = "basic"
  replica_count       = 1
  partition_count     = 1
}

resource "azurerm_cognitive_account" "openai" {
  name                = "${var.prefix}openai"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
  kind                = "OpenAI"
  sku_name            = "S0"
}

resource "azurerm_storage_account" "sa" {
  name                     = "${var.prefix}sa"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  is_hns_enabled           = true
}

resource "azurerm_purview_account" "purview" {
  name                = "${var.prefix}purview"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  sku_name            = "Standard"
}

# Note: Azure AI Foundry currently provisioned via portal; create resource placeholder
resource "azurerm_ai_foundry_workspace" "foundry" {
  name                = "${var.prefix}-foundry"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
}

output "search_endpoint" {
  value = azurerm_search_service.search.primary_endpoint
}
