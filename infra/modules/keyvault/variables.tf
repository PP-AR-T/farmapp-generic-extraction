variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "key_vault_name" {
  type = string
}

variable "tenant_id" {
  type = string
}

variable "admin_principal_id" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
