==================================
``Products.XWFMailingListManager``
==================================
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The mailing-list component of a GroupServer group
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:Author: `Michael JasonSmith`_
:Contact: Michael JasonSmith <mpj17@onlinegroups.net>
:Date: 2017-01-23
:Organization: `GroupServer.org`_
:Copyright: This document is licensed under a
  `Creative Commons Attribution-Share Alike 4.0 International License`_
  by `OnlineGroups.Net`_.

Introduction
============

This product provides the core mailing-list functionality for
GroupServer_. It provides the `mailing list manager`_ to find
lists, and the `mailing list`_ to coordinate, or mediate, between
the various ``gs.group.list.*`` products.

Mailing list manager
====================

The mailing list *manager,* which gives this product its name,
finds a `mailing list`_ when provided with an email address. The
``Products.XWFMailingListManager.XWFMailingListManager`` class
does little, and will do less once the ``group_email`` table has
been created [#groupEmail]_.

Mailing list
============

The ``Products.XWFMailingListManager.XWFMailingList`` class adds
posts to a group and sends the email out to all the members. It
uses the following products to provide most of the functionality.

``gs.group.list.base``:
  Converts the incoming message into Unicode plain-text body, a
  Unicode HTML-body, and a list of attachments.
  <https://github.com/groupserver/gs.group.list.base>

``gs.group.list.check``:
  Checks to see if the message should be processed *at* *all.*
  <https://github.com/groupserver/gs.group.list.check>

``gs.group.list.command``:
  Processes the email-commands, such as ``Subscribe`` and
  ``Digest on``.
  <https://github.com/groupserver/gs.group.list.command>

``gs.group.member.canpost``:
  Checks to see if the group member is allowed to post.
  <https://github.com/groupserver/gs.group.member.canpost>

``gs.group.list.store``:
  Stores the message, and files, in the PostgreSQL database.
  <https://github.com/groupserver/gs.group.list.store>

``gs.group.list.email.text``
  Produces a plain-text version the stored message, reformatted
  with a prelude, a list of links to files, and a footer.
  <https://github.com/groupserver/gs.group.list.email.text>

``gs.group.list.sender``
  Performs the necessary modifications of the headers of the
  message, and sends the message out using SMTP [#smtp]_.
  <https://github.com/groupserver/gs.group.list.sender>

:Note: There is no ``gs.group.list.email.html`` product… `yet`_.

.. _yet: https://redmine.iopen.net/issues/683

The main entry-point into the mailing list code is the
``manage_mailboxer`` method, which is used when an email comes
into the system [#add]_.  The ``manage_listboxer`` method is
similar, but it is used when someone posts from the Web (so it
skips much if the checking, which it presumes has already
happened).

Moderation
----------

The code for moderating a post is also contained within the
``Products.XWFMailingListManager.XWFMailingList`` class. It
works, presumably, but it is fragile and lacks unit tests. The
way moderation works is as follows:

* A post comes into the mailing list. It is checked to see if the
  member can post, as usual.

* The member is then checked to see if he or she is in the
  ``moderated`` list.

  + If the member is moderated then the post is stored in the
    ``mqueue`` folder of the mailing list object in the ZODB, and
    everyone informed of the fact.
  + If the member is unmoderated then the message is sent on.

* A moderator then responds to the moderation by making an HTTP
  ``GET`` request for ``manage_moderateMail``. This either

  + Deletes the message, or 
  + Sends the queued message through the message-processing queue
    again.

`We are not proud`_ of this code.

.. _We are not proud: https://redmine.iopen.net/issues/249

Acknowledgements
================

The mailing list code in GroupServer_ code was originally based
on ``MailBoxer``, by Maik Jablonski. It provided mailing lists to
Zope_, but lacked a Web interface. The ``MailBoxer`` code has
been replaced, often many times, but references are still seen,
and some of the API is similar.

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
.. _Zope: http://zope.org/
.. [#smtp] The ``gs.email`` product is used to send the messages
           out using SMTP.
           <https://github.com/groupserver/gs.email>
.. [#groupEmail] See `Feature 388`_ Create Group Email Table
.. _Feature 388: https://redmine.iopen.net/issues/388
.. [#add] See the ``gs.group.messages.add`` product
          <https://github.com/groupserver/gs.group.messages.add.base>
