# vars

variable "name" {
  default = "krampus"
}

variable "default_region" {
  default = "us-east=1"
}

variable "krampus_bucket" {
  default = "krampus"
}

variable "tasks_key" {
  default = "tasks.json"
}

variable "arn_whitelist_key" {
  default = "whitelist.json"
}

variable "hipchat_api_key" {
  default = ""
}

variable "hipchat_room" {
  default = 0
}

variable "action_role" { }

