# Copyright IOPEN Technologies Ltd., 2003
# richard@iopen.net
#
# For details of the license, please see LICENSE.
#
# You MUST follow the rules in README_STYLE before checking in code
# to the head. Code which does not follow the rules will be rejected.  
#
# This code is based heavily on the MailBoxer product, under the GPL.
#

from AccessControl import ClassSecurityInfo
from DateTime.DateTime import DateTime
from Globals import InitializeClass
from OFS.Folder import Folder
from OFS.Folder import manage_addFolder

from Products.CustomProperties.CustomProperties import CustomProperties
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Products.XWFCore.XWFUtils import munge_date

import MailBoxerTools
from emailmessage import EmailMessage
from emailmessage import IRDBStorageForEmailMessage
from emailmessage import RDBFileMetadataStorage
from emailmessage import strip_subject

from queries import MemberQuery, MessageQuery

from export import export_archive_as_mbox
from utils import check_for_commands
from utils import pin
from utils import getMailFromRequest

# from zLOG import LOG, PROBLEM, INFO
import logging
log = logging.getLogger('XWFMailingList')

import random
import smtplib
import os
import re
import time
import transaction

from cgi import escape
    
null_convert = lambda x: x

try:
    import Products.MaildropHost
    MaildropHostIsAvailable = 1
except:
    MaildropHostIsAvailable = 0

try:
    import Products.SecureMailHost
    SecureMailHostIsAvailable = 1
except:
    SecureMailHostIsAvailable = 0

# Simple return-Codes for web-callable-methods for the smtp2zope-gate
TRUE = "TRUE"
FALSE = "FALSE"

DEFER_EMAIL = True
MAILDROP_SPOOL='/tmp/mailboxer_spool2'

if not os.path.isdir(MAILDROP_SPOOL):
    os.makedirs(MAILDROP_SPOOL)

