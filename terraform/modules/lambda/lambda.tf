resource "aws_lambda_function" "krampus" {
  filename         = "../krampus.zip"
  function_name    = "krampus"
  role             = "${var.action_role}"
  handler          = "krampus.main"
  source_code_hash = "${base64sha256(file("../krampus.zip"))}"
  runtime          = "python2.7"
  timeout          = 300

  tags { }

  environment {
    variables = {
      DEFAULT_REGION = "${var.default_region}"
      KRAMPUS_BUCKET = "${var.krampus_bucket}"
      KRAMPUS_ROLE_NAME = "${var.action_role}"
      TASKS_FILE_KEY = "${var.tasks_key}"
      ARN_WHITELIST = "${var.arn_whitelist_key}"
      HIPCHAT_ACCESS_TOKEN = "${var.hipchat_api_key}"
      HIPCHAT_ROOM = "hipchat_room"
    }
  }
}

