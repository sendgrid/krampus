###############################################################################
# krampus 0.3.4 - silver iodide
###############################################################################
# [tell a fun krampus tale]
###############################################################################
# TODO:
    # change all repeatable tasks to raise exception to be re-added instead of
      # catching exceptions
    # eventually checks for if a resource exists when pulling by id should
      # raise specific exception that invalid jobs not re-queued
###############################################################################
import time
import os
from lib.krampus_tasks import *
import lib.krampus_logging


# kramp it
class Krampus():
    def __init__(self, region, bucket_name, key, whitelist, krampus_role):
        # setup some basic things we need
        self.region = region
        self.bucket_name = bucket_name
        self.key = key # basically the filename
        self.whitelist = whitelist
        self.krampus_role = krampus_role
        # instanitate logger
        self.klog = KLog(self.bucket_name, "krampus_log_" + str(int(time.time())))
        self.kt = KTask(self.region, self.bucket_name, self.klog, self.whitelist, self.krampus_role)

    # collect our jobs
    def getTasks(self):
        # ktask is our friend dot ru
        self.kt.getTasks(self.key) # should populate kt.tasks

    # complete them
    def completeTasks(self):
        for task in self.kt.tasks:
            try:
                task.complete()
            except Exception as e:
                # generic except to keep things moving until we have fixed all the bugs in complete methods
                # add to deferred tasks to try later
                self.kt.deferred_tasks.append(task.as_json)
                # alert that there was an issue
                KLog.log("could not complete task: %s" % str(e), "critical")

    # update the tasks
    def updateTaskList(self):
        self.kt.rebuildTaskList()


def main(event, context):
    # collect our run information, otherwise just give it something I guess
    if os.getenv("DEFAULT_REGION"):
        region = os.getenv("DEFAULT_REGION")
    else:
        region = "us-east-1"
    if os.getenv("KRAMPUS_BUCKET"):
        krampus_bucket = os.getenv("KRAMPUS_BUCKET")
    else:
        krampus_bucket = "krampus-dev"
    if os.getenv("TASKS_FILE_KEY"):
        tasks_file_key = os.getenv("TASKS_FILE_KEY")
    else:
        tasks_file_key = "tasks.json"
    if os.getenv("ARN_WHITELIST"):
        whitelist = os.getenv("ARN_WHITELIST")
    else:
        whitelist = None
    if os.getenv("KRAMPUS_ROLE_NAME"):
        krampus_role = os.getenv("KRAMPUS_ROLE_NAME")
    else:
        krampus_role = "krampus"
    # fire it all up
    k = Krampus(region, krampus_bucket, tasks_file_key, whitelist, krampus_role)
    k.getTasks()
    k.completeTasks()
    k.updateTaskList()
    # save the log file
    k.klog.writeLogFile()
    print "[+] krampus is done sowing death and destruction in AWS... until next time!"


if __name__ == "__main__":
    main(None, None)
