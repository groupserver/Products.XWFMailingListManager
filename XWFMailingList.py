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
from AccessControl import getSecurityManager, ClassSecurityInfo

from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Products.CustomProperties.CustomProperties import CustomProperties
from Globals import InitializeClass, PersistentMapping
from OFS.Folder import Folder, manage_addFolder

from Products.MailBoxer.MailBoxer import *
from Acquisition import ImplicitAcquisitionWrapper, aq_base, aq_parent

from cgi import escape

from zLOG import LOG, WARNING

def convert_date(date):
    import time
    from email.Utils import parsedate
    
    return time.asctime(parsedate(date))

def convert_addrs(field):
    import time
    from rfc822 import AddressList
    
    return map(lambda x: x[1], AddressList(field).addresslist)

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
        
    security.declareProtected('Manage properties','getMemberUserObjects')
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
       
    security.declareProtected('Access contents information', 'getValueFor')
    def getValueFor(self, key):
        # getting the maillist is a special case, working in with the
        # XWFT group framework
        pass_group_id = False
        if key in ('digestmaillist', 'maillist', 'mailinlist'):
            if key in ('digestmaillist', 'maillist'):
                address_getter = 'get_deliveryEmailAddressesByKey'
                #address_getter = 'get_preferredEmailAddresses'
                pass_group_id = True
                maillist_script = getattr(self, 'maillist_members', None)
            else:
                address_getter = 'get_emailAddresses'
                maillist_script = getattr(self, 'mailinlist_members', None)
                
            # look for a maillist script
            if maillist_script:
                return maillist_script()
                
            maillist = []
            try:
                users = self.get_memberUserObjects()
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
            except:
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
            subject = re.sub('\[%s\]' % self.getValueFor('title'), '', subject).strip()
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
        
    security.declareProtected('Add Folders','manage_addMail')
    def manage_addMail(self, mailString):
        """ Store mail & attachments in a folder and return it.
        
        """
        import re
        archive = self.restrictedTraverse(self.getValueFor('storage'),
                                          default=None)

        # no archive available? then return immediately
        if archive is None:
            return None
            
        (header, body) = self.splitMail(mailString)
        
        # if 'keepdate' is set, get date from mail,
        if self.getValueFor('keepdate'):
            timetuple = rfc822.parsedate_tz(header.get('date'))
            time = DateTime(rfc822.mktime_tz(timetuple))
        # ... take our own date, clients are always lying!
        else:
            time = DateTime()
        
        # let's create the mailObject
        mailFolder = archive
        
        subject = self.mime_decode_header(header.get('subject', 'No Subject'))
        
        # correct the subject
        subject = self.tidy_subject(subject)
        
        if subject.lower().find('re:', 0, 3) == 0 and len(subject) > 3:
            subject = subject[3:].strip()
        elif len(subject) == 0:
            subject = 'No Subject'
        
        compressedsubject = re.sub('\s+', '', subject)
        
        sender = self.mime_decode_header(header.get('from','No From'))
        title = "%s / %s" % (subject, sender)
        
        # we use our IdFactory to get the next ID, rather than trying something
        # ad-hoc
        id = str(self.get_nextId())
        
        self.addMailBoxerMail(mailFolder, id, title)
        mailObject = getattr(mailFolder, id)
        
        # unpack attachments
        (TextBody, ContentType, HtmlBody, Attachments) = self.unpackMail(
                                                              mailString)
        # ContentType is only set for the TextBody
        if ContentType:
            mailBody = TextBody
        else:
            mailBody = self.HtmlToText(HtmlBody)
             
        # and now add some properties to our new mailobject
        self.setMailBoxerMailProperty(mailObject, 'mailFrom', sender, 'string')
        self.setMailBoxerMailProperty(mailObject, 'mailSubject', subject, 'string')
        self.setMailBoxerMailProperty(mailObject, 'mailDate', time, 'date')
        self.setMailBoxerMailProperty(mailObject, 'mailBody', mailBody, 'text')
        self.setMailBoxerMailProperty(mailObject, 'compressedSubject', compressedsubject, 'string')       
        
        types = {'date': ('date', convert_date),
                 'from': ('lines', convert_addrs),
                 'to': ('lines', convert_addrs),
                 'received': ('lines', null_convert),}
        
        for key in header.keys():
            if key in types:
                self.setMailBoxerMailProperty(mailObject, key,
                                              types[key][1](self.mime_decode_header(header.get(key,''))),
                                              types[key][0])
            else:
                self.setMailBoxerMailProperty(mailObject, key,
                                              self.mime_decode_header(header.get(key,'')),
                                              'text')
        
        sender_id = self.get_mailUserId(mailObject.getProperty('from', []))
        self.setMailBoxerMailProperty(mailObject, 'mailUserId', sender_id, 'string')
        
        self.catalogMailBoxerMail(mailObject)

        return mailObject
    
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
                LOG('MailBoxer', PROBLEM,  message)
                return message

        # Check for x-mailer-loop
        mailString = self.getMailFromRequest(REQUEST)
        (header, body) = self.splitMail(mailString)

        if header.get('x-mailer') == self.getValueFor('xmailer'):
            message = 'Mail already processed'
            LOG('MailBoxer', PROBLEM, message)
            return(message)

        # Check for empty return-path => automatic mail
        if header.get('return-path', '') == '<>':
            self.bounceMail(REQUEST)
            message = 'Automated response detected from %s' % (header.get('from',
                                                                          '<>'))
            LOG('MailBoxer', PROBLEM, message)
            return (message)

        # Check for hosed denial-of-service-vacation mailers
        # or other infinite mail-loops...
        sender = self.mime_decode_header(header.get('from', 'No Sender'))
        (name, email) = rfc822.parseaddr(sender)
        email = email.lower()

        disabled = list(self.getValueFor('disabled'))

        if email in disabled:
            message = '%s is disabled.' % sender
            LOG('MailBoxer', PROBLEM, message)
            return message

        senderlimit = self.getValueFor('senderlimit')
        senderinterval = self.getValueFor('senderinterval')

        if senderlimit and senderinterval:
            sendercache = self.sendercache

            ntime = int(DateTime())

            if sendercache.has_key(email):
                sendercache[email].insert(0, ntime)
            else:
                sendercache[email] = [ntime]
            
            etime = ntime-senderinterval
            count = 0
            for atime in sendercache[email]:
                if atime > etime:
                    count += 1
                else:
                    break

            # prune our cache back to the time intervall
            sendercache[email] = sendercache[email][:count]
            self.sendercache = sendercache

            if count > senderlimit:
                #if email not in disabled:
                #    self.setValueFor('disabled', disabled + [email])
                user = self.acl_users.get_userByEmail(email)
                user.send_notification('sender_limit_exceeded', self.listId())
                message = ('Sender %s has sent %s mails in %s seconds' %
                                              (sender, count, senderinterval))
                LOG('MailBoxer', PROBLEM, message)
                return message

        # Check for spam
        for regexp in self.getValueFor('spamlist'):
            if regexp and re.search(regexp, mailString):
                message = 'Spam detected: %s\n\n%s\n' % (regexp, mailString)
                LOG('MailBoxer', PROBLEM, message)
                return message
        
        # GroupServer specific checks
        blocked_members = self.getProperty('blocked_members')
        if blocked_members:
            user = self.acl_users.get_userByEmail(email)
            if user and user.getId() in blocked_members:
                message = 'Blocked user: %s from posting' % user.getId()
                LOG('MailBoxer', PROBLEM, message)
                user.send_notification('post_blocked', self.listId())
                return message
                

    def requestMail(self, REQUEST):
        # Handles un-/subscribe-requests.

        mailString = self.getMailFromRequest(REQUEST)
        (header, body) = self.splitMail(mailString)

        # get subject
        subject = self.mime_decode_header(header.get('subject',''))

        # get email-address
        sender = self.mime_decode_header(header.get('from',''))
        (name, email) = self.parseaddr(sender)
        
        memberlist = self.lowerList(self.getValueFor('mailinlist'))
        
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
                        division_id = group_object.get_division_id()
                        user.set_verificationGroups(['%s_member' % self.getId(),
                                                     '%s_member' % division_id])
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
            	
    security.declareProtected('Manage properties','manage_addMember')
    def manage_addMember(self, email):
        """ Add member to group. """

        user = self.acl_users.get_userByEmail(email)
        if user:
            user.add_groupWithNotification('%s_member' % self.getId())
        
        return 1

    security.declareProtected('Manage properties','manage_delMember')
    def manage_delMember(self, email):
        """ Remove member from group. """
        
        user = self.acl_users.get_userByEmail(email)
        if user:
            user.del_groupWithNotification('%s_member' % self.getId())
        
        return 1

    security.declareProtected('Manage properties','getMemberUserObjects')
    def get_mailUserId(self, from_addrs=[]):
        member_users = self.get_memberUserObjects()
        for addr in from_addrs:
            for member_user in member_users:
                addrs = member_user.getProperty('emailAddresses', [])
                for member_addr in addrs:
                    if member_addr.lower() == addr.lower():
                        return member_user.getId()
                        
        return ''
    
    security.declareProtected('Manage properties','reindex_mailObjects')
    def reindex_mailObjects(self):
        """ Reindex the mailObjects that we contain.
             
        """
        for object in self.archive.objectValues('Folder'):
            if hasattr(object, 'mailFrom'):
                pp = '/'.join(object.getPhysicalPath())
                self.Catalog.uncatalog_object(pp)
                self.Catalog.catalog_object(object, pp)
         
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
            reply_text = reply(REQUEST, list_object=context, mail=mail, body=body)
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
        
        email_address = headers.get('from','')
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
    def mail_header(self, context, REQUEST, getValueFor=None, title='', mail=None, body=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        header = getattr(self, 'xwf_email_header', None)
        if header:
            return header(REQUEST, list_object=context,
                                   getValueFor=getValueFor,
                                   title=title, mail=mail, body=body)
        else:
            return ""
    
    security.declarePrivate('mail_footer')
    def mail_footer(self, context, REQUEST, getValueFor=None, title='', mail=None, body=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        footer = getattr(self, 'xwf_email_footer', None)
        if footer:
            return footer(REQUEST, list_object=context,
                                   getValueFor=getValueFor,
                                   title=title, mail=mail, body=body)
        else:
            return ""
    
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
        return self.manage_main(self,REQUEST)

InitializeClass(XWFMailingList)

def initialize(context):
    context.registerClass(
        XWFMailingList,
        permission="Add XWF MailingList",
        constructors=(manage_addXWFMailingListForm,
                      manage_addXWFMailingList),
        )
        
