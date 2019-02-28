###############################################################################
# AWS session handling via STS for krampus
###############################################################################
# create and store cross-account sessions we need. when a job is submitted,
# we will know its parent account id. each of these accounts has a krampus role
# that we will assume into by building the assume role request based on the
# account number. each session will be saved in a dict mapped by id:session_obj
# so that future jobs on the same account passed later in the tasks list will
# re-use the existing sessions
###############################################################################
# TODO:
###############################################################################
import boto3
from botocore.exceptions import ClientError

from lib.krampus_logging import KLog

sessions = {}  # keep dict of existing sessions as { <id> : boto_sess_inst }


class KSession(object):
    # create a new session
    def __init__(self, account_id, role_name):
        # before anything see if we already have this session

        if account_id in sessions:
            self.session = sessions[account_id]
            return None
        # otherwise lets get a session going
        sts = boto3.client("sts")
        arn_str = "arn:aws:iam::{0}:role/{1}".format(account_id, role_name)

        try:
            sess = sts.assume_role(RoleArn=arn_str, RoleSessionName=account_id)
        except ClientError as e:  # prob does not have perms to assume
            print "[!] issue assuming role {0}: {1}".format(arn_str, str(e))
            KLog.log("issue assuming role {0}: {1}".format(arn_str, str(e)), "critical")
            return None
        # if that works lets save the session
        sessions[account_id] = boto3.Session(
            aws_access_key_id=sess['Credentials']['AccessKeyId'],
            aws_secret_access_key=sess['Credentials']['SecretAccessKey'],
            aws_session_token=sess['Credentials']['SessionToken']
        )
        self.session = sessions[account_id]

    def getSession(self):
        if self.session:
            return self.session
        else:
            KLog.log("odd, getSession failed while retrieving existing object", "warning")
            raise Warning("could not get a session object")
