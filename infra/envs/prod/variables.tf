variable "project_name" {
  type    = string
  default = "apiextractor"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "location" {
  type    = string
  default = "eastus"
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
  type = map(string)
  default = {
    owner   = "data-platform"
    purpose = "generic-api-extraction"
  }
}
