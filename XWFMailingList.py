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
        if key in ('maillist', 'mailinlist'):
            if key == 'maillist':
                address_getter = 'get_preferredEmailAddresses'
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
                    try:
                        addresses = getattr(user, address_getter)()
                    except:
                        continue
                    for email in addresses:
                        email = email.strip()
                        if email and email not in maillist:
                            maillist.append(email)
            except:
                pass
            
            # last ditch effort
            if not maillist:
                maillist = self.getProperty('maillist')  
            
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
    def manage_addMail(self, Mail):
        """ Store mail & attachments in a folder and return it.
        
        """
        import re
        archive = self.restrictedTraverse(self.getValueFor('storage'),
                                          default=None)

        # no archive available? then return immediately
        if archive is None:
            return None
            
        (header, body) = self.splitMail(Mail)
        
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
        (TextBody, ContentType, HtmlBody) =  self._unpackMultifile(mailObject, 
                                                     multifile.MultiFile(
                                                      StringIO.StringIO(Mail)))

        # ContentType is only set for the TextBody
        if ContentType:
            mailBody = TextBody
        else:
            mailBody = self.HtmlToText(HtmlBody)
             
        # and now add some properties to our new mailobject 
        mailObject.manage_addProperty('mailFrom', sender, 'string')
        mailObject.manage_addProperty('mailSubject', subject, 'string')
        mailObject.manage_addProperty('mailDate', time, 'date')
        mailObject.manage_addProperty('mailBody', mailBody, 'text')
        mailObject.manage_addProperty('compressedSubject', compressedsubject, 'string')
        
        types = {'date': ('date', convert_date),
                 'from': ('lines', convert_addrs),
                 'to': ('lines', convert_addrs),
                 'received': ('lines', null_convert),}
        
        for key in header.keys():
            if key in types:
                mailObject.manage_addProperty(key,
                                              types[key][1](self.mime_decode_header(header.get(key,''))),
                                              types[key][0])
            else:
                mailObject.manage_addProperty(key,
                                              self.mime_decode_header(header.get(key,'')),
                                              'text')
        
        sender_id = self.get_mailUserId(mailObject.getProperty('from', []))
        mailObject.manage_addProperty('mailUserId', sender_id, 'string')
        
        # Index the new created mailFolder in the catalog
        Catalog = self.unrestrictedTraverse(self.getValueFor('catalog'),
                                            default=None)
                                            
        if Catalog is not None:
            Catalog.catalog_object(mailObject)
        return mailObject
    
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
        