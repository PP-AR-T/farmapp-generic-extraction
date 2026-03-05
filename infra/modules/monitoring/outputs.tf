output "application_insights_connection_string" {
  value = azurerm_application_insights.this.connection_string
}

output "application_insights_instrumentation_key" {
  value = azurerm_application_insights.this.instrumentation_key
}

output "application_insights_id" {
  value = azurerm_application_insights.this.id
}
