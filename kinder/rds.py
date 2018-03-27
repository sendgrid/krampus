###############################################################################
# RDS kinder class provides methods to be hooked by Ruten
###############################################################################
# requires an AWS RDS id and the region where it can be found
###############################################################################
# TODO:
# add more disable groups/rules
###############################################################################
from lib.krampus_logging import KLog


class RDS():
    def __init__(self, instance_name, region, sess):
        try:
            self.conn = sess.client('rds', region_name=region)
        except:
            KLog.log("issue connecting to AWS", "critical")
            exit("[!] issue connecting to AWS")
        # set it
        self.name = instance_name
        self.disable_groups = ['sg-c6d41cae']

    # where it at
    def status(self):
        return self.conn.describe_db_instances(DBInstanceIdentifier=self.name)

    # disable this instance
    def disable(self):
        # disable an instance
        try:
            return self.conn.stop_db_instance(DBInstanceIdentifier=self.name)
        # boto has no specific exception for InvalidDBInstanceState, which we get with multi-az
        except:
            # pull all the ingress rules
            return self.conn.modify_db_instance(
                DBInstanceIdentifier=self.name,
                DBSecurityGroups=[],
                VpcSecurityGroupIds=self.disable_groups,
                ApplyImmediately=True)

    # bring up this instance
    def enable(self):
        return self.conn.start_db_instance(DBInstanceIdentifier=self.name)
