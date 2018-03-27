###############################################################################
# EBS kinder class
###############################################################################
# it could be debated whether this is more appropriate to put in the ec2
# module since ebs volumes are associated with them as a subresource as far
# as boto is concerned. however we don't take organizational cues from boto,
# and other projects like securitymonkey seem to do more or less the same
###############################################################################
# TODO:
###############################################################################
from re import search

from kinder.ec2 import EC2  # need to work with instance parents
from lib.krampus_logging import KLog


class EBS():
    def __init__(self, volume_id, region, sess):
        try:
            self.conn = sess.resource("ec2", region_name=region)
        except Exception as e:
            KLog.log("issue connecting to AWS %s" % str(e), "critical")
            exit("[!] issue connecting to AWS: %s" % str(e))
        # get volume reference
        self.volume = self.conn.Volume(volume_id)
        self.region = region
        # save raw sess in case of instance actions
        self.sess = sess

    # kill action
    def kill(self):
        # no exceptions etc, let them bubble up to krampus.py so task re-queues
        resp = None
        try:
            resp = self.volume.delete()
        except Exception as e:  # doesn't look like boto has one for VolInUse error
            # get the attached instance and detach from it
            if str(e).find("VolumeInUse") is not -1:  # we use the exception to get vol id
                m = search("(i-[a-f0-9]+)$", str(e))
                instance = m.group(0)
                if EC2(instance, self.region, self.sess).status()['Name'] == "stopped":
                    # in a state we can work with, detach
                    self.volume.detach_from_instance(
                        InstanceId=instance)
                    KLog.log("volume %s detached, deleting now..." % self.volume.id, "info")
                    resp = self.volume.delete()
                else:  # shut down, we can detach and delete next run
                    EC2(instance, self.region, self.sess).disable()
                    msg = "parent instance of {0} stopped, volume will be deleted next run".format(self.volume.id)
                    KLog.log(msg, "warn")
                    raise Exception(msg)  # requeues job
            elif str(e).find("NotFound") is not -1:
                KLog.log("looks like volume {0} was already deleted, dequeueing job".format(self.volume.id), "warn")
        return resp
