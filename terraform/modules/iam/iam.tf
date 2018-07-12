# setup the lambda trust relationship and an empty role
resource "aws_iam_role" "krampus" {
  name = "${var.role_name}"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
}

# permissions krampus needs to do his job
resource "aws_iam_policy" "krampus_action_policy" {
  name = "${var.action_policy_name}"
  policy = <<EOF
{
  "Version":"2012-10-17",
  "Statement":[
    {
      "Action":[
        "ec2:StopInstances",
        "ec2:StartInstances",
        "ec2:TerminateInstances",
        "ec2:DescribeInstances",
        "ec2:DeleteSecurityGroup",
        "ec2:DescribeSecurityGroups",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupEgress",
        "ec2:DescribeVolumes",
        "ec2:DetachVolume",
        "ec2:DeleteVolume",
        "s3:GetBucketAcl",
        "s3:PutBucketAcl",
        "rds:StopDBInstance",
        "rds:ModifyDBInstance",
        "iam:GetUser",
        "iam:ListUserPolicies",
        "iam:ListAttachedUserPolicies",
        "iam:ListGroupsForUser",
        "iam:RemoveUserFromGroup",
        "iam:ListAccessKeys",
        "iam:DeleteAccessKey",
        "iam:ListSigningCertificates",
        "iam:DeleteUser",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:DeleteRolePolicy",
        "iam:DetachRolePolicy",
        "iam:ListGroupPolicies",
        "iam:ListAttachedGroupPolicies",
        "iam:ListInstanceProfilesForRole",
        "iam:RemoveRoleFromInstanceProfile",
        "iam:DeleteGroupPolicy",
        "iam:DetachGroupPolicy",
        "iam:DetachUserPolicy",
        "iam:DeleteGroup",
        "iam:GetGroup",
        "iam:DeleteRole",
        "lambda:DeleteFunction"
      ],
      "Effect":"Allow",
      "Resource":"*"
    }
  ]
}
EOF
}

# krampus needs to be able to access its own state bucket
resource "aws_iam_policy" "krampus_s3_bucket_policy" {
  name = "${var.s3_access_policy_name}"
  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": [
        "${var.bucket_name}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": [
        "${var.bucket_name}"
      ]
    }
  ]
}
EOF
}

# do the attachments
resource "aws_iam_policy_attachment" "action_perms" {
  name       = "attach_action_perms"
  roles      = ["${aws_iam_role.krampus.name}"]
  policy_arn = "${aws_iam_policy.krampus_action_policy.arn}"
}

resource "aws_iam_policy_attachment" "bucket_perms" {
  name       = "attach_bucket_perms"
  roles      = ["${aws_iam_role.krampus.name}"]
  policy_arn = "${aws_iam_policy.krampus_s3_bucket_policy.arn}"
}
