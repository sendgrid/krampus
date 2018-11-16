## What is Krampus
![krampus](/docs/Krampus-logo.png)
Krampus is a security solution designed to delete and disable various AWS objects such as EC2 instances, S3 buckets, etc. It accepts a simple list of objects to action in the form of a JSON tasks file, and can be also be used as a cost-control tool. Krampus itself is designed to eliminate threats post by security issues, and does not actually decide whether something is insecure. For that we recommend [Netflix's Security Monkey](https://github.com/Netflix/security_monkey).

![krampus overview](/docs/BAD_CONFIG.gif)

![krampus flowchart](/docs/krampus.png)

## How to Krampus
Setting up Krampus is generally pretty simple and should only take a few minutes. It can be run locally from the command line or from Lambda in AWS. The process involves setting up the correct IAM permissions for Krampus to run, and using a method of your choice to populate an S3 bucket with a JSON tasks file that Krampus can understand (we like [Security Monkey](https://github.com/Netflix/security_monkey)). The flow chart below demonstrates how we have chosen to set this up, though any method that generates a tasks file Krampus can understand should be fine.

### IAM setup
Krampus works by assuming a role in the target AWS account with the appropriate permissions for completing the various kill and disable tasks it supports. This is done via STS, with the temporary credentials stored in memory for use during runtime. The first thing that needs to be done is setting up the role. Every account--including the home account--that Krampus is expected to work with must have this role. Begin the role creation process from the IAM console.

At this point you have a choice to make. If Krampus is to be run from Lambda, then at the first screen choose "AWS service" as the type of trusted entity, then select “Lambda” from the list of options. Don't select any permissions; simply go to the next screen and name the role. In the list of roles, select the new Krampus role and and add an inline policy. Paste in the following policy document. The name does not matter, so do whatever makes the most sense to you.
```javascript
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
```
Alternatively, if you plan to run Krampus from a local machine, you will need to add an IAM user and generate access keys, and in the role creation process will want to select "Another AWS account" as the type of trusted entity. For the account number, enter the current account number. Krampus assumes into its role even in the home account for the sake of simplicity. If you go this route, make sure to allow the user to assume the role you created for Krampus by attaching the following inline policy. The name can be whatever you think works best.
```javascript
{
  "Version": "2012-10-17",
  "Statement": {
    "Effect": "Allow",
    "Action": "sts:AssumeRole",
    "Resource": "arn:aws:iam::*:role/krampus"
  }
}
```
Your role should now be ready. At this point it is a good idea to verify that the trust relationship for the role has been set up correctly. It should look like one the following policies. By default the relationship will probably be user/your_iam_user if setup through the web UI; change this to the krampus user if the script won’t run from Lambda.
```javascript
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:user/<user>"
      },
      "Action": "sts:AssumeRole",
      "Condition": {}
    }
  ]
}
// or for lambda
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
```
In any additional accounts, the trust relationship will be slightly different. This is because the trust will be between the krampus role in the home account and the role in the target account, rather than the Lambda service. In any accounts that Krampus will monitor, make sure the trust relationship on the target account looks something like this:
```javascript
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:sts::ACCOUNT_ID:assumed-role/krampus/krampus"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```
Krampus will need permission to access its own S3 bucket for collecting tasks and writing logs. Add the following inline policy to the krampus role in order to accomplish that. Be sure to replace "krampus" with the appropriate bucket name if necessary. Again, the policy name does not really matter here. If you choose to set up a Krampus user, this policy could be attached to that instead.
```javascript
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::krampus"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::krampus/*"
      ]
    }
  ]
}
```
### Installation and virtual environment setup
In order to run Krampus, you will need a 2.7.x version of Python. Other versions in the 2.x series may work, but have not been tested. Virtualenv is not required, but definitely recommended.

First, clone the Krampus code from the repo.
```
git clone https://github.com/sendgrid/krampus
cd krampus/
```
Regardless of how you plan to run Krampus, there are some dependencies that need to be resolved first. To do this, we will use virtualenv. First, create the environment.
```
virtualenv venv
```
Now, source the environment.
```
source venv/bin/activate
```
At this point you should be ready to install the dependencies with pip.
```
pip install -r requirements.txt
```
### Local deploy
After setting up the virtual environment, you just need to configure a few environment variables in order for Krampus to run.
```bash
DEFAULT_REGION=default_region # default region to look in, something like us-east-1
KRAMPUS_BUCKET=krampus_bucket_name # the name of the S3 bucket where the tasks file can be found
KRAMPUS_ROLE_NAME=role_name # the name of the role krampus will assume
TASKS_FILE_KEY=tasks_file # the object key in S3 where the JSON tasks can be downloaded
HIPCHAT_ACCESS_TOKEN=hipchat_api_token # if you want HipChat integration, define this var
HIPCHAT_ROOM=room_id # required to use HipChat, the room id to post messages to
```
At this point, you should be able to simply run the script.
```
./krampus.py
```
If any jobs have been uploaded to the tasks file, they will be actioned. Congratulations--you did it!

## Terraform deploy to AWS
To make deployment more friendly, Krampus now comes with a set of Terraform modules that streamline the process. To get started, change into the terraform directory and initialize the modules.
```
terraform init
terraform get
```
In each of the three modules(IAM, Lambda and S3) there is a variables.tf file that will need a little bit of setup. Change these values to match your desired config, such as choosing the role name, bucket name, etc.

Now, you're ready to get started. Use Terraform to validate that you are ok with the changes that are to be applied.
```
terraform plan
````
If everything looks good, go ahead and apply the changes to your infrastructure.
```
terraform apply
```
You're done!

### Manual deploy to AWS
Using the included Lambda distribution packaging script, going serverless could not be easier. First, we need to create the zipped distribution package to upload as the Lambda function.
```
./mkdist
```
This will create a file called krampus.zip in the krampus project root directory containing everything needed to run in Lambda. In the Lambda console UI, create a new function, and then "Author from scratch." Call it whatever you'd like. Under role, select "Choose an existing role" and select the krampus role under "Existing role." If you do not see the krampus role, make sure that the trust relationship with the Lambda service has been established as outlined above. Now hit “create function.”

In the management screen, there are just a couple more things that need to be set up. First, under "Function code," select "Python 2.7" as the runtime, then "Upload a .ZIP file" as the code entry type, and select the krampus.zip file. In the handler box, put "krampus.main"

The same environment variable requirements as above in local setup are also needed for Lambda. Under "Basic settings," increase the timeout from 3 seconds to 60. Krampus can complete about a task a second, so you can tweak this value to roughly match the maximum number of expected jobs for any given run.

You will also need to manually set up Krampus' bucket. After you've created it, make sure to update the KRAMPUS_BUCKET environment variable to tell Krampus where to find it. Make sure the bucket name matches the one specified in the S3 policy that was attached to the Krampus role earlier.

At this point you should be good to go. Try adding a few jobs to your task file and hitting the "test" button on the Lambda function's information page.

## Contributing
Contributions are always welcome and appreciated. Please see the [contribution guidelines](CONTRIBUTING.md) for more information.

## About
Krampus is guided and supported by the SendGrid Information Security team.

Krampus is maintained and funded by SendGrid, Inc.

## License
[The MIT License (MIT)](LICENSE)
