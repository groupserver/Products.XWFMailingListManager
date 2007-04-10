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
from export import export_archive_as_mbox
from emailmessage import RDBFileMetadataStorage
from AccessControl import getSecurityManager, ClassSecurityInfo

from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Products.CustomProperties.CustomProperties import CustomProperties
from Globals import InitializeClass, PersistentMapping
from OFS.Folder import Folder, manage_addFolder

from Products.MailBoxer.MailBoxer import *
from Acquisition import ImplicitAcquisitionWrapper, aq_base, aq_parent
from App.config import getConfiguration

from emailmessage import EmailMessage, IRDBStorageForEmailMessage

from cgi import escape

from zLOG import LOG, WARNING

import md5
import os

def convert_date(date):
    import time
    from email.Utils import parsedate
    
    return time.asctime(parsedate(date))

def convert_addrs(field):
    import time
    from rfc822 import AddressList
    
    return map(lambda x: x[1], AddressList(field).addresslist)

def convert_encoding_to_default(s, possible_encoding):
    for try_encoding in (possible_encoding, 'utf-8', 'iso-8859-1', 'iso-8859-15'):
            try:
                s = s.decode(try_encoding)
                s.encode(getConfiguration().default_zpublisher_encoding or 'utf-8')
                break
            except (UnicodeDecodeError, LookupError):
                pass
            
    return s

def check_unsubscribe():
    pass

def check_subscribe():
    pass

def check_digest_on():
    pass

def check_digest_off():
    pass

null_convert = lambda x: x

