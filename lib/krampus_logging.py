###############################################################################
# krampus logging utility
###############################################################################
# TODO:
# - the in-mem scheme was not necessary because lambda gives you a /tmp dir
# - Allow ability to filter which messages to go to Slack (errors/kill/disable)
# -- (i.e. differentiate between actions and logging), and determine account_id
# - Add environment variable for the account_mapping key
# - Remove global variables
###############################################################################
import boto3
import json
import os
import requests
import time

# given how modules work with python it was easiest to use globals
# I know, I know
messages = []

accountmapping_bucket = None
accountmapping_key = None
webhook_url = None
default_channel = None


# yeah this is a mess and should have been fully static sometimes
# it is easier to just avoid side effects, you know?
class KLog(object):
    def __init__(self, bucket_name, key, region="us-east-1"):
        self.region = region
        self.conn = boto3.resource("s3", self.region)
        self.bucket = self.conn.Bucket(bucket_name)
        self.key = key
        self.log_file = self.bucket.Object(key)

    # add a log msg to the list
    # because we are doing unique files per run we store all messages in mem
    # then before krampus exits we upload to the specified key
    # FIXME: Sets default account_id to None for generic log messages,
    # but can be set for Slack messages
    @staticmethod
    def log(msg, level="info", account_id=None):
        # Set list of levels and default to info if provided not in list
        levels = ["info", "warn", "critical"]
        level = level.lower()
        if level not in levels:
            level = "info"

        # If critical - send to Slack
        if webhook_url and level == "critical":
            channel = KLog.get_account_map_channel(account_id, "us-east-1")
            if not channel:
                channel = default_channel
            KLog.send_slack_message(webhook_url, msg, channel, 'danger')

        # due to interesting decisions log message stay in mem until run finish
        messages.append({
            "level": level,
            "msg": msg,
            "timestamp": int(time.time())
        })

    @staticmethod
    def get_account_map_channel(account_id, region="us-east-1"):
        """
        Searches the account_mapping file for a matching SlackChannel definition
        :param account_id: The value of the account_id to search for
        :return: channel_name or None
        """

        # FIXME: Temporary workaround for global definitions
        # FIXME: Change to be retrieved only once per Krampus run
        conn = boto3.resource("s3", region)
        bucket = conn.Bucket(accountmapping_bucket)

        mapping_channel = None
        if accountmapping_bucket and accountmapping_key:
            try:
                # Grab the JSON and filter for the matching account_id
                account_map = json.load(bucket.Object(accountmapping_key).get()['Body'])
                filtered_list = filter(lambda x: account_id == x['AccountNumber'], account_map)
                if filtered_list:
                    mapping_channel = filtered_list[0]['SlackChannel']
            except Exception as e:
                print "Unable to download account_mapping list: {0}".format(str(e))
                KLog.log("Unable to download account_mapping list: {0}".format(str(e)), "warn")

        return mapping_channel

    @staticmethod
    def delay_slack_message(retry_after):
        """
        Delays a Slack message by the value provided in Retry-After or by 1s
        :param retry_after: The value of the Retry-After header
        """
        if retry_after <= 1:
            time.sleep(retry_after + 1)
        else:
            time.sleep(retry_after)

    @staticmethod
    def send_slack_message(webhook_url, message, channel, color='warning'):
        """
        Sends a slack message.
        :param webhook_url: the slack webhook URL
        :param message: the message to be sent
        :param channel: the slack channel to send to
        :param color: the color of the message in slack (good, warning, danger) or color hex
        :return: boolean of success
        """

        url = webhook_url

        data = {
            "payload": {
                "text": message,
            },
            "channel": channel,
            "attachments": [
                {
                    "fallback": "Krampus",
                    "color": color,
                    "fields": [
                        {
                            "title": "Krampus",
                            "value": message,
                            "short": False
                        }
                    ]
                }
            ]
        }

        rsp = requests.post(url, data=json.dumps(data))

        # Rate limits messages being sent to Slack
        if rsp.headers.get('Retry-After') is not None or str(rsp.status_code) == '429':
            count = 0
            while count < 3:
                KLog.delay_slack_message(int(rsp.headers.get('Retry-After')))
                count += 1

        if str(rsp.status_code) == '429':
            KLog.log("Slack webhook failed rate limiting 3 times", "warn")
        elif str(rsp.status_code)[0] != '2':
            KLog.log("Slack webhook returned {0} - post to Slack likely failed".format(str(rsp.status_code)), "warn")

    # write the final product
    def writeLogFile(self):
        # we will need to go through each of the entries to make them into a
        # friendly-ish log format. instead of dumping json objs from the
        # array of messages, we'll create newline delimited log messages
        # to write to our key
        buff = ""
        for m in messages:
            buff += "[{0}] {1}: {2}\n".format(m['timestamp'], m['level'].upper(), m['msg'])
        # now we can worry about putting to s3
        resp = self.bucket.Object(self.key).put(Body=buff)
        return resp


if os.getenv("AWS_ACCOUNTMAPPING_BUCKET"):
    accountmapping_bucket = os.getenv("AWS_ACCOUNTMAPPING_BUCKET")
else:
    accountmapping_bucket = "bucket_name"

if os.getenv("AWS_ACCOUNTMAPPING_KEY"):
    accountmapping_key = os.getenv("AWS_ACCOUNTMAPPING_KEY")
else:
    accountmapping_key = "account-map.json"

if os.getenv("SLACK_WEBHOOK_URL"):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
else:
    webhook_url = None

if os.getenv("SLACK_DEFAULT_CHANNEL"):
    default_channel = os.getenv("SLACK_DEFAULT_CHANNEL")
else:
    default_channel = "#krampus"

# Warn if Slack configuration is missing
if not os.getenv("SLACK_WEBHOOK_URL"):
    KLog.log("Missing Slack webhook URL. Check environment variables.", "warn")
