resource "azurerm_service_plan" "this" {
  name                = var.service_plan_name
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"
  sku_name            = "Y1"

  tags = var.tags
}

resource "azurerm_linux_function_app" "this" {
  name                       = var.function_app_name
  location                   = var.location
  resource_group_name        = var.resource_group_name
  service_plan_id            = azurerm_service_plan.this.id
  storage_account_name       = var.function_storage_account_name
  storage_account_access_key = var.function_storage_account_access_key
  functions_extension_version = "~4"
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }

    ftps_state = "Disabled"
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME              = "python"
    WEBSITE_RUN_FROM_PACKAGE              = "1"
    APPINSIGHTS_INSTRUMENTATIONKEY        = var.application_insights_instrumentation_key
    APPLICATIONINSIGHTS_CONNECTION_STRING = var.application_insights_connection_string
    ADLS_ACCOUNT_NAME                     = var.adls_account_name
    KEY_VAULT_URI                         = var.key_vault_uri
    CONFIG_CONTAINER                      = var.config_container
    STATE_CONTAINER                       = var.state_container
    DEFAULT_JOB_NAME                      = var.default_job_name
    DEFAULT_TIMER_SCHEDULE                = var.default_timer_schedule
  }

  tags = var.tags
}

resource "azurerm_role_assignment" "storage_blob_data_contributor" {
  scope                = var.adls_storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_function_app.this.identity[0].principal_id
}

resource "azurerm_role_assignment" "keyvault_secrets_user" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_function_app.this.identity[0].principal_id
}
