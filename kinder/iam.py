###############################################################################
# IAM kinder class provides methods to be hooked by Ruten
###############################################################################
# give us a resource and an action and we'll figure it out
###############################################################################
# TODO:
# decide if we want to save responses for the get* actions
###############################################################################
from lib.krampus_logging import KLog


class IAM():
    def __init__(self, iam_resource, iam_resource_type, sess, region="us-east-1"):
        # we'll inevitably make many calls with this module, track whether they work
        self.responses = []
        # unfortunately we need both the low-level client, and the resource stuff
        self.conn = sess.resource("iam")
        self.resource = sess.client("iam")
        self.iam_type = iam_resource_type
        self.iam_obj = iam_resource

    # disable iam resource. aws makes you detach EVERYTHING first *sigh*
    def disable(self):
        # disable a user
        if self.iam_type == "user":
            # first inline policies
            for p in self.getPolicies("inline"):
                self.detachPolicy(p, "inline")
            # now remove arn policies
            for p in self.getPolicies("arn"):
                self.detachPolicy(p['PolicyArn'], "arn")
            # now remove all groups
            for g in self.getGroups():
                self.removeGroup(g)
            # now access keys
            for k in self.getAccessKeys():
                self.killAccessKey(k)
            # now signing certs
            for c in self.getSigningKeys():
                self.deleteSigningKey(c)
        # for roles and groups
        elif self.iam_type == "role":
            for p in self.getPolicies("inline"):
                self.detachPolicy(p, "inline")
            for p in self.getPolicies("arn"):
                self.detachPolicy(p.arn, "arn")
            # instance profiles for roles, too
            for ip in self.conn.Role(self.iam_obj).instance_profiles.all():
                ip.remove_role(RoleName=self.iam_obj)
        elif self.iam_type == "group":
            for u in self.conn.Group(self.iam_obj).users.all():
                self.conn.Group(self.iam_obj).remove_user(UserName=u.name)
            for p in self.getPolicies("inline"):
                self.detachPolicy(p, "inline")
            for p in self.getPolicies("arn"):
                self.detachPolicy(p.arn, "arn")
        return self.responses

    # actually murdercate the object, disable MUST be ran first according to amazon
    # because they will not delete users with active keys, certs or policies
    def kill(self):
        self.disable()  # always have to remove all policies for any iam type
        resp = ""
        if self.iam_type == "user":
            resp = self.conn.User(self.iam_obj).delete()
        elif self.iam_type == "role":
            resp = self.conn.Role(self.iam_obj).delete()
        elif self.iam_type == "group":
            resp = self.conn.Group(self.iam_obj).delete()
        self.responses.append(resp)
        return self.responses

    # get a list of attached policies by type
    def getPolicies(self, ptype):
        # for users
        if self.iam_type == "user":
            if ptype == "inline":
                return self.resource.list_user_policies(
                    UserName=self.iam_obj)['PolicyNames']
            elif ptype == "arn":
                return self.resource.list_attached_user_policies(
                    UserName=self.iam_obj)['AttachedPolicies']
        # for roles
        elif self.iam_type == "role":
            if ptype == "inline":
                return self.conn.Role(self.iam_obj).policies.all()
            elif ptype == "arn":
                return self.conn.Role(self.iam_obj).attached_policies.all()
        # for groups
        elif self.iam_type == "group":
            if ptype == "inline":
                return self.conn.Group(self.iam_obj).policies.all()
            elif ptype == "arn":
                return self.conn.Group(self.iam_obj).attached_policies.all()

    # remove policy from the IAM user
    def detachPolicy(self, pname, ptype):
        # delete or remove based on type
        resp = ""
        if self.iam_type == "user":
            if ptype == "inline":
                resp = self.resource.delete_user_policy(
                    UserName=self.iam_obj,
                    PolicyName=pname)
            elif ptype == "arn":
                resp = self.resource.detach_user_policy(
                    UserName=self.iam_obj,
                    PolicyArn=pname)
        # for roles
        elif self.iam_type == "role":
            if ptype == "inline":
                resp = self.conn.RolePolicy(self.iam_obj, pname.name).delete()
            elif ptype == "arn":
                resp = self.conn.Role(self.iam_obj).detach_policy(PolicyArn=pname)
        # for groups
        elif self.iam_type == "group":
            if ptype == "inline":
                resp = self.conn.GroupPolicy(self.iam_obj, pname.name).delete()
            elif ptype == "arn":
                resp = self.conn.Group(self.iam_obj).detach_policy(
                    PolicyArn=pname)

        # whatever we got, add to responses list
        self.responses.append(resp)

    # get a list of groups for a user
    def getGroups(self):
        group_names = []
        for g in self.conn.User(self.iam_obj).groups.all():
            group_names.append(g.group_name)
        return group_names

    # take user out of group
    def removeGroup(self, gname):
        return self.responses.append(
            self.conn.User(self.iam_obj).remove_group(GroupName=gname))

    # get the full list of their keys
    def getAccessKeys(self):
        key_ids = []
        for k in self.conn.User(self.iam_obj).access_keys.all():
            key_ids.append(k.access_key_id)
        return key_ids

    # soft action, disable this user's key
    def disableAccessKey(self, access_key_id):
        return self.responses.append(
            self.conn.AccessKey(self.iam_obj, access_key_id).deactivate())

    # soft action, delete the key
    def killAccessKey(self, key_id):
        return self.responses.append(
            self.conn.AccessKey(self.iam_obj, key_id).delete())

    # get the list of signing certs for this user
    def getSigningKeys(self):
        key_ids = []
        for k in self.resource.list_signing_certificates(UserName=self.iam_obj)['Certificates']:
            key_ids.append(k['CertificateId'])
        return key_ids

    # remove a signing key
    def deleteSigningKey(self, signing_key_id):
        return self.responses.append(
            self.resource.delete_signing_certificate(UserName=self.iam_obj, CertificateId=signing_key_id))
