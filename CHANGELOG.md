Krampus CHANGELOG
==================

This file shows a change history for the Krampus project

0.3.8
------
- [Matthew] Update README.md with additional information referencing Justice Engine for the tasks.json file

0.3.7
------
- [Matthew] Replace Hipchat with Slack message notifications
- [Matthew] Add the ability to set Slack channel using account\_mapping, otherwise use default 
- [Matthew] Allows definition of account\_id in KLog.log() for account\_mapping 
- [Matthew] Refactor resolveARN to utilize arnparse package for improved ARN detail
- [Matthew] Update Task.complete() to utilize ARN.resource\_type instead of parsing 
- [Matthew] Add check in getTasks to skip AWS Managed Policies 
- [Matthew] Update minimum versions for botocore, pip, and requests
- [Matthew] Update README.md and various formatting and comment updates

0.3.6
------
- [Tell] add a code of conduct blurb and a CLA comment

0.3.5
------
- [Chase] allow s3 kinder to accept multiple permissions to be removed from s3 object; fix dist script

0.3.4
------
- [Chase] various fixes and improvements in preparation for open source, thanks @MKgridSec

0.3.3
------
- [Chase] add bandit static scanning before building lambda deploy package

0.3.2
------
- [Chase] clarify that volumes belonging to stopped parents will be deleted next run
- [Chase] ensure action time is int so we don't skip jobs
- [Chase] new lambda kinder module, kill support only

0.3.1
------
- [Chase] fix issue where ARN parser passed empty region string to kinder modules

0.3.0
------
- [Chase] cleaner and more commented code
- [Chase] iam module now reports responses back to KTask
- [Chase] dequeue security group tasks when the group ID is invalid
- [Chase] don't throw hipchat connection error if no related env vars set

0.2.13
------
- [Chase] ec2 module should check if instance exists before taking action

0.2.12
------
- [Chase] do you smell that in the air, ebs volumes? that's death approaching
- [Chase] improve logging a little bit

0.2.11
------
- [Chase] fix iam role delete to remove instance profiles

0.2.10
------
- [Chase] another secgruop fiasco
- [Chase] fix iam issue with role actions

0.2.9
------
- [Chase] better handling of unsupported actions on certain job types

0.2.8
------
- [Chase] allow krampus role name to be user-definable

0.2.7
------
- [Chase] make secgroup delete action actually do something

0.2.6
------
- [Chase] fix disable ebs volume action breaking krampus

0.2.5
------
- [Chase] add ability to pull all s3 perms for when it is a tag-fail job

0.2.4
------
- [Chase] add support for arn whitelisting

0.2.3
------
- [Chase] why doesn't klog also print to stdout instead of making duplicate calls all over the place?

0.2.2
------
- [Chase] extend iam kinder to support roles and groups

0.2.1
------
- [Chase] total rewrite of tasks system(patch bump because no contracts broken)

0.2.0
------
- [Chase] cross-account functionality added
- [Chase] completely re-worked how kinder get their resource or client objects
- [Chase] minor bump to reflect a re-worked sessioning system

0.1.7
------
- [Chase] add ebs module

0.1.6
------
- [Chase] check http resp codes and re-queue tasks with non-200
- [Chase] clean ups

0.1.5
------
- [Chase] add a disable action for multi-az rds instances

0.1.4
------
- [Chase] pointless version inc to satisfy opsbot

0.1.3
------
- [Chase] add security group disable actions for ec2 instances

0.1.2
------
- [Chase] lambda-ify krampus

0.1.1
------
- [Chase] add some basic logging to krampus

0.1.0
------
- [Chase] krampus is born into the world in a swirl of sulfur and fire
