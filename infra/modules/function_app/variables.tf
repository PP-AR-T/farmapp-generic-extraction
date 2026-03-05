variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "function_app_name" {
  type = string
}

variable "service_plan_name" {
  type = string
}

variable "function_storage_account_name" {
  type = string
}

variable "function_storage_account_access_key" {
  type      = string
  sensitive = true
}

variable "adls_storage_account_id" {
  type = string
}

variable "adls_account_name" {
  type = string
}

variable "key_vault_id" {
  type = string
}

variable "key_vault_uri" {
  type = string
}

variable "application_insights_connection_string" {
  type = string
}

variable "application_insights_instrumentation_key" {
  type = string
}

variable "config_container" {
  type    = string
  default = "configs"
}

variable "state_container" {
  type    = string
  default = "state"
}

variable "default_job_name" {
  type    = string
  default = ""
}

variable "default_timer_schedule" {
  type    = string
  default = "0 0 * * * *"
}

variable "tags" {
  type    = map(string)
  default = {}
}
