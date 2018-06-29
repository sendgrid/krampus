###############################################################################
# S3 kinder class provides methods to be hooked by Ruten
###############################################################################
# requires an AWS instance id and the region where it can be found
# it would appear s3 buckets do not really have the concept of starting and
# stopping, but we can add an ACL that denies all access
###############################################################################
# TODO:
###############################################################################
from lib.krampus_logging import KLog


class S3():
    def __init__(self, bucket_name, sess, region="us-east-1"):
        try:
            self.conn = sess.resource("s3", region_name=region)
        except:
            KLog.log("issue connecting to AWS", "critical")
            exit("[!] issue connecting to AWS")
        # set it - as far as krampus is concerned the acls are the bucket
        self.bucket = self.conn.BucketAcl(bucket_name)

    # what ACEs have been applied?
    def getGrants(self):
        return self.bucket.grants

    # remove all grants
    def deleteAllGrants(self):
        return self.bucket.put(
            AccessControlPolicy={
                "Grants": [],
                "Owner": self.bucket.owner
            }
        ) # done

    # do some ACL magic to pull access to bucket
    def deleteGrant(self, principal, principal_type, perms):
        acl = []
        for g in self.getGrants():
            if g['Grantee']['Type'] == principal_type:  # matched on type at least
                if principal_type == "CanonicalUser":
                    if g['Grantee']['ID'] == principal and g['Permission'] in perms:
                        # we found the offending permission, skip adding to new ACL
                        continue
                elif principal_type == "Group":
                    if g['Grantee']['URI'] == principal and g['Permission'] in perms:
                        # we found it, skip to prevent it being added
                        continue
                else:
                    # not aware of any other principal types, but best not to assume
                    KLog.log("krampus cannot modify ACEs for principal type: %s" % principal_type, "critical")
                    return False
                # we maintain a new list to pass to the BucketAcl.put method
                # if we made it here, then we want to keep the ACE 'g'
                if g not in acl:
                    acl.append(g)
        # it's over, update the ACL on AWS' side
        return self.bucket.put(
            AccessControlPolicy={
                "Grants": acl,
                "Owner": self.bucket.owner
            }
        ) # alternate remediation could be changing owner