class XWFMailingList(MailBoxer):
    """ A mailing list implementation, based heavily on the excellent Mailboxer
    product.

    """
    security = ClassSecurityInfo()
    meta_type = 'XWF Mailing List'
    version = 0.34
    
    # a tuple of properties that we _don't_ want to inherit from the parent
    # list manager
    mailinglist_properties = ('title', 
                              'mailto', 
                              'hashkey')
    
    # track the checksum of the last email sent
    last_email_checksum = ''
    
    def __init__(self, id, title, mailto):
        """ Setup a MailBoxer with reasonable defaults.
        
        """
        MailBoxer.__init__(self, id, title)
        
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
    def get_memberUserObjects(self):
        """ Get the user objects corresponding to the membership list, assuming we can.
        
        """
        member_groups = self.getProperty('member_groups', ['%s_member' % self.listId()])
        uids = []
        for gid in member_groups:
            group = self.acl_users.getGroupById(gid)
            uids += group.getUsers()
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
    def get_moderatedUserObjects(self):
        """ Get the user objects corresponding to the moderated list, assuming we can.
        
        """
        member_groups = self.getProperty('moderated_groups', [])
        uids = []
        for gid in member_groups:
            group = self.acl_users.getGroupById(gid)
            uids += group.getUsers()
        
        uids += self.getProperty('moderated_members', [])
        
        users = []
        for uid in uids:
            user = self.acl_users.getUser(uid)
            if user:
                users.append(user)
                
        return users
    
    security.declareProtected('Manage properties', 'get_moderatorUserObjects')
    def get_moderatorUserObjects(self):
        """ Get the user objects corresponding to the moderator, assuming we can.
        
        """
        member_groups = self.getProperty('moderator_groups', [])
        uids = []
        for gid in member_groups:
            group = self.acl_users.getGroupById(gid)
            uids += group.getUsers()
        
        uids += self.getProperty('moderator_members', [])
        
        users = []
        for uid in uids:
            user = self.acl_users.getUser(uid)
            if user:
                users.append(user)
                
        return users
       
    security.declareProtected('Access contents information', 'getValueFor')
    def getValueFor(self, key):
        """ getting the maillist and moderatedlist is a special case, working
            in with the XWFT group framework.
        
        """
        pass_group_id = False
        if key in ('digestmaillist', 'maillist', 'moderator', 'moderatedlist', 'mailinlist'):
            maillist = []
            if key in ('digestmaillist', 'maillist'):
                address_getter = 'get_deliveryEmailAddressesByKey'
                member_getter = 'get_memberUserObjects'
                pass_group_id = True
                maillist_script = getattr(self, 'maillist_members', None)
            elif key in ('moderator',):
                address_getter = 'get_emailAddresses'
                member_getter = 'get_moderatorUserObjects'
                maillist_script = None
                maillist = self.aq_inner.getProperty('moderator', [])
                if not maillist:
                    maillist = self.aq_parent.getProperty('moderator', [])
            elif key in ('moderatedlist',):
                address_getter = 'get_emailAddresses'
                member_getter = 'get_moderatedUserObjects'
                maillist_script = None
                maillist = self.aq_inner.getProperty('moderatedlist', [])
                if not maillist:
                    maillist = self.aq_parent.getProperty('moderatedlist', [])
            else:
                address_getter = 'get_emailAddresses'
                member_getter = 'get_memberUserObjects'
                maillist_script = getattr(self, 'mailinlist_members', None)
                
            # look for a maillist script
            if maillist_script:
                return maillist_script()
                
            try:
                users = getattr(self, member_getter)()
                maillist = list(maillist) # make sure we're not a tuple!
                for user in users:
                    # we're looking to send out regular email, but this user is set to digest
                    if key == 'maillist' and user.get_deliverySettingsByKey(self.getId()) == 3:
                        continue
                    elif key == 'digestmaillist' and user.get_deliverySettingsByKey(self.getId()) != 3:
                        continue

                    try:
                        if pass_group_id:
                            addresses = getattr(user, address_getter)(self.getId())
                        else:
                            addresses = getattr(user, address_getter)()
                    except:
                        continue
                    for email in addresses:
                        email = email.strip()
                        if email and email not in maillist:
                            maillist.append(email)
            except Exception, x:
                LOG('XWFMailingList', PROBLEM, 
                    'A problem was experienced while getting values: %s' % x)
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
        
    def tidy_subject(self, subject, strip_listid=1, reduce_whitespace=1):
        """ A helper method for tidying the subject line.
        
        """
        import re
        if strip_listid:
            subject = re.sub('\[%s\]' % re.escape(self.getValueFor('title')), '', subject).strip()
        if reduce_whitespace:
            subject = re.sub('\s+', ' ', subject).strip()
        
        return subject
        
    def create_mailableSubject(self, subject, include_listid=1):
        """ A helper method for tidying up the mailing list subject for remailing.
        
        """
        # there is an assumption that if we're including a listid we should
        # strip any existing listid reference
        subject = self.tidy_subject(subject, include_listid)
        
        is_reply = 0
        if subject.lower().find('re:', 0, 3) == 0 and len(subject) > 3:
            subject = subject[3:].strip()
            is_reply = 1
        
        re_string = '%s' % (is_reply and 'Re: ' or '')
        if include_listid:
            subject = '%s[%s] %s' % (re_string, self.getValueFor('title'), subject)
        else:
            subject = '%s%s' % (re_string, subject)
            
        return subject

    def listMail(self, REQUEST):
        # Shifted from MailBoxer till reintegration project
        
        # Send a mail to all members of the list.
        mailString = self.getMailFromRequest(REQUEST)
        
        msg = EmailMessage(mailString, list_title=self.getProperty('title', ''), 
                                       group_id=self.getId(), 
                                       site_id=self.getProperty('siteId', ''), 
                                       sender_id_cb=self.get_mailUserId)
        
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
        
        self.addMailBoxerMail(mailFolder, str(msg.post_id), msg.title)
        mailObject = getattr(mailFolder, str(msg.post_id))
        
        # and now add some properties to our new mailobject
        props = list(mailObject._properties)
        for prop in props:
            if prop['id'] == 'title':
                prop['type'] = 'ustring'
                
        mailObject._properties = tuple(props)
        mailObject.title = msg.title
        
        self.setMailBoxerMailProperty(mailObject, 'topic_id', msg.topic_id, 'ustring')
        
        self.setMailBoxerMailProperty(mailObject, 'mailFrom', msg.sender, 'ustring')
        self.setMailBoxerMailProperty(mailObject, 'mailSubject', msg.subject, 'ustring')
        self.setMailBoxerMailProperty(mailObject, 'mailDate', time, 'date')
        self.setMailBoxerMailProperty(mailObject, 'mailBody', msg.body, 'utext')
        self.setMailBoxerMailProperty(mailObject, 'compressedSubject', msg.compressed_subject, 'ustring')
        
        self.setMailBoxerMailProperty(mailObject, 'headers', msg.headers, 'utext')
        
        self.setMailBoxerMailProperty(mailObject, 'mailUserId', msg.sender_id, 'ustring')

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
                LOG('MailBoxer', INFO, 'stripped, but not archiving attachment %s %s. Appeared to be part of an HTML message.' % (attachment['filename'], attachment['maintype']))
            elif attachment['contentid']:
                LOG('MailBoxer', INFO, 'stripped, but not archiving attachment %s %s. Appeared to be part of an HTML message.' % (attachment['filename'], attachment['maintype']))
            else:
                LOG('MailBoxer', INFO, 'stripped and archiving attachment %s %s' % (attachment['filename'], attachment['maintype']))
                
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
            self.setMailBoxerMailProperty(mailObject, 'x-xwfnotification-file-id', 
                                          ' '.join(ids), 'ustring')
            self.setMailBoxerMailProperty(mailObject, 'x-xwfnotification-message-length', 
                                          len(msg.body.replace('\r', '')), 'ustring')

        # if this is a post from the web, we may have also been passed the
        # file ID in the header

        file_ids = msg.get('x-xwfnotification-file-id')
        if file_ids:
            ids = ids+filter(None, file_ids.strip().split())
            file_notification_message_length = msg.get('x-xwfnotification-message-length')
            # if we are archiving to ZODB, update now
            if archive and file_ids and file_notification_message_length:
                self.setMailBoxerMailProperty(mailObject, 'x-xwfnotification-file-id', 
                                              file_ids, 'ustring')
                self.setMailBoxerMailProperty(mailObject, 'x-xwfnotification-message-length', 
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
        senderlimit = self.getValueFor('senderlimit')
        senderinterval = self.getValueFor('senderinterval')
        user = self.acl_users.getUserById(user_id)

        for email in user.get_emailAddresses():
            ntime = int(DateTime())
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
                return (True, DateTime(earliest+senderinterval))

        return (False, -1)

    def checkMail(self, REQUEST):
        # richard@iopen.net: this is mostly the same as the MailBoxer parent,
        # only with notification.
        
        # Check for ip, loops and spam.
        
        # Check for correct IP
        mtahosts = self.getValueFor('mtahosts')
        if mtahosts:
            if 'HTTP_X_FORWARDED_FOR' in self.REQUEST.environ.keys():
                REMOTE_IP = self.REQUEST.environ['HTTP_X_FORWARDED_FOR']
            else:
                REMOTE_IP = self.REQUEST.environ['REMOTE_ADDR']

            if REMOTE_IP not in mtahosts:
                message = 'Host %s is not allowed' % (REMOTE_IP)
                LOG('MailBoxer', PROBLEM, message)
                return message

        # Check for x-mailer-loop
        mailString = self.getMailFromRequest(REQUEST)
        msg = EmailMessage(mailString, list_title=self.getProperty('title', ''), 
                                       group_id=self.getId(), 
                                       site_id=self.getProperty('siteId', ''), 
                                       sender_id_cb=self.get_mailUserId)
        
        if msg.get('x-mailer') == self.getValueFor('xmailer'):
            message = 'X-Mailer header detected, a loop is likely'
            LOG('MailBoxer', PROBLEM, message)
            return message
        
        # Check for empty return-path => automatic mail
        if header.get('return-path', '') == '<>':
            self.bounceMail(REQUEST)
            message = 'Automated response detected from %s' % (header.get('from', 
                                                                          '<>'))
            LOG('MailBoxer', PROBLEM, message)
            return message
        
        # A sanity check ... was this email the last one we saw (tight loop)?
        # TODO: expand this to check the archives
        if self.last_email_checksum:
            if self.last_email_checksum == msg.post_id:
                message = 'Detected duplicate message from "%s"' % header.get('from', '')
                LOG('MailBoxer', PROBLEM, message)
                return message
        
        self.last_email_checksum = msg.post_id
        
        # Check for hosed denial-of-service-vacation mailers
        # or other infinite mail-loops...
        email = msg.sender
        subject = msg.get('subject', 'No Subject')
        sender_id = msg.sender_id
        
        disabled = list(self.getValueFor('disabled'))

        if email in disabled:
            message = 'Email address "%s" is disabled.' % sender
            LOG('MailBoxer', PROBLEM, message)
            return message
        
        senderlimit = self.getValueFor('senderlimit')
        senderinterval = self.getValueFor('senderinterval')
        unsubscribe = self.getValueFor('unsubscribe')
        
        # if the person is unsubscribing, we can't handle it with the loop
        # stuff, because they might easily exceed it if it is a tight setting
        if (unsubscribe != '' and
            re.match('(?i)' + unsubscribe + "|.*: " + unsubscribe, subject)):
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

            if count >= senderlimit:
                user = self.acl_users.getUser(sender_id)
                if user:
                    user.send_notification('sender_limit_exceeded', self.listId(), 
                                            n_dict={'expiry_time': DateTime(earliest+senderinterval), 
                                                    'email': mailString})
                    message = ('Sender %s has sent %s mails in %s seconds' %
                                              (sender, count, senderinterval))
                LOG('MailBoxer', PROBLEM, message)
                return message

            # this only happens if we're not already blocking
            if sendercache.has_key(email):
                sendercache[email].insert(0, ntime)
            else:
                sendercache[email] = [ntime]
            
            # prune our cache back to the limit
            sendercache[email] = sendercache[email][:senderlimit+1]
            
            self.sendercache = sendercache

        # Check for spam
        for regexp in self.getValueFor('spamlist'):
            if regexp and re.search(regexp, mailString):
                message = 'Spam detected: %s\n\n%s\n' % (regexp, mailString)
                LOG('MailBoxer', PROBLEM, message)
                return message
        
        # GroupServer specific checks
        blocked_members = filter(None, self.getProperty('blocked_members', []))
        required_properties = filter(None, self.getProperty('required_properties', []))
        
        if blocked_members or required_properties:
            user = self.acl_users.getUser(sender_id)
            if user and user.getId() in blocked_members:
                message = 'Blocked user "%s" from posting' % sender_id
                LOG('MailBoxer', PROBLEM, message)
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
                    message = 'Blocked user "%s" because of missing user properties' % sender_id
                    LOG('MailBoxer', PROBLEM, message)
                    user.send_notification('missing_properties', self.listId(), 
                                           n_dict={'email': mailString})
                    return message
    
        # look to see if we have a custom_mailcheck hook. If so, call it.
        # custom_mailcheck should return True if the message is to be blocked
        custom_mailcheck = getattr(self, 'custom_mailcheck', None)
        if custom_mailcheck:
            if custom_mailcheck(mailinglist=self, sender=email, header=header, body=body):
                return message

    def requestMail(self, REQUEST):
        # Handles un-/subscribe-requests.

        mailString = self.getMailFromRequest(REQUEST)
        (header, body) = self.splitMail(mailString)

        # get subject
        subject = self.mime_decode_header(header.get('subject', ''))

        # get email-address
        sender = self.mime_decode_header(header.get('from', ''))
        (name, email) = self.parseaddr(sender)
        
        memberlist = self.lowerList(self.getValueFor('mailinlist'))
        
        # process digest commands
        if email.lower() in memberlist:
            user = self.acl_users.get_userByEmail(email)
            digest_on = re.match('(?i)digest on', subject.strip())
            if user and digest_on:
                user.set_enableDigestByKey(self.getId())
                self.mail_digest_on(self, REQUEST, mail=header, body=body)
                
                return email
            
            digest_off = re.match('(?i)digest off', subject.strip())
            if user and digest_off:
                user.set_disableDigestByKey(self.getId())
                self.mail_digest_off(self, REQUEST, mail=header, body=body)
                
                return email 
                
        # subscription? only subscribe if subscription is enabled.
        subscribe = self.getValueFor('subscribe')
        if (subscribe <> '' and
            re.match('(?i)' + subscribe + "|.*: " + subscribe, subject)):

            if email.lower() not in memberlist:
                if subject.find(self.pin(sender))<>-1:
                    self.manage_addMember(email)
                    self.mail_subscribe(self, REQUEST, mail=header, body=body)
                else:
                    user = self.acl_users.get_userByEmail(email)
                    if user: # if the user exists, send out a subscription email
                        self.mail_subscribe_key(self, REQUEST, mail=header, body=body)
                    else: # otherwise handle subscription as part of registration
                        nparts = name.split()
                        if len(nparts) >= 2:
                            first_name = nparts[0]
                            last_name = ' '.join(nparts[1:])
                        elif len(nparts) == 1:
                            first_name = last_name = nparts[0]
                        else:
                            first_name = last_name = name
                        user_id, password, verification_code = \
                                 self.acl_users.register_user(email=email, 
                                                              first_name=first_name, 
                                                              last_name=last_name)
                        user = self.acl_users.getUser(user_id)
                        group_object = self.Scripts.get.group_by_id(self.getId())
                        #division_id = group_object.get_division_id()
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
        if (unsubscribe <> '' and
            re.match('(?i)' + unsubscribe + "|.*: " + unsubscribe, subject)):

            if email.lower() in memberlist:
                if subject.find(self.pin(sender))<>-1:
                    self.manage_delMember(email)
                    self.mail_unsubscribe(self, REQUEST, mail=header, body=body)
                else:
                    self.mail_unsubscribe_key(self, REQUEST, mail=header, body=body)
            else:
                self.mail_reply(self, REQUEST, mail=header, body=body)

            return email
    
    def manage_digestBoxer(self, REQUEST):
        """ Send out a digest of topics to users who have
	    requested it.
        
	    """
        memberlist = self.lowerList(self.getValueFor('digestmaillist'))
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
        addr = addr.lower().strip()
        member_users = self.get_memberUserObjects()
        for member_user in member_users:
            addrs = member_user.getProperty('emailAddresses', [])
            for member_addr in addrs:
                if member_addr.lower() == addr:
                    return member_user.getId()
                    
        return ''
    
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
            
    def correct_subjects(self):
        """ Correct the subject line by stripping out the group id.
        
        """
        id_string = '[%s]' % self.getProperty('title')
        subjects = []
        for object in self.archive.objectValues('Folder'):
            if hasattr(object, 'mailFrom'):
                subject = object.getProperty('mailSubject')
                subject = subject.replace(id_string, '').strip()
                if subject == '':
                    subject = 'No Subject'
                object.mailSubject = subject
        
        return True
    
    security.declarePrivate('mail_reply')
    def mail_reply(self, context, REQUEST, mail=None, body=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        import smtplib
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
        else:
            pass
            
        smtpserver.quit()

    security.declarePrivate('mail_subscribe_key')
    def mail_subscribe_key(self, context, REQUEST, mail=None, body=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        import smtplib
        smtpserver = smtplib.SMTP(self.MailHost.smtp_host, 
                              int(self.MailHost.smtp_port))
                
        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]
            
        reply = getattr(self, 'xwf_email_subscribe_key', None)
        
        email_address = mail['from']
        
        if reply:
            reply_text = reply(REQUEST, list_object=context, 
                                   getValueFor=self.getValueFor, 
                                   mail=mail, body=body)
            smtpserver.sendmail(returnpath, [email_address], reply_text)
        else:
            pass
            
        smtpserver.quit()

    security.declarePrivate('mail_subscribe')
    def mail_subscribe(self, context, REQUEST, mail=None, body=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        import smtplib
        smtpserver = smtplib.SMTP(self.MailHost.smtp_host, 
                              int(self.MailHost.smtp_port))
                
        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]
            
        reply = getattr(self, 'xwf_email_subscribe', None)
        
        email_address = mail['from']
        
        if reply:
            reply_text = reply(REQUEST, list_object=context, 
                                   getValueFor=self.getValueFor, 
                                   mail=mail, body=body)
            smtpserver.sendmail(returnpath, [email_address], reply_text)
        else:
            pass
            
        smtpserver.quit()
    
    security.declarePrivate('mail_unsubscribe')
    def mail_unsubscribe(self, context, REQUEST, mail=None, body=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        import smtplib
        smtpserver = smtplib.SMTP(self.MailHost.smtp_host, 
                              int(self.MailHost.smtp_port))
                
        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]
            
        reply = getattr(self, 'xwf_email_unsubscribe', None)
        
        email_address = mail['from']
        
        if reply:
            reply_text = reply(REQUEST, list_object=context, 
                                   getValueFor=self.getValueFor, 
                                   mail=mail, body=body)
            smtpserver.sendmail(returnpath, [email_address], reply_text)
        else:
            pass
            
        smtpserver.quit()

    security.declarePrivate('mail_unsubscribe_key')
    def mail_unsubscribe_key(self, context, REQUEST, mail=None, body=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        import smtplib
        smtpserver = smtplib.SMTP(self.MailHost.smtp_host, 
                              int(self.MailHost.smtp_port))
                
        returnpath=self.getValueFor('returnpath')
        if not returnpath:
            returnpath = self.getValueFor('moderator')[0]
            
        reply = getattr(self, 'xwf_email_unsubscribe_key', None)
        
        email_address = mail['from']
        
        if reply:
            reply_text = reply(REQUEST, list_object=context, 
                                   getValueFor=self.getValueFor, 
                                   mail=mail, body=body)
            smtpserver.sendmail(returnpath, [email_address], reply_text)
        else:
            pass
            
        smtpserver.quit()

    security.declarePrivate('mail_digest_on')
    def mail_digest_on(self, context, REQUEST, mail=None, body=''):
        """ Send out a message that the digest feature has been turned on.
        
        """
        import smtplib
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
        import smtplib
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
        import smtplib
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
                text = unicode(text, 'utf-8','ignore')
            
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
        
    security.declareProtected('View', 'manage_inboxer')
    def manage_inboxer(self, REQUEST):
        """ Wrapper to mail directly into archive.

            This is just a wrapper method if you
            want to use MailBoxer as mailarchive-system.
        """
        # Shifted from XWFMailingListManager till re-integration project
        if self.checkMail(REQUEST):
            return FALSE

        mailString = self.getMailFromRequest(REQUEST)
        msg = EmailMessage(mailString, list_title=self.getProperty('title', ''), 
                                       group_id=self.getId(), 
                                       site_id=self.getProperty('siteId', ''), 
                                       sender_id_cb=self.get_mailUserId)

        self.manage_addMail(msg)
        return TRUE


    
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
        
