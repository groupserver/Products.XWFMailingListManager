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
    
    def __init__(self, id, title, mailto): #, moderator, moderated, archived, mtahosts):
        """ setup a MailBoxer with reasonable defaults """
        
        self.id = id
        self.title = title
        self.mailto = mailto
        
    def _setPropValue(self, id, value):
        self._wrapperCheck(value)
        if hasattr(self.aq_base, id):        
            # if we have the attribute locally, just set it
            setattr(self, id, value)
        elif hasattr(self.aq_parent, id):
            # if the parent has the attribute, and we've got a different value
            # set it locally
            if value != getattr(self.aq_parent, id):            
                setattr(self, id, value)
        else:
            # if all else fails, set it locally
            setattr(self, id, value)
            
    def listId(self):
        """ Mostly intended to be tracked by the catalog, to allow us to
        track which email belongs to which list.
        
        """
        return self.getId()
        
    security.declareProtected('Add Folders','manage_addMail')
    def manage_addMail(self, Mail):
        """ store mail & attachments in a folder and return it """

        (mailHeader, mailBody) = self.splitMail(Mail)

        # always take our own date... don't believe the clients!
        if self.keepdate:
            timetuple = rfc822.parsedate_tz(mailHeader.get('date'))
            time = DateTime(rfc822.mktime_tz(timetuple))
        else:
            time = DateTime()
        
        LOG('MailHeader', WARNING, str(mailHeader.items()))
         
        # unlike the original archive, we don't store the email in a yyyy/mm format,
        # but we do record this information for the presentation layer to use,
        # should it wish to do so
        year  = str(time.year())  # yyyy
        month = str(time.mm())    # mm                
        
        archive = getattr(self,'archive')
        
        # let's create the mailObject
        mailFolder = archive
        
        Subject = self.mime_decode_header(mailHeader.get('subject',
                                                         'No Subject')).strip()
                                                         
        From = self.mime_decode_header(mailHeader.get('from','No From'))
        Title = "%s / %s" % (Subject, From)

        # maybe it's a reply ?
        #if ':' in Subject:
        #    for currentFolder in monthFolder.objectValues(['Folder']):
        #        if difflib.get_close_matches(Subject,
        #                                     [currentFolder.mailSubject]):
        #            mailFolder=currentFolder

        # search a free id for the mailobject
        id = time.millis()
        while hasattr(mailFolder,str(id)):  
             id = id + 1
             
        id = str(id)

        mailFolder.manage_addFolder(id, title=Title)
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
        mailObject.manage_addProperty('mailFrom', From, 'string')
        
        # correct the subject so we don't have the list id in it
        id_string = '[%s]' % self.getProperty('title')
        Subject = Subject.replace(id_string, '').strip()
        
        if Subject.lower().find('re:', 0, 3) == 0 and len(Subject) > 3:
            Subject = Subject[3:].strip()
            mailObject.manage_addProperty('mailSubject', Subject, 'string')
        elif len(Subject) == 0:
            Subject = 'No Subject'
        
        mailObject.manage_addProperty('mailSubject', Subject, 'string')
        mailObject.manage_addProperty('mailDate', time, 'date')
        mailObject.manage_addProperty('mailBody', mailBody, 'text')
        
        types = {'date': ('date', convert_date),
                 'from': ('lines', convert_addrs),
                 'to': ('lines', convert_addrs),
                 'received': ('lines', null_convert),}
        for key in mailHeader.keys():
            if key in types:
                mailObject.manage_addProperty(key,
                                              types[key][1](self.mime_decode_header(mailHeader.get(key,''))),
                                              types[key][0])
            else:
                mailObject.manage_addProperty(key,
                                              self.mime_decode_header(mailHeader.get(key,'')),
                                              'text')
        
        # insert header if a regular expression is set and matches
        if self.headers:
            msg = mimetools.Message(StringIO.StringIO(Mail))
            headers = []
            for (key,value) in msg.items():
                if re.match(self.headers, key, re.IGNORECASE):
                    headers.append('%s: %s' % (key, value.strip()))
            
            mailObject.manage_addProperty('mailHeader', headers, 'lines')

        # Index the new created mailFolder in the catalog
        if hasattr(self, self.catalog):
            getattr(self, self.catalog).catalog_object(mailObject)
    
        return mailObject
        
    def reindex_mailObjects(self):
        """ Reindex the mailObjects that we contain.
             
        """
        for object in self.archive.objectValues('Folder'):
            if hasattr(object, 'mailFrom'):
                pp = '/'.join(object.getPhysicalPath())
                self.Catalog.uncatalog_object(pp)
                self.Catalog.catalog_object(object, pp)
         
        return 1
        
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
        
        return 1
        
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
