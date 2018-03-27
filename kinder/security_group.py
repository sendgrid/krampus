###############################################################################
# security group kinder class
###############################################################################
# TODO:
# no ipv6 support
###############################################################################
from botocore.exceptions import ClientError
from lib.krampus_logging import KLog


class SecurityGroup():
    def __init__(self, group_id, region, sess):
        try:
            self.conn = sess.resource("ec2", region_name=region)
            # set it
            self.group = self.conn.SecurityGroup(group_id)
            self.group.load()  # bails us out if the group is bogus
        except ClientError:  # typical when group id does not exist
            KLog.log("security group %s does not exist" % group_id, "warning")
            self.group = False
        except:
            KLog.log("issue connecting to AWS", "critical")
            exit("[!] issue connecting to AWS")

    # see if there is a specified range in this rule
    def hasRange(self, rules, cidr_range):
        found = False
        for r in rules:
            if r['CidrIp'] == cidr_range:
                found = True
                break
        return found

    # since we cannot remove attached groups and we have no efficient way to
    # query for which instances it is attached to, burn all the routes down
    def kill(self):
        if not self.group:
            return None  # will cause this invalid group's job to dequeue
        resp = []
        if len(self.group.ip_permissions_egress) > 0:
            # revokes all rules
            resp.append(self.group.revoke_egress(
                IpPermissions=self.group.ip_permissions_egress))
        if len(self.group.ip_permissions) > 0:
            resp.append(self.group.revoke_ingress(IpPermissions=self.group.ip_permissions))
        return resp

    # for secgroups, 'disabling' amounts to removing the problem rule
    def disable(self, cidr_ip, from_port, to_port, proto, direction="ingress"):
        if not self.group:
            return None  # will cause this invalid group's job to dequeue
        if direction == "ingress":
            return self.group.revoke_ingress(
                CidrIp=cidr_ip,
                FromPort=from_port,
                ToPort=to_port,
                GroupName=self.group.group_name,
                IpProtocol=proto)

        # though the docs say this call *should* be identical to the above, it doesn't work
        # so we have to take some extra steps here unfortunately
        elif direction == "egress":
            for rule in self.group.ip_permissions_egress:
                if rule['FromPort'] == from_port and rule['ToPort'] == to_port and rule['IpProtocol'] == proto and self.hasRange(rule['IpRanges'], cidr_ip):
                    # good enough for me, remove it from the list
                    self.group.revoke_egress(IpPermissions=[rule])
            # update the permissions
            return self.group.ip_permissions_egress
        else:
            KLog.log("rule direction must be (in|e)gress, got {0}".format(direction), "info")
