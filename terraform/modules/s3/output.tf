output "bucket_name" {
  value = "${aws_s3_bucket.krampus_bucket.arn}"
}
