###############################################################################
# get/put tasks from/to the bucket's tasks key
###############################################################################
# TODO:
# - Have all tasks return a status to krampus.py
# - Map each service to available actions (kill/disable/none)
# - Remove the requirement for KLog to specify account_id for Slack
###############################################################################

import boto3
import json
import time
from arnparse import arnparse
from botocore.exceptions import ClientError

# Internal imports
from kinder import ec2
from kinder import iam
from kinder import rds
from kinder import s3
from kinder import security_group
from kinder import ebs
from kinder import lambda_funcs
from lib.krampus_logging import KLog
from lib.aws_sessions import KSession

# not sure what keys will be passed, but I do know how what krampus wants
KEYS = {
    "aws_region": "aws_region",
    "ec2_instance_id": "ec2_instance_id",
    "rds_instance_name": "rds_instance_name",
    "s3_bucket_name": "s3_bucket_name",
    "security_group_id": "security_group_id",
    "s3_principal": "s3_principal",
    "s3_permission": "s3_permission",
    "aws_object_type": "aws_object_type",
    "action": "action",
    "action_time": "action_time",
    "iam_user": "iam_user",
    "ebs_volume_id": "ebs_volume_id",
    "arn": "aws_resource_name",
    "to_port": "to_port",
    "from_port": "from_port",
    "proto": "proto",
    "cidr_range": "cidr_range"
}

SERVICES = ["ec2", "s3", "iam", "rds", "lambda"]


