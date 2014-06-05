# -*- coding: utf-8 -*-
##############################################################################
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
##############################################################################
#
# This code is based heavily on the MailBoxer product, under the GPL.
#
from __future__ import absolute_import
from cgi import escape
from email import message_from_string
from email.utils import formataddr
from email.Header import Header
from inspect import stack as inspect_stack
from logging import getLogger
log = getLogger('XWFMailingList')
from random import random
from re import search
from rfc822 import AddressList
# import transaction  # See line 1560 below
from zope.component import createObject, getMultiAdapter
from AccessControl import ClassSecurityInfo
from App.class_init import InitializeClass
from OFS.Folder import Folder, manage_addFolder
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from gs.core import to_ascii, to_unicode_or_bust
from gs.cache import cache
from gs.dmarc import lookup_receiver_policy, ReceiverPolicy
from gs.email import send_email
from gs.group.member.canpost import IGSPostingUser, \
    Notifier as CanPostNotifier, UnknownEmailNotifier
from gs.group.member.leave.leaver import GroupLeaver
from gs.profile.notify import NotifyUser
from Products.XWFCore.XWFUtils import removePathsFromFilenames, getOption, \
    get_group_by_siteId_and_groupId
from Products.CustomUserFolder.userinfo import IGSUserInfo
from Products.GSGroupMember.groupmembership import join_group
from Products.GSProfile.utils import create_user_from_email
from Products.GSGroup.groupInfo import IGSGroupInfo
from .emailmessage import EmailMessage, IRDBStorageForEmailMessage, \
    RDBFileMetadataStorage, strip_subject
from .queries import MemberQuery, MessageQuery
from .utils import check_for_commands, pin, getMailFromRequest
from .MailBoxerTools import lowerList, parseaddr, splitMail
UTF8 = 'utf-8'
DIGEST = 3
null_convert = lambda x: x
# Simple return-Codes for web-callable-methods for the smtp2zope-gate
TRUE = "TRUE"
FALSE = "FALSE"


