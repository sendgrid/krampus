###############################################################################
# krampus 0.3.8
###############################################################################
# [tell a fun krampus tale]
###############################################################################
# TODO:
    # change all repeatable tasks to raise exception to be re-added instead of
      # catching exceptions
    # eventually checks for if a resource exists when pulling by id should
      # raise specific exception that invalid jobs not re-queued
    # Add the option to perform a dry run with no actioning
###############################################################################
import os
import time

# Internal imports
from lib.krampus_tasks import *
import lib.krampus_logging


class Krampus():
    # Setup basic things we need and instantiate logger and krampus_tasks
    def __init__(self, region, bucket_name, key, whitelist, krampus_role):
        self.region = region
        self.bucket_name = bucket_name
        self.key = key
        self.whitelist = whitelist
        self.krampus_role = krampus_role

        self.klog = KLog(self.bucket_name, "krampus_log_{0}".format(str(int(time.time()))))
        self.kt = KTask(self.region, self.bucket_name, self.klog, self.whitelist, self.krampus_role)

    # Collect jobs to populate kt.tasks
    def getTasks(self):
        self.kt.getTasks(self.key)

    # Complete tasks, otherwise defer them to be actioned later
    def completeTasks(self):
        for task in self.kt.tasks:
            try:
                task.complete()
            except Exception as e:
                # TODO: Resolve bugs in resource complete() methods to avoid deferral
                self.kt.deferred_tasks.append(task.as_json)
                KLog.log("Unable to complete task: {0}".format(str(e)), "critical")

    # Update tasks, removing completed and keeping deferred
    def updateTaskList(self):
        self.kt.rebuildTaskList()


# Collects information required to run, otherwise set to preset values
def main(event, context):
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

    k.klog.writeLogFile()
    print "[+] Krampus is done sowing death and destruction in AWS...until next time!"


if __name__ == "__main__":
    main(None, None)