def makeTempPath(objpath):
    """ Helper to create a temp file name safely """
    temp_path_dir = os.path.join(MAILDROP_SPOOL, objpath)
    temp_path = os.path.join(temp_path_dir, str(random.randint(100000, 9999999)))

    if not os.path.isdir(temp_path_dir):
        os.makedirs(temp_path_dir)

    while os.path.exists(temp_path):
        temp_path = os.path.join(temp_path_dir, str(random.randint(100000, 9999999)))

    return temp_path

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
        {'id':'title', 'type':'string', 'mode':'w'}, 
        {'id':'mailto', 'type':'string', 'mode':'wd'}, 
        {'id':'hashkey', 'type':'string', 'mode':'wd'}, 
       )
    
    
    # Internal storages for sender-loop-limitation
    sendercache = {}
    
    # track the checksum of the last email sent
    last_email_checksum = ''
    
    def __init__(self, id, title, mailto):
        """ Setup a mailing list with reasonable defaults.
        
        """
        self.id = id
        self.title = title
        self.hashkey = str(random.random())
        self.mailto = mailto
        
    def valid_property_id(self, id):
        # A modified version of the 'valid_property_id' in the PropertyManager
        # class. This one _doesn't_ check for the existence of the ID,
        # since it might exist in our base class, and we can't remove
        # things from there
        if not id or id[:1]=='_' or (id[:3]=='aq_') \
           or (' ' in id) or escape(id) != id:
            return False
        return True
        
    def init_properties(self):
        """ Tidy up the property sheet, since we don't want to control most of
        the properties that have already been defined in the parent MailingListManager.
        
        """
        delete_properties = filter(lambda x: x not in self.mailinglist_properties, 
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
        self.processMail(REQUEST)
        return TRUE


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
            return FALSE

        self.listMail(REQUEST)
        return TRUE
    
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
                                      self.getValueFor('hashkey')) ):
            mqueue = self.restrictedTraverse(self.getValueFor('mailqueue'))
            mid = REQUEST.get('mid', '-1')

            if not hasattr(mqueue, mid):
                if action in ['approve', 'discard']:
                    if hasattr(self, "mail_approve"):
                        return self.mail_approve(self, REQUEST, msg="MAIL_NOT_FOUND")
                    else:
                        REQUEST.RESPONSE.setHeader('Content-type', 'text/plain')
                        return "MAIL NOT FOUND! MAYBE THE MAIL WAS ALREADY PROCESSED."
                else:
                    if hasattr(self, "mail_approve"):
                        return self.mail_approve(self, REQUEST, msg="MAIL_PENDING")
                    else:
                        REQUEST.RESPONSE.setHeader('Content-type', 'text/plain')
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
        member_groups = self.getProperty('member_groups', ['%s_member' % self.listId()])
        uids = []
        for gid in member_groups:
            group = self.acl_users.getGroupById(gid)
            uids += group.getUsers()

        if ids_only:
            return uids

        users = []
        for uid in uids:
            user = self.acl_users.getUser(uid)
            if user:
                users.append(user)
                
        return users

    security.declareProtected('Manage properties', 'get_memberUserCount')
    def get_memberUserCount(self):
        """ Get a count of the number of users corresponding to the
            membership list, assuming we can.
        
        """
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
        da = self.zsqlalchemy 
        assert da
        memberQuery = MemberQuery(self, da)

        if key in ('digestmaillist', 'maillist', 'moderator', 'moderatedlist', 'mailinlist'):
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
                addresses = []
                if key == 'maillist':
                    addresses = memberQuery.get_member_addresses(self.getProperty('siteId'), self.getId(),                
                                                    self.get_memberUserObjects)
                elif key == 'digestmaillist':
                    addresses = memberQuery.get_digest_addresses(self.getProperty('siteId'), self.getId(),                
                                                    self.get_memberUserObjects)
                elif key == 'moderator':
                    addresses = memberQuery.get_member_addresses(self.getProperty('siteId'), self.getId(),                
                                                    self.get_moderatorUserObjects, preferred_only=False, process_settings=False)                
                elif key == 'moderatedlist':
                    addresses = memberQuery.get_member_addresses(self.getProperty('siteId'), self.getId(),                
                                                    self.get_moderatedUserObjects, preferred_only=False, process_settings=False)
                elif key == 'mailinlist':
                    addresses = memberQuery.get_member_addresses(self.getProperty('siteId'), self.getId(),                
                                                    self.get_memberUserObjects, preferred_only=False, process_settings=False)
                for email in addresses:
                    email = email.strip()
                    if email and email not in maillist:
                        maillist.append(email)
            
            except Exception, x:
                m = '%s (%s): A problem was experienced while getting '\
                  'values: %s' % (self.getProperty('title', ''), self.getId(), x)
                log.error(m)
                maillist = None
            
            # last ditch effort
            if maillist == None:
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
        """ A helper method for tidying up the mailing list subject for remailing.
        
        """
        # there is an assumption that if we're including a listid we should
        # strip any existing listid reference
        if include_listid:
            # this *must* be a string, it cannot be unicode
            list_title = str(self.getValueFor('title'))
        else:
            list_title = ''
            
        subject = strip_subject(subject, list_title, False)
        
        is_reply = 0
        if subject.lower().find('re:', 0, 3) == 0 and len(subject) > 3:
            subject = subject[3:].strip()
            is_reply = 1
        
        re_string = '%s' % (is_reply and 'Re: ' or '')
        if include_listid:
            subject = '%s[%s] %s' % (re_string, list_title, subject)
        else:
            subject = '%s%s' % (re_string, subject)
            
        return subject

    def listMail(self, REQUEST):
        # Shifted from MailBoxer till reintegration project
        
        # Send a mail to all members of the list.
        mailString = getMailFromRequest(REQUEST)
        
        msg = EmailMessage(mailString, list_title=self.getProperty('title', ''), 
                                       group_id=self.getId(), 
                                       site_id=self.getProperty('siteId', ''), 
                                       sender_id_cb=self.get_mailUserId)
        m = '%s (%s) Listing message %s from <%s>' %\
          (self.getProperty('title', ''), self.getId(), msg.post_id, 
           msg.sender)
        log.info(m)
        
        # store mail in the archive? get context for the mail...
        post_id = msg.post_id
        if self.getValueFor('archived') != self.archive_options[0]:
            (post_id, file_ids) = self.manage_addMail(msg)
                    
        # The custom header is actually capable of replacing the top of the
        # message, for example with a banner, so we need to parse it again
        headers = {}
        for item in msg.message.items():
            headers[item[0].lower()] = item[1]
            
        customHeader = EmailMessage(self.mail_header(self, 
                                                    REQUEST, 
                                                    getValueFor=self.getValueFor, 
                                                    title=self.getValueFor('title'), 
                                                    mail=headers, 
                                                    body=msg.body, 
                                                    file_ids=file_ids, 
                                                    post_id=post_id).strip())
        
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
                if msg.message.has_key(hdr):
                    msg.message.replace_header(hdr, customHeader.message[hdr])
                else:
                    msg.message.add_header(hdr, customHeader.message[hdr])
            else:
                # if the header was blank, it means we want it to be removed
                del(msg.message[hdr])

        # patch in the archive ID
        if msg.message.has_key('x-archive-id'):
            msg.message.replace_header('x-archive-id', post_id)
        else:
            msg.message.add_header('X-Archive-Id', post_id)
        
        # patch in the user ID
        if msg.message.has_key('x-gsuser-id'):
            msg.message.replace_header('x-gsuser-id', msg.sender_id)
        else:
            msg.message.add_header('X-GSUser-Id', msg.sender_id)
        
        # We *always* distribute plain mail at the moment.
        if msg.message.has_key('content-type'):
            msg.message.replace_header('content-type', 'text/plain; charset=utf-8;')
        else:
            msg.message.add_header('content-type', 'text/plain; charset=utf-8;')
            
        # remove headers that should not be generally used for either our
        # encoding scheme or in general list mail
        for hdr in ('content-transfer-encoding', 'disposition-notification-to', 
                    'return-receipt-to'):
            if msg.message.has_key(hdr):
                del(msg.message[hdr])
            
        newMail = "%s\r\n\r\n%s\r\n%s" % (msg.headers, 
                                      body, 
                                      customFooter)
        
        if not DEFER_EMAIL:
            return self.sendMail(newMail)

        # otherwise, we save the email into a spool file for sending later.
        # this should provide a _much_ faster response time for listMail
        # we write the email to the spool file after we put the groupname
        # at the top
        spoolMail = ';;%s;;\r\n%s' % (self.getId(), newMail)

        objpath = os.path.join(*self.aq_parent.getPhysicalPath())
        tempfilepath = makeTempPath(objpath)
        lockfilepath = '%s.lck' % tempfilepath

        lockfile = file(lockfilepath, 'a+')
        lockfile.write('locked')
        lockfile.close()

        spoolfile = file(tempfilepath, 'ab+')
        spoolfile.write(spoolMail)

        os.remove(lockfilepath)
        
    def processMail(self, REQUEST):
        # Zeroth sanity check ... herein lies only madness.

        da = self.zsqlalchemy 
        assert da

        # Checks if member is allowed to send a mail to list
        mailString = getMailFromRequest(REQUEST)
        
        msg = EmailMessage(mailString, list_title=self.getProperty('title', ''), 
                                       group_id=self.getId(), 
                                       site_id=self.getProperty('siteId', ''), 
                                       sender_id_cb=self.get_mailUserId)
        
        (header, body) = MailBoxerTools.splitMail(mailString)

        # First sanity check ... have we already archived this message?
        messageQuery = MessageQuery(self, da)
        if messageQuery.post(msg.post_id):
            m = '%s (%s): Post from <%s> has already been archived with post '\
              'ID %s' % (self.getProperty('title', ''), self.getId(), 
                msg.sender, msg.post_id)
            log.info(m)
            return "Message already archived"

        # get lower case email for comparisons
        email = msg.sender
                
        # Get members
        memberlist = MailBoxerTools.lowerList(self.getValueFor('mailinlist'))
        
        # Get moderators
        moderatorlist = MailBoxerTools.lowerList(self.getValueFor('moderator'))
        
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
            else:
                self.listMail(REQUEST)
                
            return email
        m = '%s (%s): Mail received from unknown sender <%s>' %\
          (self.getProperty('title', ''), self.getId(), email)
        log.info(m)
        log.info( 'memberlist was: %s' % memberlist)

        # if all previous tests fail, it must be an unknown sender.
        self.mail_reply(self, REQUEST, mail=header, body=body)
        
    def processModeration(self, REQUEST):
        # a hook for handling the moderation stage of processing the email
        mailString = getMailFromRequest(REQUEST)
        
        # TODO: erradicate splitMail usage
        (header, body) = MailBoxerTools.splitMail(mailString)

        msg = EmailMessage(mailString, 
          list_title=self.getProperty('title', ''), 
          group_id=self.getId(), site_id=self.getProperty('siteId', ''), 
          sender_id_cb=self.get_mailUserId)
        
        # Get members
        try:
            memberlist = MailBoxerTools.lowerList(self.getValueFor('mailinlist'))
        except:
            memberlist = MailBoxerTools.lowerList(self.getValueFor('maillist'))
            
        # Get individually moderated members
        moderatedlist = filter(None, 
                               MailBoxerTools.lowerList(self.getValueFor('moderatedlist') or []))
        
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
            self.mail_reply(self, REQUEST, mail=header, body=body)
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
                    'groupName': self.title,
                    'groupEmail': self.getValueFor('mailto'),
                    'subject': msg.subject,
                    'mid': msg.post_id,
                    'body': msg.body,
                    'absolute_url': self.absolute_url(),
                    'moderatedUserName': moderatedUser.getProperty('preferredName','')}
                  moderator.send_notification('mail_moderator', 'default',
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
              'moderatedUserName': moderatedUser.getProperty('preferredName','')}

            moderatedUser.send_notification('mail_moderated_user', 
              'default', n_dict=nDict)
            
            return msg.sender
        
    def _create_mailObject(self, msg, archive):
        # do the dirty work to tidy up the legacy aspects of manage_addMail
        
        # if 'keepdate' is set, get date from mail,
        if self.getValueFor('keepdate'):
            time = DateTime(msg.date.isoformat())
        # ... take our own date, clients are always lying!
        else:
            time = DateTime()
        
        # let's create the mailObject
        mailFolder = archive
        
        mailFolder.manage_addFolder(str(msg.post_id), msg.title)
        mailObject = getattr(mailFolder, str(msg.post_id))
        
        # and now add some properties to our new mailobject
        props = list(mailObject._properties)
        for prop in props:
            if prop['id'] == 'title':
                prop['type'] = 'ustring'
                
        mailObject._properties = tuple(props)
        mailObject.title = msg.title
        
        mailObject.manage_addProperty('topic_id', msg.topic_id, 'ustring')
        
        mailObject.manage_addProperty('mailFrom', msg.sender, 'ustring')
        mailObject.manage_addProperty('mailSubject', msg.subject, 'ustring')
        mailObject.manage_addProperty('mailDate', time, 'date')
        mailObject.manage_addProperty('mailBody', msg.body, 'utext')
        mailObject.manage_addProperty('compressedSubject', msg.compressed_subject, 'ustring')
        
        mailObject.manage_addProperty('headers', msg.headers, 'utext')
        
        mailObject.manage_addProperty('mailUserId', msg.sender_id, 'ustring')

        return mailObject

    security.declareProtected('Add Folders', 'manage_addMail')
    def manage_addMail(self, msg):
        """ Store mail & attachments in a folder and return it.
        
        """
        archive = self.restrictedTraverse(self.getValueFor('storage'), 
                                          default=None)
        
        if archive:
            mailObject = self._create_mailObject(msg, archive)
            
        ids = []
        for attachment in msg.attachments:
            if attachment['filename'] == '' and attachment['subtype'] == 'plain':
                # We definately don't want to save the plain text body again!
                pass
            elif attachment['filename'] == '' and attachment['subtype'] == 'html':
                # We might want to do something with the HTML body some day
                m = '%s (%s): stripped, but not archiving %s attachment '\
                  '%s; it appears to be part of an HTML message.' % \
                  (self.getProperty('title'), self.getId(),
                   attachment['maintype'], attachment['filename'])
                log.info(m)
            elif attachment['contentid']:
                # --=mpj17=-- ?
                m = '%s (%s): stripped, but not archiving %s attachment '\
                  '%s; it appears to be part of an HTML message.' % \
                  (self.getProperty('title'), self.getId(),
                   attachment['maintype'], attachment['filename'])
                log.info(m)
            else:
                m = '%s (%s): stripped and archiving %s attachment %s' %\
                  (self.getProperty('title'), self.getId(),
                   attachment['maintype'], attachment['filename'])
                log.info(m)
                
                if archive:
                    id = self.addMailBoxerFile(mailObject, 
                                               None, 
                                               attachment['filename'], 
                                               attachment['payload'], 
                                               attachment['mimetype'])
                else:
                    id = self.addGSFile(attachment['filename'], 
                                        msg.subject, 
                                        msg.sender_id, 
                                        attachment['payload'], 
                                        attachment['mimetype'])
                ids.append(id)
        
        if archive and ids:
            mailObject.manage_addProperty('x-xwfnotification-file-id', 
                                          ' '.join(ids), 'ustring')
            mailObject.manage_addProperty('x-xwfnotification-message-length', 
                                          len(msg.body.replace('\r', '')), 'ustring')

        # if this is a post from the web, we may have also been passed the
        # file ID in the header

        file_ids = msg.get('x-xwfnotification-file-id')
        if file_ids:
            ids = ids+filter(None, file_ids.strip().split())
            file_notification_message_length = msg.get('x-xwfnotification-message-length')
            # if we are archiving to ZODB, update now
            if archive and file_ids and file_notification_message_length:
                mailObject.manage_addProperty('x-xwfnotification-file-id', 
                                              file_ids, 'ustring')
                mailObject.manage_addProperty('x-xwfnotification-message-length', 
                                              file_notification_message_length, 'ustring')

        if archive:
            self.catalogMailBoxerMail(mailObject)

        if self.getProperty('use_rdb', False):
            msgstorage = IRDBStorageForEmailMessage(msg)
            
            da = self.site_root().zsqlalchemy
            
            msgstorage.set_zalchemy_adaptor(da)
            msgstorage.insert()
            msgstorage.insert_keyword_count()
            
            filemetadatastorage = RDBFileMetadataStorage(self, msg, ids)
            filemetadatastorage.set_zalchemy_adaptor(da)
            filemetadatastorage.insert()
        
        if archive:
            return (mailObject.getId(), ids)
        else:
            return (msg.post_id, ids)
    
    def is_senderBlocked(self, user_id):
        """ Get the sendercache entry for a particular user.

            Returns a tuple containing:
            (isblocked (boolean), unblock time (datetime))
        """

         # TODO
         # --=mpj17=-- This needs to be converted to use the new 
         # IGSMessagePosting adaptors.

        senderlimit = self.getValueFor('senderlimit')
        senderinterval = self.getValueFor('senderinterval')
        user = self.acl_users.getUserById(user_id)
        
        ptnCoachId = self.getProperty('ptn_coach_id', '')

        retval = (False, -1) # Uncharacteristic optimism
        if user.getId() != ptnCoachId:
            for email in user.get_emailAddresses():
                ntime = int(time.time())
                count = 0
                etime = ntime-senderinterval
                earliest = 0
                for atime in self.sendercache.get(email, []):
                    if atime > etime:
                        if not earliest or atime < earliest:
                            earliest = atime
                        count += 1
                    else:
                        break

                if count >= senderlimit:
                    retval = (True, DateTime(earliest+senderinterval))
                    break
        return retval

    def checkMail(self, REQUEST):
        # Check for ip, loops and spam.

        # Check for correct IP
        mtahosts = self.getValueFor('mtahosts')
        if mtahosts:
            if 'HTTP_X_FORWARDED_FOR' in self.REQUEST.environ.keys():
                REMOTE_IP = self.REQUEST.environ['HTTP_X_FORWARDED_FOR']
            else:
                REMOTE_IP = self.REQUEST.environ['REMOTE_ADDR']

            if REMOTE_IP not in mtahosts:
                message = '%s (%s): Host %s is not allowed' %\
                  (self.getProperty('title', ''), self.getId(), REMOTE_IP)
                log.error(message)
                return message

        # Check for x-mailer-loop
        mailString = getMailFromRequest(REQUEST)
        msg = EmailMessage(mailString, list_title=self.getProperty('title', ''), 
                                       group_id=self.getId(), 
                                       site_id=self.getProperty('siteId', ''), 
                                       sender_id_cb=self.get_mailUserId)
        m  = '%s (%s): processing message from <%s>' %\
          (self.getProperty('title', ''), self.getId(), msg.sender)
        log.info(m)
                
        if msg.get('x-mailer') == self.getValueFor('xmailer'):
            message = '%s (%s): X-Mailer header detected, a loop is '\
              'likely' % (self.getProperty('title', ''), self.getId())
            log.error(message)
            return message
        
        # Check for empty return-path => automatic mail
        if msg.get('return-path') == '<>':
            message = '%s (%s): automated response detected from <%s>' %\
              (self.getProperty('title', ''), self.getId(), msg.get('from', '<>'))
            log.error(message)
            return message
        
        # Check for hosed denial-of-service-vacation mailers
        # or other infinite mail-loops...
        email = msg.sender
        sender_id = msg.sender_id
        user = None
        
        disabled = list(self.getValueFor('disabled'))

        if email in disabled:
            message = '%s (%s): Email address <%s> is disabled.' %\
              (self.getProperty('title', ''), self.getId(), email)
            log.error(message)
            return message
        
        senderlimit = self.getValueFor('senderlimit')
        senderinterval = self.getValueFor('senderinterval')
        unsubscribe = self.getValueFor('unsubscribe')
        
        # A sanity check ... was this email the last one we saw (tight loop)?
        # TODO: expand this to check the archives
        if self.last_email_checksum and (self.last_email_checksum == msg.post_id):
            message = '%s (%s): Detected duplicate message from <%s>' % \
              (self.getProperty('title', ''), self.getId(), msg.get('from'))
            log.error(message)
            return message

        # if the person is unsubscribing, we can't handle it with the loop
        # stuff, because they might easily exceed it if it is a tight setting
        if unsubscribe != '' and check_for_commands(msg, unsubscribe):
            pass
        
        elif senderlimit and senderinterval:
            sendercache = self.sendercache

            ntime = int(DateTime())

            count = 0
            etime = ntime-senderinterval
            earliest = 0
            for atime in sendercache.get(email, []):
                if atime > etime:
                    if not earliest or atime < earliest:
                        earliest = atime
                    count += 1
                else:
                    break

            if sender_id:
                user = self.acl_users.getUser(sender_id)
            ptnCoachId = self.getProperty('ptn_coach_id', '')

            if count >= senderlimit:
                if  user and (user.getId() != ptnCoachId):
                    expTime = DateTime(earliest+senderinterval)
                    expTime = munge_date(self, expTime)
                    user.send_notification('sender_limit_exceeded', 
                                           self.listId(), 
                                           n_dict={'expiry_time': expTime, 
                                                   'email': mailString})
                    rm = r'%s (%s): user %s (%s) has sent %s mails in %s seconds'
                    message = (rm % (self.getProperty('title', ''), 
                      self.getId(), user.getProperty('fn', ''), user.getId(), 
                      count, senderinterval))
                    log.error(message)
                    
                    self.last_email_checksum = msg.post_id
            
                    return message

            # this only happens if we're not already blocking
            if sendercache.has_key(email):
                sendercache[email].insert(0, ntime)
            else:
                sendercache[email] = [ntime]
            
            # prune our cache back to the limit
            sendercache[email] = sendercache[email][:senderlimit+1]
            
            self.sendercache = sendercache

        self.last_email_checksum = msg.post_id
        
        # Check for spam
        for regexp in self.getValueFor('spamlist'):
            if regexp and re.search(regexp, mailString):
                message = '%s (%s): Spam detected: %s\n\n%s\n' %\
                  (self.getProperty('title', ''), self.getId(), regexp, mailString)
                log.error(message)
                return message
        
        # GroupServer specific checks
        blocked_members = filter(None, self.getProperty('blocked_members', []))
        required_properties = filter(None, self.getProperty('required_properties', []))
        
        if sender_id:
            user = self.acl_users.getUser(sender_id)
        if (blocked_members or required_properties) and user:
            if user and user.getId() in blocked_members:
                message = '%s (%s): Blocked user %s (%s) from posting' %\
                  (self.getProperty('title', ''), self.getId(), 
                   user.getProperty('fn', ''), user.getId())
                log.error(message)
                user.send_notification('post_blocked', self.listId(), 
                                       n_dict={'email': mailString})
                return message
            
            for required_property in required_properties:
                # we just test for existence, and being set.
                # for backward compatibility we test for the string being
                # set to the string 'None' too.
                prop_val = str(user.getProperty(required_property, None))
                prop_val = prop_val.strip()
                if not prop_val or prop_val == 'None':
                    message = '%s (%s) blocked user %s (%s) because of '\
                      'missing user property %s' %\
                        (self.getProperty('title', ''), self.getId(), 
                         user.getProperty('fn', ''), user.getId(),
                         required_property)
                    log.error(message)
                    user.send_notification('missing_properties', self.listId(), 
                                           n_dict={'email': mailString})
                    return message
    
        # look to see if we have a custom_mailcheck hook. If so, call it.
        # custom_mailcheck should return True if the message is to be blocked
        custom_mailcheck = getattr(self, 'custom_mailcheck', None)
        if custom_mailcheck:
            if custom_mailcheck(mailinglist=self, sender=email, header=msg, body=msg.body):
                return message

    def requestMail(self, REQUEST):
        # Handles requests for subscription changes

        mailString = getMailFromRequest(REQUEST)

        # TODO: this needs to be completely removed, but some of the email
        # depends on it still
        (header, body) = MailBoxerTools.splitMail(mailString)

        msg = EmailMessage(mailString, list_title=self.getProperty('title', ''), 
                                       group_id=self.getId(), 
                                       site_id=self.getProperty('siteId', ''), 
                                       sender_id_cb=self.get_mailUserId)
        
        # get subject
        subject = msg.subject

        # get email-address
        email = msg.sender
        
        memberlist = MailBoxerTools.lowerList(self.getValueFor('mailinlist'))
        
        # process digest commands
        if email in memberlist and msg.sender_id:
            user = self.acl_users.getUser(msg.sender_id)
            if check_for_commands(msg, 'digest on'):
                user.set_enableDigestByKey(self.getId())
                self.mail_digest_on(self, REQUEST, mail=header, body=body)
                
                return email
            
            elif check_for_commands(msg, 'digest off'):
                user.set_disableDigestByKey(self.getId())
                self.mail_digest_off(self, REQUEST, mail=header, body=body)
                
                return email 
        
        # subscription? only subscribe if subscription is enabled.
        subscribe = self.getValueFor('subscribe')
        if subscribe != '' and check_for_commands(msg, subscribe):
            if email not in memberlist:
                if subject.find(pin(email, self.getValueFor('hashkey'))) != -1:
                    self.manage_addMember(email)
                else:
                    user = self.acl_users.get_userByEmail(email)
                    if user: # if the user exists, send out a subscription email
                        self.mail_subscribe_key(self, REQUEST, msg )
                    else: # otherwise handle subscription as part of registration
                        # --=mpj17=-- TODO: Update this to the new system.
                        user_id, password, verification_code = \
                                 self.acl_users.register_user(email=email, 
                                                              preferred_name=msg.name)
                        user = self.acl_users.getUser(user_id)
                        group_object = self.Scripts.get.group_by_id(self.getId())
                        
                        division = group_object.Scripts.get.division_object()
                        div_groups = division.groups_with_local_role('DivisionMember')
                        div_mem = None
                        if len(div_groups) == 1:
                            div_mem = div_groups[0]
                        if div_mem:
                            v_groups = ['%s_member' % self.getId(), div_mem]
                        else:
                            v_groups = ['%s_member' % self.getId()]
                            
                        user.set_verificationGroups(v_groups)
                        user.send_userVerification()
            else:
                self.mail_reply(self, REQUEST, mail=header, body=body)

            return email

        # unsubscription? only unsubscribe if unsubscription is enabled...
        unsubscribe = self.getValueFor('unsubscribe')
        if unsubscribe != '' and check_for_commands(msg, unsubscribe):
            if email.lower() in memberlist:
                if subject.find(pin(email, self.getValueFor('hashkey'))) != -1:
                    self.manage_delMember(email)
                else:
                    self.mail_unsubscribe_key(self, REQUEST, msg)
            else:
                self.mail_reply(self, REQUEST, mail=header, body=body)

            return email
    
    def manage_digestBoxer(self, REQUEST):
        """ Send out a digest of topics to users who have
	    requested it.
        
	    """
        memberlist = MailBoxerTools.lowerList(self.getValueFor('digestmaillist'))
        maillist = []
        for email in memberlist:
            if '@' in email and email not in maillist:
                maillist.append(email)
        
        # if no digestreturnpath is set, use first moderator as returnpath
        returnpath=self.getValueFor('digestreturnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]
        
        digest = self.xwf_email_topic_digest(REQUEST, list_object=self, 
                                             getValueFor=self.getValueFor)
        
        if ((MaildropHostIsAvailable and
             getattr(self, "MailHost").meta_type=='Maildrop Host')
            or (SecureMailHostIsAvailable and
                getattr(self, "MailHost").meta_type=='Secure Mail Host')):
            TransactionalMailHost = getattr(self, "MailHost")
            # Deliver each mail on its own with a transactional MailHost
            batchsize = 1
        else:
            TransactionalMailHost = None
            batchsize = self.getValueFor('batchsize')
        
        # start batching mails
        while maillist:
            # if no batchsize is set (default)
            # or batchsize is greater than maillist,
            # bulk all mails in one batch,
            # otherwise bulk only 'batch'-mails at once

            if (batchsize == 0) or (batchsize > len(maillist)):
                batch = len(maillist)
            else:
                batch = batchsize
            
            if TransactionalMailHost:
                TransactionalMailHost._send(returnpath, maillist[0:batch], digest)
            else:
                smtpserver = smtplib.SMTP(self.MailHost.smtp_host, 
                                          int(self.MailHost.smtp_port))
                smtpserver.sendmail(returnpath, maillist[0:batch], digest)
                smtpserver.quit()

            # remove already bulked addresses
            maillist = maillist[batch:]
            	
    security.declareProtected('Manage properties', 'manage_addMember')
    def manage_addMember(self, email):
        """ Add member to group. """

        user = self.acl_users.get_userByEmail(email)
        if user:
            user.add_groupWithNotification('%s_member' % self.getId())
        
        return 1

    security.declareProtected('Manage properties', 'manage_delMember')
    def manage_delMember(self, email):
        """ Remove member from group. """
        
        user = self.acl_users.get_userByEmail(email)
        if user:
            user.del_groupWithNotification('%s_member' % self.getId())
        
        return 1
    
    def get_mailUserId(self, addr):
        """ From the email address, get the user's ID.

        """
        return self.acl_users.get_userIdByEmail(addr) or ''

    security.declareProtected('Add Folders', 'catalogMailBoxerMail')
    def catalogMailBoxerMail(self, MailBoxerMail):
        """ Catalogs MailBoxerFile. """

        # Index the new created mailFolder in the catalog
        Catalog = self.unrestrictedTraverse(self.getValueFor('catalog'),
                                            default=None)
        if Catalog is not None:
            Catalog.catalog_object(MailBoxerMail)
  
    security.declareProtected('Manage properties', 'reindex_mailObjects')
    def reindex_mailObjects(self):
        """ Reindex the mailObjects that we contain.
             
        """
        for object in self.archive.objectValues('Folder'):
            if hasattr(object, 'mailFrom'):
                pp = '/'.join(object.getPhysicalPath())
                self.Catalog.uncatalog_object(pp)
                self.Catalog.catalog_object(object, pp)
         
        return True

    security.declareProtected('Manage properties', 'unindex_mailObjects')
    def unindex_mailObjects(self):
        """ Unindex the mailObjects that we contain.

            Handy for playing with a single list without having to reindex
            all lists!
        """
        for object in self.archive.objectValues('Folder'):
            if hasattr(object, 'mailFrom'):
                pp = '/'.join(object.getPhysicalPath())
                self.Catalog.uncatalog_object(pp)

        return True
    
    def parseaddr(self, header):
        # wrapper for rfc822.parseaddr, returns (name, addr)
        return MailBoxerTools.parseaddr(header)
    
    security.declarePrivate('mail_reply')
    def mail_reply(self, context, REQUEST, mail=None, body=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        smtpserver = smtplib.SMTP(self.MailHost.smtp_host, 
                              int(self.MailHost.smtp_port))
                
        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]
            
        reply = getattr(self, 'xwf_email_reply', None)
        
        email_address = mail['from']
        
        if reply:
            reply_text = reply(REQUEST, list_object=context, 
                               mail=mail, body=body)
            smtpserver.sendmail(returnpath, [email_address], reply_text)
        smtpserver.quit()            

    security.declarePrivate('mail_subscribe_key')
    def mail_subscribe_key(self, context, REQUEST, msg):
        """ Email out a subscription authentication notification.
        
        """
        smtpserver = smtplib.SMTP(self.MailHost.smtp_host, 
                              int(self.MailHost.smtp_port))
                
        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]
            
        reply = getattr(self, 'email_subscribe_key', None)
        
        thepin = pin( msg.sender, self.getValueFor('hashkey') )

        member = self.acl_users.getUser(msg.sender_id)
        memberName = member.getProperty('preferredName','')
        
        if reply:
            reply_text = reply(REQUEST, list_object=context, 
                                   getValueFor=self.getValueFor, 
                                   pin=thepin,
                                   email=msg.sender,
                                   sender_id=msg.sender_id,
                                   member_name=memberName)
            
            smtpserver.sendmail(returnpath, [msg.sender], reply_text)
        smtpserver.quit()


    security.declarePrivate('mail_unsubscribe_key')
    def mail_unsubscribe_key(self, context, REQUEST, msg):
        """ Email out an unsubscription authentication notification.
        
        """
        smtpserver = smtplib.SMTP(self.MailHost.smtp_host, 
                              int(self.MailHost.smtp_port))
                
        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]
            
        reply = getattr(self, 'email_unsubscribe_key', None)
        
        thepin = pin( msg.sender, self.getValueFor('hashkey') )
        
        member = self.acl_users.getUser(msg.sender_id)
        memberName = member.getProperty('preferredName','')

        if reply:
            reply_text = reply(REQUEST, list_object=context, 
                                   getValueFor=self.getValueFor, 
                                   pin=thepin,
                                   email=msg.sender,
                                   sender_id=msg.sender_id,
                                   member_name=memberName)
            
            smtpserver.sendmail(returnpath, [msg.sender], reply_text)
        else:
            pass
            
        smtpserver.quit()

    security.declarePrivate('mail_digest_on')
    def mail_digest_on(self, context, REQUEST, mail=None, body=''):
        """ Send out a message that the digest feature has been turned on.
        
        """
        smtpserver = smtplib.SMTP(self.MailHost.smtp_host, 
                              int(self.MailHost.smtp_port))
                
        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]
            
        reply = getattr(self, 'xwf_email_digest_on', None)
        
        email_address = mail['from']
        
        if reply:
            reply_text = reply(REQUEST, list_object=context, 
                                   getValueFor=self.getValueFor, 
                                   mail=mail, body=body)
            smtpserver.sendmail(returnpath, [email_address], reply_text)
        else:
            pass
            
        smtpserver.quit()

    security.declarePrivate('mail_digest_off')
    def mail_digest_off(self, context, REQUEST, mail=None, body=''):
        """ Send out a message that the digest feature has been turned off.
        
        """
        smtpserver = smtplib.SMTP(self.MailHost.smtp_host, 
                              int(self.MailHost.smtp_port))
                
        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]
            
        reply = getattr(self, 'xwf_email_digest_off', None)
        
        email_address = mail['from']
        
        if reply:
            reply_text = reply(REQUEST, list_object=context, 
                                   getValueFor=self.getValueFor, 
                                   mail=mail, body=body)
            smtpserver.sendmail(returnpath, [email_address], reply_text)
        else:
            pass
            
        smtpserver.quit()

    security.declarePrivate('mail_event_default')
    def mail_event_default(self, context, event_codes, headers):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        smtpserver = smtplib.SMTP(self.MailHost.smtp_host, 
                              int(self.MailHost.smtp_port))
                
        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]
        
        email_address = headers.get('from', '')
        seen = []
        for code in event_codes:
            if code in seen: continue
            reply = getattr(self, 'xwf_email_event', None)
            
            if reply:
                reply_text = reply(list_object=context, event_code=code, headers=headers)
                if reply_text and email_address:
                    smtpserver.sendmail(returnpath, [email_address], reply_text)
            else:
                pass
            seen.append(code)
            
        smtpserver.quit()
    
    security.declarePrivate('mail_header')
    def mail_header(self, context, REQUEST, getValueFor=None, title='', 
                          mail=None, body='', file_ids=(), post_id=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        header = getattr(self, 'xwf_email_header', None)
        if header:
            return header(REQUEST, list_object=context, 
                                   getValueFor=getValueFor, 
                                   title=title, mail=mail, body=body, 
                                   file_ids=file_ids, 
                                   post_id=post_id)
        else:
            return ""
    
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
        
            This is used instead of addMailBoxerFile if we are *only* using
            the relational database.
            
        """
        # TODO: group ID should be more robust
        group_id = self.getId()
        storage = self.FileLibrary2.get_fileStorage()
        id = storage.add_file(data)
        file = storage.get_file(id)
        file.manage_changeProperties(content_type=content_type, title=title, tags=['attachment'], 
                                     group_ids=[group_id], dc_creator=creator, 
                                     topic=topic)
        file.reindex_file()
        
        #
        # Commit the ZODB transaction -- this basically makes it impossible for
        # us to rollback, but since our RDB transactions won't be rolled back
        # anyway, we do this so we don't have dangling metadata.
        # 
        transaction.commit()

        return id

    def addMailBoxerFile(self, archiveObject, id, title, data, content_type):
        """ Adds an attachment as File.
            
            This is mainly used by the moderation framework, unless the relational
            database is not being used.
            
        """
        # TODO: group ID should be more robust
        group_id = self.getId()
        storage = self.FileLibrary2.get_fileStorage()
        id = storage.add_file(data)
        file = storage.get_file(id)
        topic = archiveObject.getProperty('mailSubject', '')
        creator = archiveObject.getProperty('mailUserId', '')
        file.manage_changeProperties(content_type=content_type, title=title, tags=['attachment'], 
                                     group_ids=[group_id], dc_creator=creator, 
                                     topic=topic)
        file.reindex_file()
        
        return id        
  
    def export_as_mbox(self):
        """ Export our mailing list archives into mbox format, as best we can.
        
        """
        archive = self.restrictedTraverse(self.getValueFor('storage'), 
                                          default=None)
        
        self.REQUEST.RESPONSE.setHeader('Content-Type', 'application/mbox')
        
        export_archive_as_mbox(archive, group_id=self.getId(), 
                                site_id=self.getProperty('siteId', ''), 
                                group_title=self.getProperty('title', ''), 
                                writer=self.REQUEST.RESPONSE)

    def processSpool(self):
        #
        # run through the spool, and actually send the mail out
        #
        archive = self.restrictedTraverse(self.getValueFor('storage'))
        for spoolfilepath in os.listdir(MAILDROP_SPOOL):
            if os.path.exists(os.path.join(MAILDROP_SPOOL,
                                           '%s.lck' % spoolfilepath)):
                continue # we're locked
            spoolfile = file(os.path.join(MAILDROP_SPOOL, spoolfilepath))
            line = spoolfile.readline().strip()
            if len(line) < 5 or line[:2] != ';;' or line[-2:] != ';;':
                log.error('Spooled email has no group specified')
                continue

            groupname = line[2:-2]
            if self.getId() != groupname:
                continue # not for us
                     
            mailString = spoolfile.read()
            (header, body) = self.splitMail(mailString)
            
            # a robustness check -- if we an archive ID, and we aren't in
            # the archive, what are we doing here?
            archive_id = header.get('x-archive-id', None)
            log.error('archive_id = "%s"' % archive_id)
            if archive_id and not hasattr(archive.aq_explicit,
                                          archive_id.strip()):
                m= 'Spooled email had archive_id %s, but did not exist in '\
                  ' archive %s (%s)' %\
                  (archive_id, self.getProperty('title', ''), self.getId())
                log.error(m)
                continue

            self.sendMail(mailString)
            spoolfile.close()
            os.remove(spoolfilepath)
            # sleep a little
            time.sleep(0.5)

    def sendMail(self, mailString):
        # actually send the email

        # Get members
        memberlist = self.getValueFor('maillist')

        # Remove "blank" / corrupted / doubled entries
        maillist=[]
        for email in memberlist:
            if '@' in email and email not in maillist:
                maillist.append(email)

        # if no returnpath is set, use first moderator as returnpath
        returnpath=self.getValueFor('returnpath')
        
        mailoptions = self.getValueFor('mailoptions')
        if not mailoptions:
            mailoptions = []

        # we want to handle bounces with XVERP
        if not returnpath and 'XVERP' in mailoptions:
            returnpath = self.getValueFor('mailto')
        elif not returnpath:
            returnpath = self.getValueFor('moderator')[0]
        
        if ((MaildropHostIsAvailable and
             getattr(self, "MailHost").meta_type=='Maildrop Host') 
            or (SecureMailHostIsAvailable and 
                getattr(self, "MailHost").meta_type=='Secure Mail Host')):
            TransactionalMailHost = getattr(self, "MailHost")
            # Deliver each mail on its own with a transactional MailHost
            batchsize = 50
        else:
            TransactionalMailHost = None
            batchsize = self.getValueFor('batchsize')

        # start batching mails
        while maillist:
            # if no batchsize is set (default)
            # or batchsize is greater than maillist,
            # bulk all mails in one batch,
            # otherwise bulk only 'batch'-mails at once
            if (batchsize == 0) or (batchsize > len(maillist)):
                batch = len(maillist)
            else:
                batch = batchsize

            if TransactionalMailHost:
                 TransactionalMailHost._send(returnpath, maillist[0:batch], mailString)
            else:
                smtpserver = smtplib.SMTP(self.MailHost.smtp_host,
                                          int(self.MailHost.smtp_port))
                smtpserver.sendmail(returnpath, maillist[0:batch], mailString, mail_options=mailoptions)
                smtpserver.quit()

            # remove already bulked addresses
            maillist = maillist[batch:]

    
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
        
