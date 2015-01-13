# -*- coding: utf-8 -*-
############################################################################
#
# Copyright IOPEN Technologies Ltd., 2003, Copyright © 2014 OnlineGroups.net
# and Contributors. All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
############################################################################
#
# This code is based heavily on the MailBoxer product, under the GPL.
#
from __future__ import absolute_import
from cgi import escape
from email import message_from_string
from email.parser import Parser
from inspect import stack as inspect_stack
from logging import getLogger
log = getLogger('XWFMailingList')
from random import random
# import transaction  # See line 1560 below
from zope.component import createObject, getMultiAdapter
from zope.globalrequest import getRequest
from AccessControl import ClassSecurityInfo
from App.class_init import InitializeClass
from OFS.Folder import Folder, manage_addFolder
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from gs.core import to_ascii
from gs.group.member.canpost import (
    IGSPostingUser, Notifier as CanPostNotifier, UnknownEmailNotifier)
from gs.profile.notify import NotifyUser
from gs.group.list.check.interfaces import IGSValidMessage
from gs.group.list.command import process_command, CommandResult
from gs.group.list.sender import Sender
from gs.group.list.email.text import Post
from Products.XWFCore.XWFUtils import (
    removePathsFromFilenames, get_group_by_siteId_and_groupId)
from Products.GSGroup.groupInfo import IGSGroupInfo
from .emailmessage import EmailMessage, IRDBStorageForEmailMessage, \
    RDBFileMetadataStorage
from .queries import MemberQuery, MessageQuery
from .utils import pin, getMailFromRequest
from .MailBoxerTools import lowerList, splitMail
UTF8 = 'utf-8'
DIGEST = 3
null_convert = lambda x: x
# Simple return-Codes for web-callable-methods for the smtp2zope-gate
TRUE = "TRUE"
FALSE = "FALSE"


