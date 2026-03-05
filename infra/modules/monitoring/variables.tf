variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "application_insights_name" {
  type = string
}

variable "log_analytics_workspace_name" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
