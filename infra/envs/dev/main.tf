terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.1"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}
}

data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

locals {
  common_tags = merge(var.tags, {
    environment = var.environment
    workload    = var.project_name
  })

  storage_account_name = substr(regexreplace("st${var.project_name}${var.environment}${random_string.suffix.result}", "[^a-z0-9]", ""), 0, 24)
  key_vault_name       = substr(regexreplace("kv-${var.project_name}-${var.environment}-${random_string.suffix.result}", "[^a-zA-Z0-9-]", ""), 0, 24)
  function_app_name    = substr(regexreplace("func-${var.project_name}-${var.environment}-${random_string.suffix.result}", "[^a-zA-Z0-9-]", ""), 0, 60)
  service_plan_name    = substr(regexreplace("asp-${var.project_name}-${var.environment}-${random_string.suffix.result}", "[^a-zA-Z0-9-]", ""), 0, 40)
  appinsights_name     = substr(regexreplace("appi-${var.project_name}-${var.environment}-${random_string.suffix.result}", "[^a-zA-Z0-9-]", ""), 0, 60)
  log_workspace_name   = substr(regexreplace("log-${var.project_name}-${var.environment}-${random_string.suffix.result}", "[^a-zA-Z0-9-]", ""), 0, 63)
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${var.project_name}-${var.environment}"
  location = var.location
  tags     = local.common_tags
}

module "storage" {
  source               = "../../modules/storage"
  resource_group_name  = azurerm_resource_group.this.name
  location             = azurerm_resource_group.this.location
  storage_account_name = local.storage_account_name
  containers           = ["bronze", "configs", "state"]
  tags                 = local.common_tags
}

module "monitoring" {
  source                       = "../../modules/monitoring"
  resource_group_name          = azurerm_resource_group.this.name
  location                     = azurerm_resource_group.this.location
  application_insights_name    = local.appinsights_name
  log_analytics_workspace_name = local.log_workspace_name
  tags                         = local.common_tags
}

module "keyvault" {
  source              = "../../modules/keyvault"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  key_vault_name      = local.key_vault_name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  admin_principal_id  = data.azurerm_client_config.current.object_id
  tags                = local.common_tags
}

module "function_app" {
  source                                    = "../../modules/function_app"
  resource_group_name                       = azurerm_resource_group.this.name
  location                                  = azurerm_resource_group.this.location
  function_app_name                         = local.function_app_name
  service_plan_name                         = local.service_plan_name
  function_storage_account_name             = module.storage.storage_account_name
  function_storage_account_access_key       = module.storage.primary_access_key
  adls_storage_account_id                   = module.storage.storage_account_id
  adls_account_name                         = module.storage.storage_account_name
  key_vault_id                              = module.keyvault.key_vault_id
  key_vault_uri                             = module.keyvault.key_vault_uri
  application_insights_connection_string    = module.monitoring.application_insights_connection_string
  application_insights_instrumentation_key  = module.monitoring.application_insights_instrumentation_key
  config_container                          = "configs"
  state_container                           = "state"
  default_job_name                          = var.default_job_name
  default_timer_schedule                    = var.default_timer_schedule
  tags                                      = local.common_tags
}
