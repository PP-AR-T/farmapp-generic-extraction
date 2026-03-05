output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "function_app_name" {
  value = module.function_app.function_app_name
}

output "storage_account_name" {
  value = module.storage.storage_account_name
}

output "key_vault_name" {
  value = module.keyvault.key_vault_name
}

output "application_insights_id" {
  value = module.monitoring.application_insights_id
}
