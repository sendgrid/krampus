resource "aws_s3_bucket" "krampus_bucket" {
  bucket = "${var.krampus_bucket}"
  acl    = "private"
  tags   = {}

  lifecycle_rule {
    id      = "log_cleaning"
    enabled = true
    prefix  = "krampus_log"

    expiration {
      days = 60
    }
  }
}
