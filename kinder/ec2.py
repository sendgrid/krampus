###############################################################################
# EC2 kinder class
###############################################################################
# requires an AWS instance id and the region where it can be found
###############################################################################
# TODO:
###############################################################################
from botocore.exceptions import ClientError

from lib.krampus_logging import KLog


class EC2():
    def __init__(self, instance_id, region, sess):
        try:
            self.conn = sess.resource("ec2", region)
        except Exception as e:
            KLog.log("issue connecting to AWS %s" % str(e), "critical")
            exit("[!] issue connecting to AWS: %s" % str(e))
        # set it
        self.instance = self.getInstanceByID(instance_id)
        # verify the instance
        try:
            self.instance.load()
        except:
            KLog.log("provided instance id %s appears invalid" % instance_id, "warn")

    # whats up
    def status(self):
        return self.instance.state

    # disable this instance
    def disable(self):
        try:
            return self.instance.stop()
        except ClientError:
            KLog.log("instance %s already stopped or invalid, will be dequeued" % self.instance.instance_id, "info")
            return None  # colloquial dequeue

    # bring up this instance
    def enable(self):
        return self.instance.start()

    # no mr. bond... I expect you to die
    def kill(self):
        try:
            return self.instance.terminate()
        except ClientError:
            KLog.log("instance {0} already dead or invalid, will be dequeued".format(self.instance.instance_id), "info")
            return None  # colloquial dequeue

    # we need to be able to get the boto Instance obj to do stuff
    def getInstanceByID(self, instance_id):
        return self.conn.Instance(instance_id)
