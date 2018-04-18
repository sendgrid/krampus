###############################################################################
# get/put tasks from/to the bucket's tasks key
###############################################################################
# TODO:
# all these tasks should return a status to krampus.py
###############################################################################
import boto3
from botocore.exceptions import ClientError
import json
import time
import sys

# our stuff
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
                    KLog.log("%s aws success response!" % self.job_params['arn'].arn_str, "info")
                else:
                    KLog.log("%s aws failed response: %s" % (self.job_params['arn'].arn_str, r), "warn")
            if success_count == 0:
                # complete failure
                raise Warning("all calls for task %s failed, please check logs" % self.job_params['arn'].arn_str)
            elif success_count == len(resp):
                # complete success
                KLog.log(
                    "the object '%s' of type '%s' was %sed on %d" %
                    (self.job_params['arn'].arn_str, self.job_params['arn'].service, self.action, time.time())
                )
            else:
                # something... else
                KLog.log("at least one call failed for %s, please check logs" % self.job_params['arn'].arn_str, "critical")

        def complete(self):
            # now we go through and see what type of action and object and call the appropriate kinder methods
            arn_obj = self.job_params['arn']
            obj_type = arn_obj.service
            # this is an ebs volume job
            if obj_type == "ec2" and arn_obj.resource.find("volume") is not -1:
                ebs_volume = arn_obj.resource.split("/")[1]
                if self.action == "kill":  # only ebs action right now
                    KLog.log("deleting ebs volume with id: %s" % ebs_volume, "info")
                    resp = ebs.EBS(ebs_volume, self.aws_region, self.session).kill()
                elif self.action == "disable":
                    KLog.log("'disable' action makes no sense for EBS volume: %s, will be deleted instead" % ebs_volume, "warn")
                    resp = ebs.EBS(ebs_volume, self.aws_region, self.session).kill()
                else:
                    KLog.log("did not understand action '%s' for ebs job type on %s" % (self.action, ebs_volume), "critical")
                    resp = None
                self.responseHandler(resp)
            # security group job
            elif obj_type == "ec2" and arn_obj.resource.find("security-group") is not -1:
                security_group_id = arn_obj.resource.split("/")[1]
                if self.action == "kill":
                    KLog.log("deleting security group: %s" % security_group_id)
                    resp = security_group.SecurityGroup(security_group_id, self.aws_region, self.session).kill()
                elif self.action == "disable":
                    KLog.log("pulling rule on: %s" % security_group_id)
                    resp = security_group.SecurityGroup(security_group_id, self.aws_region, self.session).disable(
                        self.job_params['cidr_range'],
                        self.job_params['from_port'],
                        self.job_params['to_port'],
                        self.job_params['proto']
                    )
                else:
                    KLog.log("did not understand action '%s' for secgroup job type on %s" % (self.action, security_group_id), "critical")
                    resp = None
                self.responseHandler(resp)
            # standard ec2 instance job
            elif obj_type == "ec2":
                ec2_instance = arn_obj.resource.split("/")[1]
                if self.action == "disable":
                    KLog.log("disabling ec2 instance: %s" % ec2_instance)
                    resp = ec2.EC2(ec2_instance, self.aws_region, self.session).disable()
                elif self.action == "kill":
                    KLog.log("deleting ec2 instance: %s" % ec2_instance)
                    resp = ec2.EC2(ec2_instance, self.aws_region, self.session).kill()
                else:
                    KLog.log("did not understand action '%s' for ec2 job type on %s" % (self.action, ec2_instance), "critical")
                    resp = None
                self.responseHandler(resp)
            # s3 job
            elif obj_type == "s3":
                bucket = arn_obj.resource
                remove_all = False
                try:
                    s3_permissions = self.job_params[KEYS['s3_permission']]
                    s3_principal = self.job_params[KEYS['s3_principal']]
                    s3_principal_type = "Group" if self.job_params[KEYS['s3_principal']].find("http") > -1 else "CanonicalUser"
                except KeyError:
                    KLog.log("s3 job %s was not passed with principal and permission info - all perms will be removed" % bucket, "warn")
                    remove_all = True
                if self.action == "disable" and not remove_all:
                    KLog.log(
                        "deleting permissions '%s' for principal '%s' on bucket '%s'"
                        % (", ".join(map(str, s3_permissions)), s3_principal, bucket)
                    )
                    resp = s3.S3(bucket, self.session).deleteGrant(s3_principal, s3_principal_type, s3_permissions)
                elif self.action == "disable" and remove_all:
                    KLog.log("removing all permissions on '%s'" % bucket, "info")
                    resp = s3.S3(bucket, self.session).deleteAllGrants()
                else:
                    KLog.log("did not understand action '%s' for s3 job type on %s" % (self.action, bucket), "critical")
                    resp = None
                self.responseHandler(resp)
            # iam job
            elif obj_type == "iam":
                iam_obj = arn_obj.resource
                if self.action == "kill":
                    KLog.log("deleting iam object: %s" % iam_obj)
                    resp = iam.IAM(iam_obj, self.session, self.aws_region).kill()
                elif self.action == "disable":
                    KLog.log("disabling iam object: %s" % iam_obj)
                    resp = iam.IAM(iam_obj, self.session, self.aws_region).disable()
                else:
                    KLog.log("did not understand action '%s' for iam job type on %s" % (self.action, iam_obj), "critical")
                    resp = None
                self.responseHandler(resp)
            # rds job
            elif obj_type == "rds":
                rds_instance = arn_obj.resource
                if self.action == "disable":
                    KLog.log("disabling rds instance: %s" % rds_instance)
                    resp = rds.RDS(rds_instance, self.aws_region, self.session).disable()
                elif self.action == "kill":
                    KLog.log("'kill' action too dangerous for rds job: %s, will be dequeued" % rds_instance, "critical")
                    resp = None  # will cause responseHandler to dequeue this job
                else:
                    KLog.log("did not understand action '%s' for rds job type on %s" % (self.action, rds_instance), "critical")
                    resp = None
                self.responseHandler(resp)
            # lambda job
            elif obj_type == "lambda":
                func_name = arn_obj.resource
                KLog.log("deleting lambda function '%s'" % arn_obj.arn_str)
                if self.action == "disable":
                    KLog.log("lambda job '%s' has no disable action, will kill instead" % arn_obj.arn_str, "critical")
                    resp = lambda_funcs.Lambda(func_name, self.aws_region, self.session).kill()
                elif self.action == "kill":
                    resp = lambda_funcs.Lambda(func_name, self.aws_region, self.session).kill()
                else:
                    KLog.log("did not understand action '%s' for lambda job '%s'" % (self.action, func_name), "critical")
                    resp = None
                # send it back
                self.responseHandler(resp)
    # end task class

    # ktask ARN utils
    class ARN():
        def __init__(self, arn_str):
            self.resolveARN(arn_str)

        def resolveARN(self, arn_str):
            self.arn_str = arn_str
            # it all starts with a split
            arn = arn_str.split(":")
            # other than resource, most of it is the same
            self.service = arn[2]
            self.region = arn[3] if arn[3] is not "" else False
            self.account_id = arn[4]
            self.resource = arn[5]
            # special cases
            if self.service == "rds" or self.service == "lambda":
                self.resource = arn[6]  # deal with the resource:resource_name scheme we get for these guys
    # end ARN class

    # I WANT THE TASKS
    def getTasks(self, key):
        # in case we're dealing with multiple files for some reason, save current ref
        self.key = key
        try:  # we'll actually want to save this for later to rebuild task list
            self.json_data = json.load(self.bucket.Object(key).get()['Body'])
        except ClientError as e:
            KLog.log("failed to download tasks file: %s" % str(e), "critical")
            exit()
        for job in self.json_data['tasks']:
            # resolve the arn
            arn_obj = KTask.ARN(job[KEYS['arn']])
            obj_type = arn_obj.service
            # first, is this something we should worry about right now?
            if job[KEYS['action_time']] >= time.time():
                KLog.log("skipping job of type: %s" % obj_type, "info")
                self.deferred_tasks.append(job)
                continue  # over it
            elif job[KEYS['arn']] in self.whitelist:
                KLog.log("can't action whitelisted object: %s, will not be retried" % job[KEYS['arn']], "critical")
                continue
            # otherwise we can classify and instantiate
            # but first, collect all the params
            opts = {}
            for k in job:
                if k in KEYS.keys():  # collect valid ones
                    opts[k] = job[KEYS[k]]
            # add the arn object too
            opts['arn'] = arn_obj
            # pass role name
            opts['krampus_role'] = self.krampus_role
            # task obj if/else series determines how the additional args outside action etc used
            t = KTask.Task(opts)
            if (obj_type not in SERVICES):
                KLog.log("got unrecognized aws object type: " + obj_type, "warn")
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
        KLog.log("done updating tasks list: " + self.key, "info")
        return resp
