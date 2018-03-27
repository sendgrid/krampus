###############################################################################
# krampus logging utility
###############################################################################
# TODO:
# the in-mem scheme was not necessary because lambda gives you a /tmp dir
# should have read the docs man
###############################################################################
import boto3
import time
import os
from hypchat import HypChat

# given how modules work with python it was easiest to use globals
# I know, I know
messages = []
hc_room = None


# yeah this is a mess and should have been fully static sometimes
# it is easier to just avoid side effects, you know?
class KLog(object):
    def __init__(self, bucket_name, key, region="us-east-1"):
        self.conn = boto3.resource("s3", region)
        self.bucket = self.conn.Bucket(bucket_name)
        self.key = key
        self.log_file = self.bucket.Object(key)

    # add a log msg to the list
    # because we are doing unique files per run we store all messages in mem
    # then before krampus exits we upload to the specified key
    @staticmethod
    def log(msg, level="info"):
        levels = ["info", "warn", "critical"]  # keep it simple
        level = level.lower()
        if level not in levels:
            level = "info"  # don't allow random stuff
        # print the stdout part
        # stdout print prepends
        prepends = {
            "info": "[i]",
            "warn": "[-]",
            "critical": "[!]"
        }
        print "%s %s" % (prepends[level], msg)
        # see if it should go to the hipchat room
        if level == "critical":
            KLog.hipLog(msg)
        # due to interesting decisions log message stay in mem until run finish
        messages.append({
            "level": level,
            "msg": msg,
            "timestamp": int(time.time())
        })

    # log something to the hipchat room
    @staticmethod
    def hipLog(msg):
        if not hc_room:
            # don't change below to critical, think about it...
            KLog.log("tried to log to hipchat without a working connection", "warn")
            return False
        # otherwise let's set as red
        hc_room.notification("KRAMPUS: " + msg, "red")

    # write the final product
    def writeLogFile(self):
        # we will need to go through each of the entries to make them into a
        # friendly-ish log format. instead of dumping json objs from the
        # array of messages, we'll create newline delimited log messages
        # to write to our key
        buff = ""
        for m in messages:
            buff += "[%d] %s: %s\n" % (m['timestamp'], m['level'].upper(), m['msg'])
        # now we can worry about putting to s3
        resp = self.bucket.Object(self.key).put(Body=buff)
        return resp


# just trust me when I say at the time I was out of options and needed global namespace
# should have planned better man
if os.getenv('HIPCHAT_ACCESS_TOKEN') and os.getenv('HIPCHAT_ROOM'):
    try:
        hc_room = HypChat(os.getenv('HIPCHAT_ACCESS_TOKEN')).get_room(os.getenv('HIPCHAT_ROOM'))
    except:
        KLog.log("problem starting hipchat, check env vars and connection", "warn")