# krampus takes orders
class KTask():
    def __init__(self, region, bucket_name, logger=False, whitelist=None, krampus_role="krampus"):
        # setup our interface to the bucket
        self.conn = boto3.resource("s3", region)
        self.bucket = self.conn.Bucket(bucket_name)
        self.key = ""
        self.tasks = []
        self.deferred_tasks = []  # so we can add them to the tasks file again
        self.json_data = ""  # is there a better way to init?
        # setup the whitelist
        self.whitelist = []
        if whitelist:
            self.whitelist = json.load(self.bucket.Object(whitelist).get()['Body'])['Whitelist']
        self.krampus_role = krampus_role

    # task classes trakced in above task lists
    class Task(object):
        def __init__(self, opts):
            # some opts we know we can expect
            self.action = opts['action']
            self.action_time = int(opts['action_time']) if opts['action_time'] else 0
            self.aws_region = opts['arn'].region
            self.job_params = opts  # store it all, not a lot anyway
            # we also make sure that each of these things has a session to use
            self.session = KSession(opts['arn'].account_id, opts['krampus_role']).getSession()

        def responseHandler(self, resp):
            if not resp:
                return "success"
            if type(resp) is not list:
                resp = [resp]
            success_count = 0
            for r in resp:  # some things need multiple calls
                code = r['ResponseMetadata']['HTTPStatusCode']
                if code >= 200 and code < 400:
                    # that's it all right
                    success_count += 1
                    KLog.log("{0} AWS success response!".format(self.job_params['arn'].arn_str), "info")
                else:
                    KLog.log("{0} AWS failed response: {1}".format(self.job_params['arn'].arn_str, r), "warn")
            if success_count == 0:
                # complete failure
                KLog.log(
                    "All calls for task {0} failed, please check logs {1}".format(self.job_params['arn'].arn_str),
                    "critical",
                    self.job_params['arn'].account_id
                )
            elif success_count == len(resp):
                # complete success
                KLog.log(
                    "The object '{0}' of type '{1}' was {2}ed on {3}".format(
                        (self.job_params['arn'].arn_str, self.job_params['arn'].service, self.action, time.time())
                    ),
                    "critical",
                    self.job_params['arn'].account_id
                )
            else:
                # something... else
                KLog.log(
                    "At least one call failed for {0}, please check logs".format(self.job_params['arn'].arn_str),
                    "critical",
                    self.job_params['arn'].account_id
                )

        def complete(self):
            # now we go through and see what type of action and object and call the appropriate kinder methods
            arn_obj = self.job_params['arn']
            obj_service = arn_obj.service
            obj_account_id = arn_obj.account_id
            obj_resource = arn_obj.resource
            obj_resource_type = arn_obj.resource_type

            # ebsvolume job
            if obj_service == "ec2" and obj_resource_type == "volume":
                ebs_volume = obj_resource
                if self.action == "kill":  # only ebs action right now
                    KLog.log("Deleting EBS volume with ID: {0}".format(ebs_volume), "info")
                    resp = ebs.EBS(ebs_volume, self.aws_region, self.session).kill()
                elif self.action == "disable":
                    KLog.log("'disable' action makes no sense for EBS volume: {0}, deleting instead".format(ebs_volume), "warn")
                    resp = ebs.EBS(ebs_volume, self.aws_region, self.session).kill()
                else:
                    KLog.log(
                        "Did not understand action '{0}' for EBS job type on {1}".format(self.action, ebs_volume),
                        "critical",
                        obj_account_id,
                    )
                    resp = None
                self.responseHandler(resp)
            # security_group job
            elif obj_service == "ec2" and obj_resource_type == "security-group":
                security_group_id = obj_resource
                if self.action == "kill":
                    KLog.log("Deleting security_group: {0}".format(security_group_id))
                    resp = security_group.SecurityGroup(security_group_id, self.aws_region, self.session).kill()
                elif self.action == "disable":
                    KLog.log("Pulling rule on: {0}".format(security_group_id))
                    resp = security_group.SecurityGroup(security_group_id, self.aws_region, self.session).disable(
                        self.job_params['cidr_range'],
                        self.job_params['from_port'],
                        self.job_params['to_port'],
                        self.job_params['proto']
                    )
                else:
                    KLog.log(
                        "Did not understand action '{0}' for security-group job type on {1}".format(
                            self.action, security_group_id
                        ),
                        "critical",
                        obj_account_id
                    )
                    resp = None
                self.responseHandler(resp)
            # ec2instance job
            elif obj_service == "ec2" and obj_resource_type == "instance":
                ec2_instance = obj_resource
                if self.action == "disable":
                    KLog.log("Disabling EC2 instance: {0}".format(ec2_instance))
                    resp = ec2.EC2(ec2_instance, self.aws_region, self.session).disable()
                elif self.action == "kill":
                    KLog.log("Deleting EC2 instance: {0}".format(ec2_instance))
                    resp = ec2.EC2(ec2_instance, self.aws_region, self.session).kill()
                else:
                    KLog.log(
                        "Did not understand action '{0}' for EC2 job on {1}".format(self.action, ec2_instance),
                        "critical",
                        obj_account_id
                    )
                    resp = None
                self.responseHandler(resp)
            # s3 job
            elif obj_service == "s3":
                bucket = obj_resource
                remove_all = False
                try:
                    s3_permissions = self.job_params[KEYS['s3_permission']]
                    s3_principal = self.job_params[KEYS['s3_principal']]
                    s3_principal_type = "Group" if self.job_params[KEYS['s3_principal']].find("http") > -1 else "CanonicalUser"
                except KeyError:
                    KLog.log("S3 job {0} was not passed with principal/permissions - all perms will be removed".format(bucket), "warn")
                    remove_all = True
                if self.action == "disable" and not remove_all:
                    KLog.log(
                        "Deleting permissions '{0}' for principal '{1}' on bucket '{2}'"
                        .format(", ".join(map(str, s3_permissions)), s3_principal, bucket)
                    )
                    resp = s3.S3(bucket, self.session).deleteGrant(s3_principal, s3_principal_type, s3_permissions)
                elif self.action == "disable" and remove_all:
                    KLog.log("removing all permissions on '%s'" % bucket, "info")
                    resp = s3.S3(bucket, self.session).deleteAllGrants()
                else:
                    KLog.log(
                        "Did not understand action '{0}' for S3 job type on {1}".format(self.action, bucket),
                        "critical",
                        obj_account_id
                    )
                    resp = None
                self.responseHandler(resp)
            # iam job
            elif obj_service == "iam":
                iam_obj = obj_resource
                iam_obj_type = obj_resource_type
                if self.action == "kill":
                    KLog.log("Deleting IAM Object: {0}".format(iam_obj))
                    resp = iam.IAM(iam_obj, iam_obj_type, self.session, self.aws_region).kill()
                elif self.action == "disable":
                    KLog.log("Disabling IAM Object: {0}".format(iam_obj))
                    resp = iam.IAM(iam_obj, iam_obj_type, self.session, self.aws_region).disable()
                else:
                    KLog.log(
                        "Did not understand action '{0}' for IAM job type on {1}".format(self.action, iam_obj),
                        "critical",
                        obj_account_id
                    )
                    resp = None
                self.responseHandler(resp)
            # rds job
            elif obj_service == "rds":
                rds_instance = obj_resource
                if self.action == "disable":
                    KLog.log("Disabling RDS instance: {0}".format(rds_instance))
                    resp = rds.RDS(rds_instance, self.aws_region, self.session).disable()
                elif self.action == "kill":
                    KLog.log("'kill' action too dangerous for RDS job: {0}, will be dequeued".format(rds_instance), "critical")
                    resp = None  # will cause responseHandler to dequeue this job
                else:
                    KLog.log(
                        "Did not understand action '{0}' for RDS job type on {1}".format(self.action, rds_instance),
                        "critical",
                        obj_account_id
                    )
                    resp = None
                self.responseHandler(resp)
            # lambda job
            elif obj_service == "lambda":
                func_name = obj_resource
                if self.action == "disable":
                    KLog.log("Lambda job '{0}' has no disable action, will kill instead".format(arn_obj.arn_str))
                    resp = lambda_funcs.Lambda(func_name, self.aws_region, self.session).kill()
                elif self.action == "kill":
                    KLog.log("Deleting Lambda function '{0}'".format(arn_obj.arn_str))
                    resp = lambda_funcs.Lambda(func_name, self.aws_region, self.session).kill()
                else:
                    KLog.log(
                        "Did not understand action '{0}' for Lambda job '{1}'".format(self.action, func_name),
                        "critical",
                        obj_account_id
                    )
                    resp = None
                # send it back
                self.responseHandler(resp)
    # end Task class

    # Helper to extract ARN information
    class ARN():
        def __init__(self, arn_str):
            self.resolveARN(arn_str)

        def resolveARN(self, arn_str):
            self.arn_str = arn_str
            arn = arnparse(arn_str)

            self.service = arn.service
            self.region = arn.region
            self.account_id = arn.account_id
            self.resource = arn.resource
            self.resource_type = arn.resource_type
            self.service = arn.service
    # end ARN class

    # I WANT THE TASKS
    def getTasks(self, key):
        # in case we're dealing with multiple files for some reason, save current ref
        self.key = key
        try:  # we'll actually want to save this for later to rebuild task list
            self.json_data = json.load(self.bucket.Object(key).get()['Body'])
        except ClientError as e:
            print "[!] failed to download tasks file: {0}".format(str(e))
            KLog.log("Failed to download tasks file: {0}".format(str(e)), "critical")
            exit()

        for job in self.json_data['tasks']:
            # resolve the arn
            arn_obj = KTask.ARN(job[KEYS['arn']])
            obj_service = arn_obj.service
            obj_account_id = arn_obj.account_id
            obj_resource_type = arn_obj.resource_type

            # Skip task if AWS IAM Managed Policy
            if obj_account_id == 'aws' and obj_service == 'iam' and obj_resource_type == 'policy':
                KLog.log("Can't action AWS managed policy: {0}, will not be retried".format(job[KEYS['arn']], "warn"))
                continue

            # Skip task if action_time is in the future or task is in whitelist
            if job[KEYS['action_time']] >= time.time():
                KLog.log("deferring job of type: {0}, not time to action".format(obj_service), "info")
                self.deferred_tasks.append(job)
                continue
            elif job[KEYS['arn']] in self.whitelist:
                KLog.log("can't action whitelisted object: {0}, will not be retried".format(job[KEYS['arn']], "critical"))
                continue

            # Collect params if we can classify and instantiate
            opts = {}
            for k in job:
                if k in KEYS.keys():  # collect valid ones
                    opts[k] = job[KEYS[k]]

            # Add the ARN object and role name
            opts['arn'] = arn_obj
            opts['krampus_role'] = self.krampus_role

            # task obj if/else series determines how the additional args outside action etc used
            t = KTask.Task(opts)
            if obj_service not in SERVICES:
                KLog.log("Got unrecognized AWS object type: {0}".format(obj_service), "warn")
                continue  # don't append a non-existant task brah

            # add it to the list of things to action on
            # save json representation for convenience
            t.as_json = job
            self.tasks.append(t)
        # end of task iterator

    # rebuild the task list with completed tasks removed, then upload it
    def rebuildTaskList(self):
        # in python dicts are immutable, so we need to build a new obj
        # first add deferred tasks
        updated_json = {
            "tasks": self.deferred_tasks
        }
        # then add whatever else is in that obj, skipping tasks key of course
        for k in self.json_data:
            if k == "tasks":
                continue
            else:
                updated_json[k] = self.json_data[k]
        # convert from dict so aws doesn't complain
        updated_json = json.dumps(updated_json)
        # put it to the bucket
        resp = self.bucket.Object(self.key).put(Body=updated_json)
        KLog.log("done updating tasks list: {0}".format(self.key), "info")

        return resp
