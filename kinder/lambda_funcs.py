###############################################################################
# Lambda kinder class
###############################################################################
# lambda is actionable dot ru
###############################################################################
# TODO:
###############################################################################
from lib.krampus_logging import KLog


class Lambda():
    def __init__(self, func_name, region, sess):
        try:
            self.conn = sess.client("lambda", region_name=region)
        except Exception as e:
            KLog.log("issue connecting to AWS %s" % str(e), "critical")
            exit("[!] issue connecting to AWS: %s" % str(e))
        # get volume reference
        self.func = func_name
        self.region = region
        # save raw sess in case of instance actions
        self.sess = sess

    def disable(self):
        KLog.log("no disable action for lambda function '%s', will delete instead" % self.func, "warning")
        return self.kill()

    def kill(self):
        try:
            # low level call, just pass the resp back
            return self.conn.delete_function(FunctionName=self.func)
        except Exception as e:
            if str(e).find("ResourceNotFoundException") is not -1:
                KLog.log("could not find function '%s', dequeueing task" % self.func)
            else:
                KLog.log("could not delete function '%s', unknown error: %s" % str(e), "critical")
            return None
