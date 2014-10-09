==================================
``Products.XWFMailingListManager``
==================================
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The mailing-list component for a GroupServer group
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:Author: `Michael JasonSmith`_
:Contact: Michael JasonSmith <mpj17@onlinegroups.net>
:Date: 2014-10-09
:Organization: `GroupServer.org`_
:Copyright: This document is licensed under a
  `Creative Commons Attribution-Share Alike 4.0 International License`_
  by `OnlineGroups.Net`_.

Introduction
============

This product contains the *ugliest* code in serious use in
GroupServer_. Which is a bit ironic, as it provides the core
mailing-list functionality. It is *slowly* being dismantled and
its functionality farmed out to other products (see `Issue
387`_).

The core class, which adds posts to a group and sends the email
out to all the group members, is
``Products.XWFMailingListManager.XWFMailingList``. The
mailing-list *manager* itself is a subclass of folder that finds
a mailing list, given an email address. 

This code is based on the even *older* ``MailBoxer`` code, which
provided mailing lists to Zope, but without a web
interface. References to ``MailBoxer`` are still scattered in the
code.

Resources
=========

- Code repository: https://github.com/groupserver/Products.XWFMailingListManager
- Questions and comments to http://groupserver.org/groups/development
- Report bugs at https://redmine.iopen.net/projects/groupserver

.. _GroupServer: http://groupserver.org/
.. _GroupServer.org: http://groupserver.org/
.. _OnlineGroups.Net: https://onlinegroups.net
.. _Michael JasonSmith: http://groupserver.org/p/mpj17
.. _Creative Commons Attribution-Share Alike 4.0 International License:
    http://creativecommons.org/licenses/by-sa/4.0/
.. _gs.group.member.base: https://github.com/groupserver/gs.group.member.base
.. _Issue 387: https://redmine.iopen.net/issues/387
