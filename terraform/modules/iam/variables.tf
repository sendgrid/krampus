# vars

variable "role_name" {
  default = "krampus"
}

variable "action_policy_name" {
  default = "krampus_action_policy"
}

variable "s3_access_policy_name" {
  default = "krampus_s3_bucket_policy"
}

variable "bucket_name" { }