class XWFMailingList(Folder):
    """ A mailing list implementation, based heavily on the excellent
    Mailboxer product."""
    security = ClassSecurityInfo()
    meta_type = 'XWF Mailing List'
    version = 0.99

    # a tuple of properties that we _don't_ want to inherit from the parent
    # list manager
    mailinglist_properties = ('title',
                              'mailto',
                              'hashkey')

    _properties = (
        {'id': 'title', 'type': 'string', 'mode': 'w'},
        {'id': 'mailto', 'type': 'string', 'mode': 'wd'},
        {'id': 'hashkey', 'type': 'string', 'mode': 'wd'}, )

    # track the checksum of the last email sent. Volatile because we
    # just want a quick short circuit (post ID is checked for uniqueness
    # at the database level anyway)
    _v_last_email_checksum = ''

    def __init__(self, id, title, mailto):
        """ Setup a mailing list with reasonable defaults."""
        self.id = id
        self.title = title
        self.hashkey = str(random())
        self.mailto = mailto

    def valid_property_id(self, id):
        # A modified version of the 'valid_property_id' in the PropertyManager
        # class. This one _doesn't_ check for the existence of the ID,
        # since it might exist in our base class, and we can't remove
        # things from there
        if ((not id or id[:1] == '_') or (id[:3] == 'aq_')
           or (' ' in id) or (escape(id) != id)):
            return False
        return True

    def init_properties(self):
        """ Tidy up the property sheet, since we don't want to control most of
        the properties that have already been defined in the parent
        MailingListManager."""
        delete_properties = filter(lambda x:
                                    x not in self.mailinglist_properties,
                                   self.propertyIds())
        props = []
        for item in self._properties:
            if item['id'] not in delete_properties:
                props.append(item)
            else:
                try:
                    self._delProperty(item['id'])
                except:
                    pass

        self._properties = tuple(props)
        self._p_changed = 1

        return True

    ###
    # Public methods to be called via smtp2zope-gateway
    ##
    security.declareProtected('View', 'manage_mailboxer')

    def manage_mailboxer(self, REQUEST):
        """Default for a all-in-one mailinglist-workflow.

Handles (un)subscription-requests and checks for loops etc & bulks mails to
list. Checks that the message can be processed, checks for an email command,
checks that the person can post, and then processes the email."""
        if self.checkMail(REQUEST):
            return FALSE  # This code predates False...
        # Check for subscription/unsubscription-request
        if self.requestMail(REQUEST):
            return TRUE  # ...and True
        if self.cannotPost(REQUEST):
            return TRUE
        # Process the mail...
        retval = self.processMail(REQUEST)
        return retval

    security.declareProtected('View', 'manage_listboxer')

    def manage_listboxer(self, REQUEST):
        """ Send a mail to all members of the list.

Puts a mail into archive and then bulks it to all members on list. Assumes

* The user can post
* The user is moderated
* The message does not contain a command.

If any of these does not hold (as in, this is an email not a post from the
Web) then ``manage_mailboxer`` should be used."""

        if self.checkMail(REQUEST):
            retval = False
        else:
            retval = self.listMail(REQUEST)
        return retval

    security.declareProtected('View', 'manage_moderateMail')

    def manage_moderateMail(self, REQUEST):
        """ Approves / discards a mail for a moderated list. """
        # TODO: UGLY, UGLY, UGLY!!!
        # --=mpj17=-- This code is command-coupled on the "action"
        #   parameter, so it really needs to be split into two parts: one
        #   for accepting, and one for rejecting the moderated message. In
        #    addition, the moderated member should be informed that the
        #    message has been accepted or rejected.
        action = REQUEST.get('action', '')
        if (REQUEST.get('pin') == pin(self.getValueFor('mailto'),
                                      self.getValueFor('hashkey'))):
            mqueue = self.restrictedTraverse(self.getValueFor('mailqueue'))
            mid = REQUEST.get('mid', '-1')

            if not hasattr(mqueue, mid):
                if action in ['approve', 'discard']:
                    if hasattr(self, "mail_approve"):
                        return self.mail_approve(self, REQUEST,
                                                 msg="MAIL_NOT_FOUND")
                    else:
                        REQUEST.RESPONSE.setHeader(b'Content-type',
                                                   b'text/plain')
                        return "MAIL NOT FOUND! MAYBE THE MAIL WAS ALREADY"\
                            "PROCESSED."
                else:
                    if hasattr(self, "mail_approve"):
                        return self.mail_approve(self, REQUEST,
                                                 msg="MAIL_PENDING")
                    else:
                        REQUEST.RESPONSE.setHeader(b'Content-type',
                                                   b'text/plain')
                        if len(mqueue.objectValues()):
                            return "PENDING MAILS IN QUEUE!"
                        else:
                            return "NO PENDING MAILS IN QUEUE!"

            mail = getattr(mqueue, mid).data
            REQUEST.set('Mail', mail)

            # delete queued mail
            mqueue.manage_delObjects([mid])
            if action == 'approve':
                # relay mail to list
                self.listMail(REQUEST)
                if hasattr(self, "mail_approve"):
                    return self.mail_approve(self, REQUEST,
                                             msg="MAIL_APPROVE")
                else:
                    REQUEST.RESPONSE.setHeader(b'Content-type',
                                               b'text/plain')
                    return "MAIL APPROVED\n\n%s" % mail
            else:
                if hasattr(self, "mail_approve"):
                    return self.mail_approve(self, REQUEST,
                                             msg="MAIL_DISCARD")
                else:
                    REQUEST.RESPONSE.setHeader(b'Content-type',
                                               b'text/plain')
                    return "MAIL DISCARDED\n\n%s" % mail

        if hasattr(self, "mail_approve"):
            return self.mail_approve(self, REQUEST, msg="INVALID_REQUEST")
        else:
            REQUEST.RESPONSE.setHeader('Content-type', 'text/plain')
            return "INVALID REQUEST! Please check your PIN."

    security.declareProtected('Manage properties', 'setValueFor')

    def setValueFor(self, key, value):
        '''Universal getter / setter for retrieving / storing properties or
calling appropriate handlers in ZODB'''
        # We look for the property locally, then assume it is in the parent
        # We don't try to access the property directly, because it might be
        # defined in our base class, which we can't remove
        if self.aq_inner.hasProperty(key):
            prop_loc = self.aq_inner
        else:
            prop_loc = self.aq_parent

        # Use manage_changeProperties as default for setting properties
        prop_loc.manage_changeProperties({key: value})

    security.declareProtected('Manage properties', 'get_memberUserObjects')

    def get_memberUserObjects(self, ids_only=False):
        """ Get the user objects corresponding to the membership list,
assuming we can."""
        member_groups = self.getProperty('member_groups',
                                         ['%s_member' % self.listId()])
        uids = []
        for gid in member_groups:
            group = self.acl_users.getGroupById(gid)
            uids += group.getUsers()

        if ids_only:
            retval = uids
        else:
            m = 'Getting all the user-objects in "%s"' % self.listId()
            log.warning(m)
            s = inspect_stack()[:2]
            log.warning(s)
            users = []
            for uid in uids:
                user = self.acl_users.getUser(uid)
                if user:
                    users.append(user)
            retval = users
        return retval

    security.declareProtected('Manage properties',
                              'get_moderatedUserObjects')

    def get_moderatedUserObjects(self, ids_only=False):
        """ Get the user objects corresponding to the moderated list,
assuming we can."""
        member_groups = self.getProperty('moderated_groups', [])
        uids = []
        for gid in member_groups:
            group = self.acl_users.getGroupById(gid)
            uids += group.getUsers()

        uids += self.getProperty('moderated_members', [])

        if ids_only:
            return uids

        # AM: Avoid nastiness associated with empty strings and null users
        users = filter(lambda x: x, [ self.acl_users.getUser(uid) for uid in uids if uid ])

        return users

    security.declareProtected('Manage properties', 'get_moderatorUserObjects')
    def get_moderatorUserObjects(self, ids_only=False):
        """ Get the user objects corresponding to the moderator, assuming we can.

        """
        member_groups = self.getProperty('moderator_groups', [])
        uids = []
        for gid in member_groups:
            group = self.acl_users.getGroupById(gid)
            uids += group.getUsers()

        uids += self.getProperty('moderator_members', [])

        if ids_only:
            return uids

        # AM: Avoid nastiness associated with empty strings and null users
        users = filter(lambda x: x, [ self.acl_users.getUser(uid) for uid in uids if uid ])

        return users

    security.declareProtected('Access contents information', 'getValueFor')

    def getValueFor(self, key):
        """ getting the maillist and moderatedlist is a special case,
        working in with the XWFT group framework."""

        if key in ('digestmaillist', 'maillist', 'moderator',
                   'moderatedlist'):
            maillist = []
            if key in ('digestmaillist', 'maillist'):
                maillist_script = getattr(self, 'maillist_members', None)
            elif key in ('moderator',):
                maillist_script = None
                maillist = self.aq_inner.getProperty('moderator', [])
                if not maillist:
                    maillist = self.aq_parent.getProperty('moderator', [])
            elif key in ('moderatedlist',):
                maillist_script = None
                maillist = self.aq_inner.getProperty('moderatedlist', [])
                if not maillist:
                    maillist = self.aq_parent.getProperty('moderatedlist',
                                                          [])
            maillist = list(maillist)

            # look for a maillist script
            if maillist_script:
                return maillist_script()

            try:
                memberQuery = MemberQuery(self)
                addresses = []
                if key == 'maillist':
                    addresses = memberQuery.get_member_addresses(
                        self.getProperty('siteId'), self.getId(),
                        self.get_memberUserObjects)
                elif key == 'digestmaillist':
                    addresses = memberQuery.get_digest_addresses(
                        self.getProperty('siteId'), self.getId(),
                        self.get_memberUserObjects)
                elif key == 'moderator':
                    addresses = memberQuery.get_member_addresses(
                        self.getProperty('siteId'), self.getId(),
                        self.get_moderatorUserObjects,
                        preferred_only=False, process_settings=False)
                elif key == 'moderatedlist':
                    addresses = memberQuery.get_member_addresses(
                        self.getProperty('siteId'), self.getId(),
                        self.get_moderatedUserObjects,
                        preferred_only=False, process_settings=False)
                for email in addresses:
                    email = email.strip()
                    if email and email not in maillist:
                        maillist.append(email)

            except Exception as x:
                m = '%s (%s): A problem was experienced while getting '\
                    'values\n\n%s'
                msg = m % (self.getProperty('title', ''), self.listId(), x)
                log.error(to_ascii(msg))
                maillist = None

            # last ditch effort
            if maillist is None:
                maillist = self.getProperty('maillist', [])

            return maillist

        # Again, look for the property locally, then assume it is in the
        # parent
        if self.aq_inner.hasProperty(key):
            return self.aq_inner.getProperty(key)
        else:
            return self.aq_parent.getProperty(key)

    def listId(self):
        """ Mostly intended to be tracked by the catalog, to allow us to
        track which email belongs to which list."""
        return self.getId()

    def listMail(self, REQUEST):
        '''Store a message and send it. Shifted from MailBoxer till
reintegration project'''

        # Send a mail to all members of the list.
        mailString = getMailFromRequest(REQUEST)
        msg = EmailMessage(
            mailString,
            list_title=self.getProperty('title', ''),
            group_id=self.getId(),
            site_id=self.getProperty('siteId', ''),
            sender_id_cb=self.get_mailUserId)
        # TODO: Audit
        m = 'listMail: Processing message in group "%s", post id "%s" '\
            'from <%s>' % (self.getId(), msg.post_id, msg.sender)
        log.info(m)

        # store mail in the archive? get context for the mail...
        post_id = msg.post_id
        (post_id, file_ids) = self.manage_addMail(msg)

        siteId = self.getProperty('siteId', '')
        groupId = self.getId()
        site = getattr(self.site_root().Content, siteId)
        groupInfo = createObject('groupserver.GroupInfo', site, groupId)
        r = getRequest()  # The actual Zope request; FIXME

        newMail = "%s\r\n\r\nDropped text." % (msg.headers)
        e = Parser().parsestr(newMail, headersonly=True)
        p = Post(groupInfo.groupObj.messages, groupInfo, post_id)
        textPage = getMultiAdapter((p, r), name='text')
        textBody = textPage()
        e.set_payload(textBody, 'utf-8')
        sender = Sender(groupInfo.groupObj, r)
        sender.send(e)

        return post_id

    def processMail(self, REQUEST):
        '''Do all the moderation processing, then list the message by
calling ``self.listMail``'''
        # Zeroth sanity check ... herein lies only madness.
        m = 'processMail: list (%s)' % self.getId()
        log.info(m)

        # Checks if member is allowed to send a mail to list
        mailString = getMailFromRequest(REQUEST)

        msg = EmailMessage(
            mailString, list_title=self.getProperty('title', ''),
            group_id=self.getId(),
            site_id=self.getProperty('siteId', ''),
            sender_id_cb=self.get_mailUserId)

        (header, body) = splitMail(mailString)

        # First sanity check ... have we already archived this message?
        messageQuery = MessageQuery(self)
        if messageQuery.post(msg.post_id):
            m = '%s (%s): Post from <%s> has already been archived with '\
                'post ID %s' % (self.getProperty('title', ''), self.getId(),
                                msg.sender, msg.post_id)
            log.info(m)
            return "Message already archived"

        # get lower case email for comparisons
        email = msg.sender

        # Get moderators
        moderatorlist = lowerList(self.getValueFor('moderator'))
        if self.getValueFor('moderated') and (email not in moderatorlist):
            # message to a moderated list... relay all mails from a
            # moderator
            m = '%s (%s): relaying message %s from moderator <%s>' %\
                (self.getProperty('title', ''), self.getId(),
                 msg.post_id, email)
            log.info(m)
            modresult = self.processModeration(REQUEST)
            if modresult:
                return modresult
            # --=mpj17=-- No else?

        retval = self.listMail(REQUEST)
        return retval

    def processModeration(self, REQUEST):
        # a hook for handling the moderation stage of processing the email
        m = '%s (%s) Processing moderation' %\
            (self.getProperty('title', ''), self.getId())
        log.info(m)

        mailString = getMailFromRequest(REQUEST)

        # TODO: erradicate splitMail usage
        (header, body) = splitMail(mailString)

        msg = EmailMessage(
            mailString, list_title=self.getProperty('title', ''),
            group_id=self.getId(), site_id=self.getProperty('siteId', ''),
            sender_id_cb=self.get_mailUserId)

        # Get members
        memberlist = lowerList(self.getValueFor('maillist'))

        # Get individually moderated members
        moderatedlist = filter(None,
                               lowerList(self.getValueFor('moderatedlist') or []))

        unclosed = self.getValueFor('unclosed')

        # if we have a moderated list we _only_ moderate those individual
        # members, no others.
        moderate = False
        if len(moderatedlist):
            m = '%s (%s) is a moderated list; hunting for individual '\
                'moderation' % (self.getProperty('title', ''), self.getId())
            log.info(m)
            if msg.sender in moderatedlist:
                m = '%s (%s): found individual moderation <%s> %s' % \
                    (self.getProperty('title', ''), self.getId(),
                     msg.sender, moderatedlist)
                log.info(m)
                moderate = True
            else:
                m = '%s (%s): not moderating <%s>' % \
                    (self.getProperty('title', ''), self.getId(),
                     msg.sender)
                log.info(m)

        elif (msg.sender in memberlist) or unclosed:
            # --=mpj17=-- If we are here, then we are moderating *everyone*
            moderate = True
        else:
            self.mail_reply(self, REQUEST, mailString)
            return msg.sender

        if moderate:
            mqueue = getattr(self.aq_explicit, 'mqueue', None)

            # create a default-mailqueue if the traverse to mailqueue
            # fails...
            if not mqueue:
                self.setValueFor('mailqueue', 'mqueue')
                self.manage_addFolder('mqueue', 'Moderated Mail Queue')
                mqueue = self.mqueue

            title = "%s / %s" % (msg.subject, msg.get('from'))

            mqueue.manage_addFile(msg.post_id, title=title, file=mailString,
                                  content_type='text/plain')

            # --=mpj17=-- Changed to use the GroupServer message
            # notification framework. Instead of a single call to the
            # "mail_moderator" template, two calls are made to notify the
            # two users.

            # self.mail_moderator(self, REQUEST, mid=msg.post_id,
            #                    pin=pin, mail=header, body=body)

            #
            # FIXME: Moderation *totally* broken for the unclosed case
            #
            moderatedUser = self.acl_users.getUser(msg.sender_id)
            assert moderatedUser, 'Moderated user %s not found' % msg.sender_id

            moderators = self.get_moderatorUserObjects()
            for moderator in moderators:
                nDict = {
                    'mailingList': self,
                    'pin': pin(self.getValueFor('mailto'),
                               self.getValueFor('hashkey')),
                    'moderatedUserAddress': msg.sender,
                    'groupId': self.getId(),
                    'groupName': self.title,
                    'groupEmail': self.getValueFor('mailto'),
                    'subject': msg.subject,
                    'mid': msg.post_id,
                    'body': msg.body,
                    'absolute_url': self.absolute_url(),
                    'moderatedUserId': msg.sender_id,
                    'moderatedUserName': moderatedUser.getProperty('fn','')}
                notify = NotifyUser(moderator)
                notify.send_notification('mail_moderator', 'default',
                    n_dict=nDict)

            nDict = {'mailingList': self,
              'pin': pin(self.getValueFor('mailto'),
                          self.getValueFor('hashkey')),
              'moderatedUserAddress': msg.sender,
              'groupName': self.title,
              'groupEmail': self.getValueFor('mailto'),
              'subject': msg.subject,
              'mid': msg.post_id,
              'body': msg.body,
              'absolute_url': self.absolute_url(),
              'moderatedUserName': moderatedUser.getProperty('fn','')}

            notify = NotifyUser(moderatedUser)
            notify.send_notification('mail_moderated_user',
              'default', n_dict=nDict)

            return msg.sender

    security.declareProtected('Add Folders', 'manage_addMail')

    def manage_addMail(self, msg):
        """ Store mail & attachments in a folder and return it."""
        ids = []
        for attachment in msg.attachments:
            if ((attachment['filename'] == '')
                    and (attachment['subtype'] == 'plain')):
                # We definately don't want to save the plain text body
                # again!
                pass
            elif ((attachment['filename'] == '')
                    and (attachment['subtype'] == 'html')):
                # We might want to do something with the HTML body some day,
                # but we archive the HTML body here, as it suggests in the
                # log message. The HTML body is archived along with the
                # plain text body.
                m = '%s (%s): archiving HTML message.' % \
                    (self.getProperty('title'), self.getId())
                log.info(m)
            elif attachment['contentid'] and (attachment['filename'] == ''):
                # TODO: What do we want to do with these? They are typically
                # part of an HTML message, for example the images, but what
                # should we do with them once we've stripped them?
                m = '%s (%s): stripped, but not archiving %s attachment '\
                    '%s; it appears to be part of an HTML message.' % \
                    (self.getProperty('title'), self.getId(),
                     attachment['maintype'], attachment['filename'])
                log.info(m)
            elif attachment['length'] <= 0:
                # Empty attachment. Kinda pointless archiving this!
                m = '%s (%s): stripped, but not archiving %s attachment '\
                    '%s; attachment was of zero size.' % \
                    (self.getProperty('title'), self.getId(),
                     attachment['maintype'], attachment['filename'])
                log.warn(m)
            else:
                m = '%s (%s): stripped and archiving %s attachment %s' %\
                    (self.getProperty('title'), self.getId(),
                     attachment['maintype'], attachment['filename'])
                log.info(m)

                nid = self.addGSFile(attachment['filename'], msg.subject,
                                     msg.sender_id, attachment['payload'],
                                     attachment['mimetype'])
                ids.append(nid)

        msgstorage = IRDBStorageForEmailMessage(msg)
        msgstorage.insert()

        filemetadatastorage = RDBFileMetadataStorage(self, msg, ids)
        filemetadatastorage.insert()

        return (msg.post_id, ids)

    def checkMail(self, REQUEST):
        '''Check the email for loops and spam.

        The work of this method is mostly done by the gs.group.list.check
        product.

        RETURNS
            * Unicode if the message should *not* be processed, or
            * None if the message *should* be processed.

        SIDE EFFECTS
            If the user can post, "self._v_last_email_checksum" is set to
            the ID of the message, which is calculated by
            "emailmessage.EmailMessage".'''

        groupId = self.getId()
        siteId = self.getProperty('siteId', '')
        site = getattr(self.site_root().Content, siteId)
        groupInfo = createObject('groupserver.GroupInfo', site, groupId)
        mailString = getMailFromRequest(REQUEST)

        # --=mpj17=-- Because checkMail is the first method called with the
        # email message it is far more cautious about checking the validity
        # of the message string.
        try:
            msg = EmailMessage(mailString,
                               list_title=self.getProperty('title', ''),
                               group_id=groupId,
                               site_id=siteId,
                               sender_id_cb=self.get_mailUserId)
        except ValueError:
            m = u'Could not create an email message in the group "{0}" '\
                u'with the mail-string starting with\n{1}'
            logMsg = m.format(groupId, mailString[:256])
            log.error(logMsg)
            raise
        try:
            m = u'checkMail: {0} ({1}) checking message from <{2}>'
            logMsg = m.format(groupInfo.name, groupInfo.id, msg.sender)
            log.info(logMsg)
        except AttributeError:
            m = u'checkMail: problem checking message to "{0}" with the '\
                u'mail-string starting with\n{1}'
            logMsg = m.format(groupId, mailString[:256])
            log.error(logMsg)
            raise

        ivm = getMultiAdapter((groupInfo.groupObj, msg), IGSValidMessage)
        if ivm.validMessage:
            m = u'checkMail: {0} ({1}) message from <{2}> checks ok'
            logMsg = m.format(groupInfo.name, groupInfo.id, msg.sender)
            log.info(logMsg)
            # Checksum to ensure we are not in a tight loop.
            # --=mpj17=-- Is this in the right place?
            self._v_last_email_checksum = msg.post_id
            retval = None  # Oddly, this is the success value
        else:
            retval = ivm.status
            m = u'checkMail: failed check. status {0}\n{1}'
            logMsg = m.format(ivm.statusNum, ivm.status)
            log.warn(logMsg)

        return retval

    def requestMail(self, REQUEST):
        'Handle the email commands'
        mailString = getMailFromRequest(REQUEST)

        msg = EmailMessage(mailString,
                           list_title=self.getProperty('title', ''),
                           group_id=self.getId(),
                           site_id=self.getProperty('siteId', ''),
                           sender_id_cb=self.get_mailUserId)
        # get subject
        # get email-address
        email = msg.sender

        siteId = self.getProperty('siteId', '')
        groupId = self.getId()
        site = getattr(self.site_root().Content, siteId)
        groupInfo = createObject('groupserver.GroupInfo', site, groupId)
        r = process_command(groupInfo.groupObj, mailString, REQUEST)
        if r == CommandResult.commandStop:
            return email

    def cannotPost(self, REQUEST):
        mailString = getMailFromRequest(REQUEST)
        groupId = self.getId()
        siteId = self.getProperty('siteId', '')

        msg = EmailMessage(mailString,
                           list_title=self.getProperty('title', ''),
                           group_id=groupId,
                           site_id=siteId,
                           sender_id_cb=self.get_mailUserId)
        userInfo = createObject('groupserver.UserFromId',
                                self.site_root(), msg.sender_id)
        site = getattr(self.site_root().Content, siteId)
        groupInfo = createObject('groupserver.GroupInfo', site, groupId)
        insts = (groupInfo.groupObj, userInfo)
        postingInfo = getMultiAdapter(insts, IGSPostingUser)
        if not(postingInfo.canPost) and not(userInfo.anonymous):
            message = '%s (%s): %s' % (userInfo.name, userInfo.id,
                                       postingInfo.status)
            log.warning(message)
            notifier = CanPostNotifier(groupInfo.groupObj, REQUEST)
            siteInfo = createObject('groupserver.SiteInfo', site)
            notifier.notify(userInfo, siteInfo, groupInfo,
                            mailString)
            return message
        elif not(postingInfo.canPost) and userInfo.anonymous:
            # if all previous tests fail, it must be an unknown sender.
            m = 'cannotPost %s (%s): Mail received from unknown sender '\
                '<%s>'
            message = m % (self.getProperty('title', ''), groupId,
                           msg.sender)
            log.info(message)
            self.mail_reply(self, REQUEST, mailString)
            return message

        # If here then everything is fine.

    def get_mailUserId(self, addr):
        """ From the email address, get the user's ID.

        """
        return self.acl_users.get_userIdByEmail(addr) or ''

    security.declarePrivate('mail_reply')

    def mail_reply(self, context, REQUEST, message):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default. """
        # The email message that is sent to unknown email addresses
        siteId = self.getProperty('siteId', '')
        groupId = self.getId()
        group = get_group_by_siteId_and_groupId(self, siteId, groupId)
        groupInfo = IGSGroupInfo(group)
        emailAddress = message_from_string(message)['From']

        notifier = UnknownEmailNotifier(group, REQUEST)
        notifier.notify(emailAddress, message)
        m = '%s (%s) sent Unknown Email Address notification to <%s>' % \
            (groupInfo.name, groupInfo.id, emailAddress)
        log.info(m)

    def addGSFile(self, title, topic, creator, data, content_type):
        """ Adds an attachment as a file.

        """
        # TODO: group ID should be more robust
        group_id = self.getId()
        storage = self.FileLibrary2.get_fileStorage()
        fileId = storage.add_file(data)
        fileObj = storage.get_file(fileId)
        fixedTitle = removePathsFromFilenames(title)
        fileObj.manage_changeProperties(
            content_type=content_type, title=fixedTitle,
            tags=['attachment'], group_ids=[group_id],
            dc_creator=creator, topic=topic)
        fileObj.reindex_file()
        #
        # Commit the ZODB transaction -- this basically makes it impossible
        # for us to rollback, but since our RDB transactions won't be rolled
        # back anyway, we do this so we don't have dangling metadata.
        #
        # --=mpj17=-- But it caused death on my local box. So I am
        # experimenting with commenting it out.
        # transaction.commit()
        return fileId

manage_addXWFMailingListForm = PageTemplateFile(
    'management/manage_addXWFMailingListForm.zpt',
    globals(),
    __name__='manage_addXWFMailingListForm')


def manage_addXWFMailingList(self, id, mailto, title='Mailing List',
                             REQUEST=None):
    """ Add an XWFMailingList to a container.

    """
    ob = XWFMailingList(id, title, mailto)
    self._setObject(id, ob)
    ob = getattr(self, id)
    ob.init_properties()
    manage_addFolder(ob, 'archive', 'mailing list archives')

    if REQUEST is not None:
        return self.manage_main(self, REQUEST)

InitializeClass(XWFMailingList)


def initialize(context):
    context.registerClass(
        XWFMailingList,
        permission="Add XWF MailingList",
        constructors=(manage_addXWFMailingListForm,
                      manage_addXWFMailingList),
        )
