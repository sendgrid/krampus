provider "aws" {
  region = "us-east-1"
}

module "iam" {
  source = "./modules/iam"
  bucket_name = "${module.s3.bucket_name}"
}

module "s3" {
  source = "./modules/s3"
}

module "lambda" {
  source = "./modules/lambda"
  action_role = "${module.iam.krampus_action_role}"
  krampus_bucket = "${module.s3.bucket_name}"
}

variable "krampus_environment_variables" {
  type = "map"

  default = {
    some_env_var = "hello"
  }
}