class XWFMailingList(Folder):
    """ A mailing list implementation, based heavily on the excellent Mailboxer
    product.

    """
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
        {'id': 'hashkey', 'type': 'string', 'mode': 'wd'},
       )

    # track the checksum of the last email sent. Volatile because we
    # just want a quick short circuit (post ID is checked for uniqueness
    # at the database level anyway)
    _v_last_email_checksum = ''

    def __init__(self, id, title, mailto):
        """ Setup a mailing list with reasonable defaults.

        """
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
        MailingListManager.

        """
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
        """ Default for a all-in-one mailinglist-workflow.

            Handles (un)subscription-requests and
            checks for loops etc & bulks mails to list.
        """
        if self.checkMail(REQUEST):
            return FALSE
        # Check for subscription/unsubscription-request
        if self.requestMail(REQUEST):
            return TRUE
        # Process the mail...
        retval = self.processMail(REQUEST)
        return retval

    security.declareProtected('View', 'manage_requestboxer')
    def manage_requestboxer(self, REQUEST):
        """ Handles un-/subscribe-requests.

            Check mails for (un)subscription-requests,
            returns (un)subscribed adress if request
            was successful.
        """

        if self.checkMail(REQUEST):
            return FALSE

        # Check for subscription/unsubscription-request
        self.requestMail(REQUEST)
        return TRUE

    security.declareProtected('View', 'manage_listboxer')
    def manage_listboxer(self, REQUEST):
        """ Send a mail to all members of the list.

            Puts a mail into archive and then bulks
            it to all members on list.
        """

        if self.checkMail(REQUEST):
            retval = False
        else:
            retval = self.listMail(REQUEST)
        return retval

    security.declareProtected('View', 'manage_inboxer')
    def manage_inboxer(self, REQUEST):
        """ Wrapper to mail directly into archive.

            This is just a wrapper method if you
            want to use MailBoxer as mailarchive-system.
        """
        # Shifted from XWFMailingListManager till re-integration project
        if self.checkMail(REQUEST):
            return FALSE

        mailString = getMailFromRequest(REQUEST)
        msg = EmailMessage(mailString, list_title=self.getProperty('title', ''),
                                       group_id=self.getId(),
                                       site_id=self.getProperty('siteId', ''),
                                       sender_id_cb=self.get_mailUserId)

        self.manage_addMail(msg)
        return TRUE

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
                        REQUEST.RESPONSE.setHeader('Content-type',
                                                    'text/plain')
                        return "MAIL NOT FOUND! MAYBE THE MAIL WAS ALREADY"\
                            "PROCESSED."
                else:
                    if hasattr(self, "mail_approve"):
                        return self.mail_approve(self, REQUEST,
                                                msg="MAIL_PENDING")
                    else:
                        REQUEST.RESPONSE.setHeader('Content-type',
                                                    'text/plain')
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
                    return self.mail_approve(self, REQUEST, msg="MAIL_APPROVE")
                else:
                    REQUEST.RESPONSE.setHeader('Content-type', 'text/plain')
                    return "MAIL APPROVED\n\n%s" % mail
            else:
                if hasattr(self, "mail_approve"):
                    return self.mail_approve(self, REQUEST, msg="MAIL_DISCARD")
                else:
                    REQUEST.RESPONSE.setHeader('Content-type', 'text/plain')
                    return "MAIL DISCARDED\n\n%s" % mail

        if hasattr(self, "mail_approve"):
            return self.mail_approve(self, REQUEST, msg="INVALID_REQUEST")
        else:
            REQUEST.RESPONSE.setHeader('Content-type', 'text/plain')
            return "INVALID REQUEST! Please check your PIN."


    ###
    # Universal getter / setter for retrieving / storing properties
    # or calling appropriate handlers in ZODB
    ##
    security.declareProtected('Manage properties', 'setValueFor')
    def setValueFor(self, key, value):
        # We look for the property locally, then assume it is in the parent
        # We don't try to access the property directly, because it might be
        # defined in our base class, which we can't remove
        if self.aq_inner.hasProperty(key):
            prop_loc = self.aq_inner
        else:
            prop_loc = self.aq_parent

        # Use manage_changeProperties as default for setting properties
        prop_loc.manage_changeProperties({key:value})

    security.declareProtected('Manage properties', 'get_memberUserObjects')
    def get_memberUserObjects(self, ids_only=False):
        """ Get the user objects corresponding to the membership list, assuming we can.

        """
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

    security.declareProtected('Manage properties', 'get_memberUserCount')
    def get_memberUserCount(self):
        """ Get a count of the number of users corresponding to the
            membership list, assuming we can.

        """
        # TODO: --=mpj17=-- Do we need this method?
        member_groups = self.getProperty('member_groups', ['%s_member' % self.listId()])
        uids = []
        for gid in member_groups:
            group = self.acl_users.getGroupById(gid)
            uids += group.getUsers()

        return len(uids)

    security.declareProtected('Manage properties', 'get_moderatedUserObjects')
    def get_moderatedUserObjects(self, ids_only=False):
        """ Get the user objects corresponding to the moderated list, assuming we can.

        """
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
        """ getting the maillist and moderatedlist is a special case, working
            in with the XWFT group framework.

        """

        if key in ('digestmaillist', 'maillist', 'moderator', 'moderatedlist',
                    'mailinlist'):
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
                    maillist = self.aq_parent.getProperty('moderatedlist', [])
            else:
                maillist_script = getattr(self, 'mailinlist_members', None)

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
                elif key == 'mailinlist':
                    addresses = memberQuery.get_member_addresses(
                                self.getProperty('siteId'), self.getId(),
                                self.get_memberUserObjects,
                                preferred_only=False, process_settings=False)
                for email in addresses:
                    email = email.strip()
                    if email and email not in maillist:
                        maillist.append(email)

            except Exception as x:
                m = '%s (%s): A problem was experienced while getting values'\
                  '\n\n%s'
                msg = m % (self.getProperty('title', ''), self.listId(), x)
                log.error(to_ascii(msg))
                maillist = None

            # last ditch effort
            if maillist is None:
                maillist = self.getProperty('maillist', [])

            return maillist

        # Again, look for the property locally, then assume it is in the parent
        if self.aq_inner.hasProperty(key):
            return self.aq_inner.getProperty(key)
        else:
            return self.aq_parent.getProperty(key)

    def listId(self):
        """ Mostly intended to be tracked by the catalog, to allow us to
        track which email belongs to which list.

        """
        return self.getId()

    def create_mailableSubject(self, subject, include_listid=1):
        """ A helper method for tidying up the mailing list subject for
        remailing. """
        # there is an assumption that if we're including a listid we should
        # strip any existing listid reference
        if include_listid:
            # this *must* be a string, it cannot be unicode
            list_title = str(self.getValueFor('title'))
        else:
            list_title = ''

        retval = strip_subject(subject, list_title, False)

        is_reply = 0
        if (retval.lower().find('re:', 0, 3)) == 0 and (len(retval) > 3):
            retval = retval[3:].strip()
            is_reply = 1

        re_string = '%s' % (is_reply and 'Re: ' or '')
        if include_listid:
            retval = '%s[%s] %s' % (re_string, list_title, retval)
        else:
            retval = '%s%s' % (re_string, retval)
        return retval

    @staticmethod
    @cache('Products.XWFMailingList.dmarc', lambda h: h, 7 * 60)
    def get_dmarc_policy_for_host(host):
        retval = lookup_receiver_policy(host)
        return retval

    def listMail(self, REQUEST):
        # Shifted from MailBoxer till reintegration project

        # Send a mail to all members of the list.
        mailString = getMailFromRequest(REQUEST)
        msg = EmailMessage(mailString,
                list_title=self.getProperty('title', ''),
                group_id=self.getId(), site_id=self.getProperty('siteId', ''),
                sender_id_cb=self.get_mailUserId)
        # TODO: Audit
        m = 'listMail: Processing message in group "%s", post id "%s" from '\
            '<%s>' % (self.getId(), msg.post_id, msg.sender)
        log.info(m)

        # store mail in the archive? get context for the mail...
        post_id = msg.post_id
        (post_id, file_ids) = self.manage_addMail(msg)

        # The custom header is actually capable of replacing the top of the
        # message, for example with a banner, so we need to parse it again
        headers = {}
        for item in msg.message.items():
            headers[item[0].lower()] = item[1]

        mail_header = self.mail_header(self,
                                       REQUEST,
                                       getValueFor=self.getValueFor,
                                       title=self.getValueFor('title'),
                                       mail=headers,
                                       body=msg.body,
                                       file_ids=file_ids,
                                       post_id=post_id)

        # The mail header needs to be committed to a  bytestream,
        # not just a unicode object.
        mail_header = mail_header.encode('utf-8', 'ignore').strip()

        customHeader = EmailMessage(mail_header)

        # If customBody is not empty, use it as new mailBody, and we need to
        # fetch it before any other changes are made, since changing the
        # header can affect the way the body is decoded
        if customHeader.body.strip():
            body = customHeader.body
        else:
            body = msg.body

        # unlike the header, the footer is just a footer
        customFooter = self.mail_footer(self, REQUEST,
                                              getValueFor=self.getValueFor,
                                              title=self.getValueFor('title'),
                                              mail=headers,
                                              body=msg.body,
                                              file_ids=file_ids,
                                              post_id=post_id).strip()

        for hdr in customHeader.message.keys():
            if customHeader.message[hdr].strip():
                if hdr in msg.message:
                    msg.message.replace_header(hdr, customHeader.message[hdr])
                else:
                    msg.message.add_header(hdr, customHeader.message[hdr])
            else:
                # if the header was blank, it means we want it to be removed
                del(msg.message[hdr])

        # patch in the archive ID
        if 'x-archive-id' in msg.message:
            msg.message.replace_header('x-archive-id', post_id)
        else:
            msg.message.add_header('X-Archive-Id', post_id)

        # patch in the user ID
        if 'x-gsuser-id' in msg.message:
            msg.message.replace_header('x-gsuser-id', msg.sender_id)
        else:
            msg.message.add_header('X-GSUser-Id', msg.sender_id)

        # We *always* distribute plain mail at the moment.
        if 'content-type' in msg.message:
            msg.message.replace_header('content-type',
                                        'text/plain; charset=utf-8;')
        else:
            msg.message.add_header('content-type',
                                    'text/plain; charset=utf-8;')

        # Check if the From address is Yahoo! or AOL
        originalFromAddr = msg.sender
        origHost = self.parseaddr(originalFromAddr)[1].split('@')[1]
        dmarcPolicy = self.get_dmarc_policy_for_host(origHost)
        if (dmarcPolicy != ReceiverPolicy.none):
            # Set the old From header to 'X-gs-formerly-from'
            oldName = to_unicode_or_bust(msg.name)
            oldHeaderName = Header(oldName, UTF8)
            oldEncodedName = oldHeaderName.encode()
            oldFrom = formataddr((oldEncodedName, originalFromAddr))
            msg.message.add_header('X-gs-formerly-from', oldFrom)
            m = 'Rewriting From address "{0}" because of DMARC settings for '\
                '"{1}"'
            log.info(m.format(originalFromAddr, origHost))

            # Create a new From address from the list address
            user = self.acl_users.get_userByEmail(originalFromAddr)
            listMailto = self.getValueFor('mailto')
            domain = self.parseaddr(listMailto)[1].split('@')[1]
            if (user is not None):
                # Create a new From using the user-ID
                userInfo = createObject('groupserver.UserFromId',
                                        self.site_root(), user.getId())
                na = 'user-{userInfo.id}@{domain}'
                newAddress = na.format(userInfo=userInfo, domain=domain)
                m = 'Using user-address "{0}"'
                log.info(m.format(newAddress))
            else:
                # Create a new From using the old address
                na = 'anon-{mbox}-at-{host}@{domain}'
                mbox, host = self.parseaddr(originalFromAddr)[1].split('@')
                host = host.replace('.', '-')
                newAddress = na.format(mbox=mbox, host=host, domain=domain)
                m = 'Using anon-address "{0}"'
                log.info(m.format(newAddress))

            # Pick the "best" name, using length as a proxy for "best"
            if (user is not None) and (len(userInfo.name) >= len(msg.name)):
                fn = to_unicode_or_bust(userInfo.name)
            else:
                fn = to_unicode_or_bust(msg.name)
            headerName = Header(fn, UTF8)
            encodedName = headerName.encode()

            # Set the From address
            newFrom = formataddr((encodedName, newAddress))
            msg.message.replace_header('From', newFrom)

        # remove headers that should not be generally used for either our
        # encoding scheme or in general list mail
        for hdr in ('content-transfer-encoding', 'disposition-notification-to',
                    'return-receipt-to'):
            if hdr in msg.message:
                del(msg.message[hdr])

        newMail = "%s\r\n\r\n%s\r\n%s" % (msg.headers,
                                      body,
                                      customFooter)

        self.sendMail(newMail)

        return post_id

    def processMail(self, REQUEST):
        # Zeroth sanity check ... herein lies only madness.
        m = 'processMail: list (%s)' % self.getId()
        log.info(m)

        # Checks if member is allowed to send a mail to list
        mailString = getMailFromRequest(REQUEST)

        msg = EmailMessage(mailString, list_title=self.getProperty('title', ''),
                                       group_id=self.getId(),
                                       site_id=self.getProperty('siteId', ''),
                                       sender_id_cb=self.get_mailUserId)

        (header, body) = splitMail(mailString)

        # First sanity check ... have we already archived this message?
        messageQuery = MessageQuery(self)
        if messageQuery.post(msg.post_id):
            m = '%s (%s): Post from <%s> has already been archived with post '\
              'ID %s' % (self.getProperty('title', ''), self.getId(),
                msg.sender, msg.post_id)
            log.info(m)
            return "Message already archived"

        # get lower case email for comparisons
        email = msg.sender

        # Get members
        memberlist = lowerList(self.getValueFor('mailinlist'))

        # Get moderators
        moderatorlist = lowerList(self.getValueFor('moderator'))

        moderated = self.getValueFor('moderated')
        unclosed = self.getValueFor('unclosed')

        # message to a moderated list... relay all mails from a moderator
        if moderated and (email not in moderatorlist):
            m = ' %s (%s): relaying message %s from moderator <%s>' %\
              (self.getProperty('title', ''), self.getId(),
               msg.post_id, email)
            log.info(m)
            modresult = self.processModeration(REQUEST)
            if modresult:
                return modresult

        # traffic! relay all mails to a unclosed list or
        # relay if it is sent from members and moderators...
        if unclosed or (email in (memberlist + moderatorlist)):
            if hasattr(self, 'mail_handler'):
                self.mail_handler(self, REQUEST, mail=header, body=body)
                return email
            else:
                retval = self.listMail(REQUEST)
                return retval

        # if all previous tests fail, it must be an unknown sender.
        m = 'processMail %s (%s): Mail received from unknown sender <%s>' % \
          (self.getProperty('title', ''), self.getId(), email)
        log.info(m)
        log.info('memberlist was: %s' % memberlist)
        self.mail_reply(self, REQUEST, mailString)

    def processModeration(self, REQUEST):
        # a hook for handling the moderation stage of processing the email
        m = '%s (%s) Processing moderation' %\
          (self.getProperty('title', ''), self.getId())
        log.info(m)

        mailString = getMailFromRequest(REQUEST)

        # TODO: erradicate splitMail usage
        (header, body) = splitMail(mailString)

        msg = EmailMessage(mailString,
          list_title=self.getProperty('title', ''),
          group_id=self.getId(), site_id=self.getProperty('siteId', ''),
          sender_id_cb=self.get_mailUserId)

        # Get members
        try:
            memberlist = lowerList(self.getValueFor('mailinlist'))
        except:
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
                  (self.getProperty('title', ''), self.getId(), msg.sender)
                log.info(m)

        elif (msg.sender in memberlist) or unclosed:
            # --=mpj17=-- If we are here, then we are moderating *everyone*
            moderate = True
        else:
            self.mail_reply(self, REQUEST, mailString)
            return msg.sender

        if moderate:
            mqueue = getattr(self.aq_explicit, 'mqueue', None)

            # create a default-mailqueue if the traverse to mailqueue fails...
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
                nDict = {'mailingList': self,
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
        """ Store mail & attachments in a folder and return it.

        """
        ids = []
        for attachment in msg.attachments:
            if ((attachment['filename'] == '')
                and (attachment['subtype'] == 'plain')):
                # We definately don't want to save the plain text body again!
                pass
            elif ((attachment['filename'] == '')
                    and (attachment['subtype'] == 'html')):
                # We might want to do something with the HTML body some day,
                # but we archive the HTML body here, as it suggests in the log
                # message. The HTML body is archived along with the plain text
                # body.
                m = '%s (%s): archiving HTML message.' % (
                                       self.getProperty('title'), self.getId())
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
        '''Check the email for the correct IP address, loops and spam.

        The work of this method is done in three places:
            1. The "chk_*" methods of the mailing list.
            2. The "check_for_commands" method of the mailing list.
            3. A Group Member Posting Info, which is instantiated here.

        The "chk_*" methods check for fundamental issues with the message:
          * Mail loops,
          * Automatic responces,
          * Verboten text in the message, and
          * Banned email addresses.
        If one of these checks fails then the poster is not notified.

        If the message is recognised as a command then this method will
        return "None" (which is a good thing, see RETURNS below) so the
        message can be processed by the command-handling subsystem.

        The group member posting info class checks for more user-specific
        problems, such as exceeding the posting limit and being a banned
        member of a group. If these checks fail the user is sent a
        notification.

        RETURNS
            * Unicode if the message should *not* be processed, or
            * None if the message *should* be processed.

        SIDE EFFECTS
            If the user can post, "self._v_last_email_checksum" is set to the
            ID of the message, which is calculated by
            "emailmessage.EmailMessage".

            If the user cannot post, and the user exists in the system,
            then he or she is sent a notification, stating why the post
            was not processed.
        '''
        if not(self.chk_request_from_allowed_mta_hosts(REQUEST)):
            message = u'%s (%s): Host is not allowed' %\
              (self.getProperty('title', ''), self.getId())
            log.warning(message)
            return message

        groupId = self.getId()
        siteId = self.getProperty('siteId', '')
        if not siteId:
            m = u'No site identifier associated with "{0}"'.format(groupId)
            raise ValueError(m)
        site = getattr(self.site_root().Content, siteId)
        siteInfo = createObject('groupserver.SiteInfo', site)
        try:
            groupInfo = createObject('groupserver.GroupInfo', site, groupId)
        except:
            m = u'{0} ({1}): No group found to match listId. This should not '\
                u'happen.'
            message = m.format(self.getProperty('title', ''), self.getId())
            log.error(message)
            return message

        mailString = getMailFromRequest(REQUEST)
        try:
            msg = EmailMessage(mailString,
                               list_title=self.getProperty('title', ''),
                               group_id=groupId,
                               site_id=siteId,
                               sender_id_cb=self.get_mailUserId)
        except ValueError:
            m = u'Could not create an email message in the group "{0}" with '\
                u'the mail-string starting with\n{1}'
            message = m.format(groupId, mailString[:256])
            log.error(message)
            raise

        try:
            m = u'checkMail: {0} ({1}) checking message from <{2}>'
            message = m.format(groupInfo.name, groupInfo.id, msg.sender)
            log.info(message)
        except AttributeError:
            m = u'checkMail: problem checking message to "{0}" with the '\
                u'mail-string starting with\n{1}'
            message = m.format(groupId, mailString[:256])
            log.error(message)
            raise

        message = u''
        if self.chk_msg_xmailer_loop(msg):
            message = u'%s (%s): X-Mailer header detected, a loop is '\
              'likely' % (groupInfo.name, groupInfo.id)
        elif self.chk_msg_automatic_email(msg):
            message = u'%s (%s): automated response detected from <%s>' %\
              (groupInfo.name, groupInfo.id, msg.get('from', '<>'))
        elif self.chk_msg_tight_loop(msg):
            message = u'%s (%s): Detected duplicate message, using tight '\
              u'loop, from <%s>' % \
              (groupInfo.name, groupInfo.id, msg.get('from'))
        elif self.chk_msg_disabled(msg):
            message = u'%s (%s): Email address <%s> is disabled.' %\
              (groupInfo.name, groupInfo.id, msg.sender)
        elif self.chk_msg_spam(mailString):  # --=mpj17=--I moved this far
            message = u'%s (%s): Spam detected' %\
              (groupInfo.name, groupInfo.id)
        elif self.chk_sender_blacklist(msg):
            message = '%s (%s): Dropping message from blacklisted '\
                'address <%s>' % (groupInfo.name, groupInfo.id, msg.sender)
        if message:
            assert type(message) == unicode
            log.warning(message)
            return message

        # Check for hosed denial-of-service-vacation mailers
        # or other infinite mail-loops...
        email = msg.sender
        sender_id = msg.sender_id
        userInfo = createObject('groupserver.UserFromId',
                                self.site_root(), sender_id)
        commands = [
          self.getValueFor('unsubscribe'),
          self.getValueFor('subscribe'),
          'digest on',
          'digest off']
        if check_for_commands(msg, commands):
            # If the message is a command, we have to let the
            #   command-handling subsystem deal with it.
            m = u'%s (%s) email-command from <%s>: "%s"' % \
              (groupInfo.name, groupInfo.id, msg.sender, msg.subject)
            log.info(m)
            return None
        else:
            # Not a command
            insts = (groupInfo.groupObj, userInfo)
            postingInfo = getMultiAdapter(insts, IGSPostingUser)
            if not(postingInfo.canPost) and not(userInfo.anonymous):
                message = '%s (%s): %s' % (userInfo.name, userInfo.id,
                                            postingInfo.status)
                log.warning(message)
                notifier = CanPostNotifier(groupInfo.groupObj, REQUEST)
                notifier.notify(userInfo, siteInfo, groupInfo,
                                mailString)

                return message

        self._v_last_email_checksum = msg.post_id

        # look to see if we have a custom_mailcheck hook. If so, call it.
        # custom_mailcheck should return True if the message is to be blocked
        custom_mailcheck = getattr(self, 'custom_mailcheck', None)
        if custom_mailcheck:
            if custom_mailcheck(mailinglist=self, sender=email, header=msg,
                                body=msg.body):
                return message

        m = u'checkMail: %s (%s) message from <%s> checks ok' %\
          (groupInfo.name, groupInfo.id, msg.sender)
        log.info(m)
        return None

    def chk_request_from_allowed_mta_hosts(self, REQUEST):
        '''Check if the request comes from one of the allowed Mail Transfer
        Agent host-machines.
        '''
        retval = True
        mtahosts = self.getValueFor('mtahosts')
        if mtahosts:
            if 'HTTP_X_FORWARDED_FOR' in self.REQUEST.environ.keys():
                REMOTE_IP = self.REQUEST.environ['HTTP_X_FORWARDED_FOR']
            else:
                REMOTE_IP = self.REQUEST.environ['REMOTE_ADDR']

            retval = REMOTE_IP in mtahosts

        if not retval:
            message = u'%s (%s): Host %s is not allowed' %\
              (self.getProperty('title', ''), self.getId(), REMOTE_IP)
            log.info(message)

        assert type(retval) == bool
        return retval

    def chk_msg_xmailer_loop(self, msg):
        '''Check to see if the x-mailer header is one that GroupServer
        set'''
        retval = msg.get('x-mailer') == self.getValueFor('xmailer')
        assert type(retval) == bool
        return retval

    def chk_msg_disabled(self, msg):
        '''Check if the email is from a disabled email address'''
        disabled = list(self.getValueFor('disabled'))
        retval = msg.sender in disabled
        assert type(retval) == bool
        return retval

    def chk_msg_automatic_email(self, msg):
        '''Check for empty return-path, which implies automatic mail'''
        retval = msg.get('return-path') == '<>'
        assert type(retval) == bool
        return retval

    def chk_msg_tight_loop(self, msg):
        assert hasattr(self, '_v_last_email_checksum'),\
                 "no _v_last_email_checksum"
        retval = self._v_last_email_checksum and \
          (self._v_last_email_checksum == msg.post_id) or False
        assert type(retval) == bool, "type was %s, not bool" % type(retval)
        return retval

    def chk_msg_spam(self, mailString):
        '''Check if the message is "spam". Actually, check if the message
        matches the list of banned regular expressions. This is normally
        used to prevent out-of-office autoreply messages hitting the list.
        '''
        retval = False  # Uncharacteristic optimism
        for regexp in self.getValueFor('spamlist'):
            if regexp and search(regexp, mailString):
                log.info(u'%s matches message' % regexp)
                retval = True
                break
        assert type(retval) == bool
        return retval

    def chk_sender_blacklist(self, msg):
        # See Ticket 459 <https://projects.iopen.net/groupserver/ticket/459>
        memberQuery = MemberQuery(self)
        retval = memberQuery.address_is_blacklisted(msg.sender)
        assert type(retval) == bool
        return retval

    def requestMail(self, REQUEST):
        # Handles requests for subscription changes

        mailString = getMailFromRequest(REQUEST)

        # TODO: this needs to be completely removed, but some of the email
        # depends on it still
        (header, body) = splitMail(mailString)

        msg = EmailMessage(mailString, list_title=self.getProperty('title', ''),
                                       group_id=self.getId(),
                                       site_id=self.getProperty('siteId', ''),
                                       sender_id_cb=self.get_mailUserId)

        # get subject
        subject = msg.subject

        # get email-address
        email = msg.sender

        memberlist = lowerList(self.getValueFor('mailinlist'))

        # process digest commands
        if email in memberlist and msg.sender_id:
            userInfo = createObject('groupserver.UserFromId',
                         self.site_root(), msg.sender_id)
            deliverySettings = \
                        userInfo.user.get_deliverySettingsByKey(self.getId())
            if check_for_commands(msg, 'digest on'):
                if deliverySettings != DIGEST:
                    self.digest_on(REQUEST, userInfo.user, header, body)
                else:
                    self.mail_cannot_change_subscription(self, REQUEST,
                                                         msg, 'digest on')
                return email
            elif check_for_commands(msg, 'digest off'):
                if deliverySettings == DIGEST:
                    self.digest_off(REQUEST, userInfo.user, header, body)
                else:
                    self.mail_cannot_change_subscription(self, REQUEST,
                                                         msg, 'digest off')
                return email

        # subscription? only subscribe if subscription is enabled.
        subscribe = self.getValueFor('subscribe')
        if subscribe != '' and check_for_commands(msg, subscribe):
            if email not in memberlist:
                if subject.find(pin(email, self.getValueFor('hashkey'))) != -1:
                    self.manage_addMember(email)
                else:
                    user = self.acl_users.get_userByEmail(email)
                    if user:
                        # if the user exists, send out a subscription email
                        self.mail_subscribe_key(self, REQUEST, msg)
                    else:
                        # otherwise handle subscription as part of registration
                        self.register_newUser(REQUEST, msg)
            else:
                self.mail_cannot_change_subscription(self, REQUEST, msg,
                                                    'subscribe')
            return email

        # unsubscription? only unsubscribe if unsubscription is enabled...
        unsubscribe = self.getValueFor('unsubscribe')
        if unsubscribe != '' and check_for_commands(msg, unsubscribe):
            if email.lower() in memberlist:
                self.manage_delMember(email)
            else:
                self.mail_cannot_change_subscription(self, REQUEST, msg,
                                                        'unsubscribe')
            return email

    def register_newUser(self, REQUEST, msg):
        siteId = self.getProperty('siteId', '')
        groupId = self.getId()
        site = getattr(self.site_root().Content, siteId)
        siteInfo = createObject('groupserver.SiteInfo', site)
        groupInfo = createObject('groupserver.GroupInfo', site, groupId)

        m = u'Registering <%s> with %s (%s) on %s (%s)' %\
          (msg.sender, groupInfo.name, groupInfo.id,
           siteInfo.name, siteInfo.id)
        log.info(m)
        email = str(msg.sender)
        user = create_user_from_email(groupInfo.groupObj, email)
        eu = createObject('groupserver.EmailVerificationUserFromEmail',
                           groupInfo.groupObj, email)
        eu.send_verification_message()
        join_group(user, groupInfo)

        assert user

    def digest_on(self, REQUEST, user, header, body):
        '''Turn on digest mode for a user
        '''
        siteId = self.getProperty('siteId', '')
        groupId = self.getId()
        site = getattr(self.site_root().Content, siteId)
        siteInfo = createObject('groupserver.SiteInfo', site)
        groupInfo = createObject('groupserver.GroupInfo', site, groupId)
        userInfo = createObject('groupserver.UserFromId',
                            self.site_root(), user.getId())

        m = u'%s (%s) on %s (%s) turning on digest for %s (%s)' %\
          (groupInfo.name, groupInfo.id,
           siteInfo.name, siteInfo.id,
           userInfo.name, userInfo.id)
        log.info(m)

        user.set_enableDigestByKey(groupInfo.id)
        self.mail_digest_on(self, REQUEST, mail=header, body=body)

    def digest_off(self, REQUEST, user, header, body):
        '''Turn off digest mode (and turn on one email per post) for a user
        '''
        siteId = self.getProperty('siteId', '')
        groupId = self.getId()
        site = getattr(self.site_root().Content, siteId)
        siteInfo = createObject('groupserver.SiteInfo', site)
        groupInfo = createObject('groupserver.GroupInfo', site, groupId)
        userInfo = createObject('groupserver.UserFromId',
                            self.site_root(), user.getId())

        m = u'%s (%s) on %s (%s) turning off digest for %s (%s)' %\
          (groupInfo.name, groupInfo.id,
           siteInfo.name, siteInfo.id,
           userInfo.name, userInfo.id)
        log.info(m)

        user.set_disableDigestByKey(groupInfo.id)
        self.mail_digest_off(self, REQUEST, mail=header, body=body)

    security.declareProtected('Manage properties', 'manage_addMember')

    def manage_addMember(self, email):
        """ Add member to group. """
        retval = 0
        user = self.acl_users.get_userByEmail(email)
        if user:
            userInfo = createObject('groupserver.UserFromId',
                                self.site_root(), user.getId())
            siteId = self.getProperty('siteId', '')
            groupId = self.getId()
            site = getattr(self.site_root().Content, siteId)
            siteInfo = createObject('groupserver.SiteInfo', site)
            groupInfo = createObject('groupserver.GroupInfo', site, groupId)

            m = u'%s (%s) on %s (%s) subscribing %s (%s) <%s>' % \
              (groupInfo.name, groupInfo.id, siteInfo.name, siteInfo.id,
               userInfo.name, userInfo.id, email)
            log.info(m)

            # TODO: Use gs.group.member.join like the rest of GS
            join_group(user, groupInfo)

            retval = 1

        return retval

    security.declareProtected('Manage properties', 'manage_delMember')

    def manage_delMember(self, email):
        """ Remove member from group. """
        retval = 0
        user = self.acl_users.get_userByEmail(email)
        if user:
            siteId = self.getProperty('siteId', '')
            site = getattr(self.site_root().Content, siteId)
            groupId = self.getId()
            groupInfo = createObject('groupserver.GroupInfo', site, groupId)
            userInfo = \
              createObject('groupserver.UserFromId', self.site_root(),
                            user.getId())
            leaver = GroupLeaver(groupInfo, userInfo)
            leaver.removeMember()
            retval = int(not(leaver.isMember))
        return retval

    def get_mailUserId(self, addr):
        """ From the email address, get the user's ID.

        """
        return self.acl_users.get_userIdByEmail(addr) or ''

    def parseaddr(self, header):
        # wrapper for rfc822.parseaddr, returns (name, addr)
        return parseaddr(header)

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

    security.declarePrivate('mail_subscribe_key')
    def mail_subscribe_key(self, context, REQUEST, msg):
        """ Email out a subscription authentication notification.

        This is only called when an existing user tries to subscribe by
        email.
        """
        userInfo = createObject('groupserver.UserFromId',
                            self.site_root(), msg.sender_id)
        if userInfo.anonymous:
            m = u'subscribe: Cannot subscribe user %s because they '\
              u'do not exist. We shouldn\'t have gotten this far.' % msg.sender_id
            m.encode('ascii', 'ignore')
            log.error(m)
            return

        siteId = self.getProperty('siteId', '')
        groupId = self.getId()
        site = getattr(self.site_root().Content, siteId)
        siteInfo  = createObject('groupserver.SiteInfo', site)
        groupInfo = createObject('groupserver.GroupInfo', site, groupId)
        thepin = pin( msg.sender, self.getValueFor('hashkey') )

        m = u'%s (%s) on %s (%s) sending subscribe key (%s) to '\
          u'existing user %s (%s)' %\
          (groupInfo.name, groupInfo.id, siteInfo.name, siteInfo.id,
           thepin, userInfo.name, userInfo.id)
        m.encode('ascii', 'ignore')
        log.info(m)

        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]

        reply = getattr(self, 'email_subscribe_key', None)

        if reply:
            reply_text = reply(REQUEST, listId=self.listId(),
                                   pin=thepin,
                                   email=msg.sender,
                                   listMailTo=self.getValueFor('mailto'),
                                   subject=self.getValueFor('subscribe'),
                                   xmailer=self.getValueFor('xmailer'),
                                   returnpath=returnpath,
                                   siteInfo=siteInfo,
                                   groupInfo=groupInfo,
                                   userInfo=userInfo)
            send_email(returnpath, [msg.sender], reply_text)

    security.declarePrivate('mail_unsubscribe_key')

    def mail_unsubscribe_key(self, context, REQUEST, msg):
        """ Email out an unsubscription authentication notification.

        """
        userInfo = createObject('groupserver.UserFromId',
                            self.site_root(), msg.sender_id)
        if userInfo.anonymous:
            m = u'unsubscribe: Cannot unsubscribe user %s because they '\
              u'do not exist. We shouldn\'t have gotten this far.' % \
              msg.sender_id
            m.encode('ascii', 'ignore')
            log.error(m)
            return

        siteId = self.getProperty('siteId', '')
        groupId = self.getId()
        site = getattr(self.site_root().Content, siteId)
        siteInfo = createObject('groupserver.SiteInfo', site)
        groupInfo = createObject('groupserver.GroupInfo', site, groupId)
        thepin = pin(msg.sender, self.getValueFor('hashkey'))

        m = u'%s (%s) on %s (%s) sending unsubscribe key (%s) to %s (%s)' % \
          (groupInfo.name, groupInfo.id, siteInfo.name, siteInfo.id,
           thepin, userInfo.name, userInfo.id)
        m.encode('ascii', 'ignore')
        log.info(m)

        returnpath = self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]

        reply = getattr(self, 'email_unsubscribe_key', None)
        if reply:
            reply_text = reply(REQUEST, listId=self.listId(),
                                   pin=thepin,
                                   email=msg.sender,
                                   listMailTo=self.getValueFor('mailto'),
                                   subject=self.getValueFor('unsubscribe'),
                                   xmailer=self.getValueFor('xmailer'),
                                   returnpath=returnpath,
                                   siteInfo=siteInfo,
                                   groupInfo=groupInfo,
                                   userInfo=userInfo)
            send_email(returnpath, [msg.sender], reply_text)

    security.declarePrivate('mail_cannot_change_subscription')

    def mail_cannot_change_subscription(self, context, REQUEST, msg, change):
        """ Explain that the user:
              * cannot subscribe because they are already a member,
              * cannot unsubscribe because they're not a member,
              * cannot turn the digest on because it already is, or
              * cannot turn the digest off because it already is.
        """
        assert change in ['subscribe','unsubscribe','digest on','digest off'], \
          'Subscription change request %s was not one of subscribe, unsubscribe, '\
          'digest on, or digest off.' % change
        userInfo = createObject('groupserver.UserFromId',
                            self.site_root(), msg.sender_id)
        if userInfo.anonymous:
            m = u'cannot_change_subscription: Cannot notify user %s because they '\
              u'do not exist. We shouldn\'t have gotten this far.' % msg.sender_id
            m.encode('ascii', 'ignore')
            log.error(m)
            return

        siteId = self.getProperty('siteId', '')
        groupId = self.getId()
        group = get_group_by_siteId_and_groupId(self, siteId, groupId)
        supportEmail = getOption(group, 'supportEmail')
        siteInfo = createObject('groupserver.SiteInfo', group)
        groupInfo = IGSGroupInfo(group)

        notification = 'email_already_subscribed'
        if change == 'unsubscribe':
            notification = 'email_already_unsubscribed'
        elif change == 'digest on':
            notification = 'email_digest_already_on'
        elif change == 'digest off':
            notification = 'email_digest_already_off'
        m = u'%s (%s) on %s (%s) sending notification %s to '\
          u'existing user %s (%s)' %\
          (groupInfo.name, groupInfo.id, siteInfo.name, siteInfo.id,
           notification, userInfo.name, userInfo.id)
        m.encode('ascii', 'ignore')
        log.info(m)

        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]

        reply = getattr(self, notification, None)
        if reply:
            reply_text = reply(REQUEST, sender=msg.sender,
                listMailTo=self.getValueFor('mailto'),
                supportEmail=supportEmail,
                shortName=groupInfo.get_property('short_name', groupInfo.name),
                siteInfo=siteInfo,
                groupInfo=groupInfo,
                userInfo=userInfo)

            send_email(returnpath, [msg.sender], reply_text)

    security.declarePrivate('mail_digest_on')
    def mail_digest_on(self, context, REQUEST, mail=None, body=''):
        """ Send out a message that the digest feature has been turned on.

        """
        mailString = getMailFromRequest(REQUEST)
        msg = EmailMessage(mailString,
                list_title=self.getProperty('title', ''),
                group_id=self.getId(),
                site_id=self.getProperty('siteId', ''),
                sender_id_cb=self.get_mailUserId)
        userInfo = createObject('groupserver.UserFromId',
                        self.site_root(), msg.sender_id)
        assert not userInfo.anonymous
        siteId = self.getProperty('siteId', '')
        site = getattr(self.site_root().Content, siteId)
        siteInfo  = createObject('groupserver.SiteInfo', site)
        groupId = self.getId()
        groupInfo = createObject('groupserver.GroupInfo', site, groupId)

        m = u'%s (%s) on %s (%s) sending digest on '\
          u'notification to %s (%s)' %\
          (groupInfo.name, groupInfo.id,
           siteInfo.name, siteInfo.id,
           userInfo.name, userInfo.id)
        m.encode('ascii', 'ignore')
        log.info(m)

        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]

        reply = getattr(self, 'email_digest_on', None)
        if reply:
            reply_text = reply(REQUEST, listId=self.listId(),
               getValueFor=self.getValueFor,
               email=msg.sender,
               shortName=groupInfo.get_property('short_name', groupInfo.name),
               listMailTo=self.getValueFor('mailto'),
               xmailer=self.getValueFor('xmailer'),
               returnpath=returnpath,
               siteInfo=siteInfo,
               groupInfo=groupInfo,
               userInfo=userInfo)

            send_email(returnpath, [msg.sender], reply_text)

    security.declarePrivate('mail_digest_off')
    def mail_digest_off(self, context, REQUEST, mail=None, body=''):
        """ Send out a message that the digest feature has been turned off.

        """
        mailString = getMailFromRequest(REQUEST)
        msg = EmailMessage(mailString,
                list_title=self.getProperty('title', ''),
                group_id=self.getId(),
                site_id=self.getProperty('siteId', ''),
                sender_id_cb=self.get_mailUserId)
        userInfo = createObject('groupserver.UserFromId',
                        self.site_root(), msg.sender_id)
        assert not userInfo.anonymous
        siteId = self.getProperty('siteId', '')
        site = getattr(self.site_root().Content, siteId)
        siteInfo = createObject('groupserver.SiteInfo', site)
        groupId = self.getId()
        groupInfo = createObject('groupserver.GroupInfo', site, groupId)

        m = u'%s (%s) on %s (%s) sending digest off '\
          u'notification to %s (%s)' %\
          (groupInfo.name, groupInfo.id,
           siteInfo.name, siteInfo.id,
           userInfo.name, userInfo.id)
        m.encode('ascii', 'ignore')
        log.info(m)

        returnpath = self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]

        reply = getattr(self, 'email_digest_off', None)
        if reply:
            reply_text = reply(REQUEST, listId=self.listId(),
               getValueFor=self.getValueFor,
               email=msg.sender,
               shortName=groupInfo.get_property('short_name', groupInfo.name),
               listMailTo=self.getValueFor('mailto'),
               xmailer=self.getValueFor('xmailer'),
               returnpath=returnpath,
               siteInfo=siteInfo,
               groupInfo=groupInfo,
               userInfo=userInfo)
            send_email(returnpath, [msg.sender], reply_text)

    security.declarePrivate('mail_event_default')
    def mail_event_default(self, context, event_codes, headers):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.

        """
        siteId = self.getProperty('siteId', '')
        groupId = self.getId()
        group = get_group_by_siteId_and_groupId(self, siteId, groupId)
        supportEmail = getOption(group, 'supportEmail')
        siteInfo = createObject('groupserver.SiteInfo', group)
        groupInfo = IGSGroupInfo(group)
        name, email_address = AddressList(headers['from'])[0]
        user = self.site_root().acl_users.get_userByEmail(email_address)
        userInfo = None
        if user:
            userInfo = IGSUserInfo(user)

        returnpath = self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]

        seen = []
        for code in event_codes:
            if code in seen:
                continue
            reply = getattr(self, 'xwf_email_event', None)
            if reply:
                reply_text = reply(context, code, headers, supportEmail,
                                   siteInfo, groupInfo, userInfo)
                if reply_text and email_address:
                    send_email(returnpath, [email_address], reply_text)
            seen.append(code)

    security.declarePrivate('mail_header')
    def mail_header(self, context, REQUEST, getValueFor=None, title='',
                          mail=None, body='', file_ids=(), post_id=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.

        """
        header = getattr(self, 'xwf_email_header', None)
        if header:
            text = header(REQUEST, list_object=context,
                                   getValueFor=getValueFor,
                                   title=title, mail=mail, body=body,
                                   file_ids=file_ids,
                                   post_id=post_id)

            if not isinstance(text, unicode):
                text = unicode(text, 'utf-8', 'ignore')
            return text
        else:
            return u''

    security.declarePrivate('mail_footer')
    def mail_footer(self, context, REQUEST, getValueFor=None, title='',
                          mail=None, body='', file_ids=(), post_id=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.

        """
        footer = getattr(self, 'xwf_email_footer', None)
        if footer:
            text = footer(REQUEST, list_object=context,
                                   getValueFor=getValueFor,
                                   title=title, mail=mail, body=body,
                                   file_ids=file_ids,
                                   post_id=post_id)
            if not isinstance(text, unicode):
                text = unicode(text, 'utf-8', 'ignore')

            return text

        else:
            return u""

    def addGSFile(self, title, topic, creator, data, content_type):
        """ Adds an attachment as a file.

        """
        # TODO: group ID should be more robust
        group_id = self.getId()
        storage = self.FileLibrary2.get_fileStorage()
        fileId = storage.add_file(data)
        fileObj = storage.get_file(fileId)
        fixedTitle = removePathsFromFilenames(title)
        fileObj.manage_changeProperties(content_type=content_type,
          title=fixedTitle, tags=['attachment'], group_ids=[group_id],
          dc_creator=creator, topic=topic)
        fileObj.reindex_file()
        #
        # Commit the ZODB transaction -- this basically makes it impossible for
        # us to rollback, but since our RDB transactions won't be rolled back
        # anyway, we do this so we don't have dangling metadata.
        #
        # --=mpj17=-- But it caused death on my local box. So I am
        # experimenting with commenting it out.
        # transaction.commit()
        return fileId

    def sendMail(self, mailString):
        # actually send the email

        # Get members
        memberlist = self.getValueFor('maillist')

        # Remove "blank" / corrupted / doubled entries
        maillist = []
        for email in memberlist:
            if '@' in email and email not in maillist:
                maillist.append(email)

        returnpath = self.getValueFor('mailto')

        send_email(returnpath, maillist, mailString.encode('utf-8', 'ignore'))

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
