# Copyright IOPEN Technologies Ltd., 2003
# richard@iopen.net
#
# For details of the license, please see LICENSE.
#
# You MUST follow the rules in README_STYLE before checking in code
# to the head. Code which does not follow the rules will be rejected.  
#
from AccessControl import getSecurityManager, ClassSecurityInfo

from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Globals import InitializeClass, PersistentMapping
from OFS.Folder import Folder

from Products.XWFCore.XWFMetadataProvider import XWFMetadataProvider
from Products.XWFCore.XWFCatalog import XWFCatalog
from Products.MailBoxer.MailBoxer import MailBoxer

class Record:
    pass

class XWFMailingListManager(Folder, XWFMetadataProvider):
    """ A searchable, self indexing mailing list manager.

    """
    security = ClassSecurityInfo()
    
    meta_type = 'XWF Mailing List Manager'
    version = 0.38
    
    manage_options = Folder.manage_options + \
                     ({'label': 'Configure',
                       'action': 'manage_configure'},)
    
    manage_configure = PageTemplateFile('management/main.zpt',
                                        globals(),
                                        __name__='manage_main')

    archive_options = MailBoxer.archive_options
    
    _properties=(
        {'id':'title', 'type':'string', 'mode':'w'},
        {'id':'mailto', 'type':'string', 'mode':'w'},
        {'id':'maillist', 'type':'lines', 'mode':'w'},
        {'id':'moderator', 'type':'lines', 'mode':'w'},
        {'id':'moderated', 'type':'boolean', 'mode':'w'},
        {'id':'plainmail', 'type':'boolean', 'mode':'w'},
        {'id':'keepdate', 'type':'boolean', 'mode':'w'},
        {'id':'archived', 'type':'selection','mode':'w', 
                      'select_variable':'archive_options'},
        {'id':'subscribe', 'type':'string', 'mode':'w'},
        {'id':'unsubscribe','type':'string', 'mode':'w'},
        {'id':'mtahosts', 'type':'tokens', 'mode':'w'},
        {'id':'spamlist', 'type':'lines', 'mode':'w'},
        {'id':'atmask', 'type':'string', 'mode':'w'},
        {'id':'sniplist', 'type':'lines', 'mode':'w'},
        {'id':'catalog', 'type':'string', 'mode':'w'},
        {'id':'xmailer', 'type':'string', 'mode':'w'},
        {'id':'headers', 'type':'string', 'mode':'w'}
    )
    
    def __init__(self, id, title=''):
        """ Initialise a new instance of XWFMailingListManager.
        
        """
        self.__name__ = id
        self.id = id
        self.title = title
        self._setupMetadata()
        self._setupProperties()
        
    def _setupProperties(self):
        """ Setup the properties to be provided by default in the manager.
        
        """
        self.moderator = getattr(self, 'moderator', ['moderator@xwft.net'])
        self.moderated = getattr(self, 'moderated', 0)
        self.archived = getattr(self, 'archived', 'with attachments')
        self.mtahosts = getattr(self, 'mtahosts', ['127.0.0.1'])

        self.mailto = getattr(self, 'mailto', '')
        self.maillist = getattr(self, 'maillist', [])
        self.plainmail = getattr(self, 'plainmail', 0)
        self.keepdate = getattr(self, 'keepdate', 0)
        self.subscribe = getattr(self, 'subscribe', 'subscribe')
        self.unsubscribe = getattr(self, 'unsubscribe', 'unsubscribe')
        self.spamlist = getattr(self, 'spamlist', [])
        self.atmask = getattr(self, 'atmask', '(at)')
        self.sniplist = getattr(self, 'sniplist',  [r'(\n>[^>].*)+|(\n>>[^>].*)+', 
                         r'(?s)\n-- .*', 
                         r'(?s)\n_+\n.*'])
        self.catalog = getattr(self, 'catalog', 'Catalog')
        self.xmailer = getattr(self, 'xmailer', 'MailBoxer')
        self.headers = getattr(self, 'headers', '')
        
        # we also store the properties of our stored lists
        self.mailingListProperties = {}

    def _setupMetadata(self):
        """ Setup the metadata to be provided by default in the manager.
        
        """
        XWFMetadataProvider.__init__(self)
        # dublin core
        self.set_metadataNS('http://purl.org/dc/elements/1.1/', 'dc')
        dc = (('Contributor','dc','KeywordIndex'),
              ('Creator','dc','FieldIndex'),
              ('Description','dc','ZCTextIndex'),
              ('Format','dc','FieldIndex'),
              ('Language','dc','FieldIndex'),
              ('Subject','dc','KeywordIndex'),
              ('Type','dc','FieldIndex'),
              ('Publisher','dc','FieldIndex'),
              )
        for mdi in dc:
            apply(self.set_metadataIndex, mdi)
        
        self.set_metadataIndex('Contributor', 'dc', 'KeywordIndex')
        
        # file library
        self.set_metadataNSDefault('http://xwft.org/ns/mailinglistmanager/0.9/')
        fl = (('id','','FieldIndex'),
              ('listId', '', 'FieldIndex'),
              ('title','','FieldIndex'),
              ('mailDate','','DateIndex'),
              ('mailFrom','','FieldIndex'),
              ('mailSubject', '', 'ZCTextIndex'),
              ('mailBody', '', 'ZCTextIndex'),
              )
              
        for mdi in fl:
            apply(self.set_metadataIndex, mdi)
        
    def manage_afterAdd(self, item, container):
        """ For configuring the object post-instantiation.
                        
        """
        item._setObject('Catalog', XWFCatalog())
        
        wordsplitter = Record()
        wordsplitter.group = 'Word Splitter'
        wordsplitter.name = 'HTML aware splitter'
        
        casenormalizer = Record()
        casenormalizer.group = 'Case Normalizer'
        casenormalizer.name = 'Case Normalizer'
        
        stopwords = Record()
        stopwords.group = 'Stop Words'
        stopwords.name = 'Remove listed and single char words'
        
        item.Catalog.manage_addProduct['ZCTextIndex'].manage_addLexicon(
            'Lexicon', 'Default Lexicon', (wordsplitter, casenormalizer, stopwords))
        
        zctextindex_extras = Record()
        zctextindex_extras.index_type = 'Okapi BM25 Rank'
        zctextindex_extras.lexicon_id = 'Lexicon'
        
        for key, index in self.get_metadataIndexMap().items():
            if index == 'ZCTextIndex':
                zctextindex_extras.doc_attr = key
                item.Catalog.addIndex(key, index, zctextindex_extras)
            elif index == 'MultiplePathIndex':
                # we need to shortcut this one
                item.Catalog._catalog.addIndex(key, MultiplePathIndex(key))
            else:
                item.Catalog.addIndex(key, index)
                
        # add the metadata we need
        item.Catalog.addColumn('id')
        item.Catalog.addColumn('mailSubject')
        item.Catalog.addColumn('mailFrom')
        item.Catalog.addColumn('mailDate')
        
        item.manage_addProduct['MailHost'].manage_addMailHost('MailHost', 
                                                              smtp_host='127.0.0.1')

    def get_catalog(self):
        """ Get the catalog associated with this file library.
        
        """
        return self.Catalog

    def find_email(self, query):
        """ Return the catalog 'brains' objects representing the results of
        our query.
        
        """
        catalog = self.get_catalog()
        
        return catalog.searchResults(query)

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
        
        # now let's create the date-path (yyyy/yyyy-mm) 
        year  = str(time.year())                  # yyyy
        month = "%s-%s" % (year, str(time.mm()))  # yyyy-mm

        archive = getattr(self,'archive')
        
        # do we have a year folder already?
        if not hasattr(archive, year):
            archive.manage_addFolder(year, title=year)
        yearFolder=getattr(archive, year)

        # do we have a month folder already?
        if not hasattr(yearFolder, month):
            yearFolder.manage_addFolder(month, title=month)
        monthFolder=getattr(yearFolder, month)

        # let's create the mailObject
        mailFolder = monthFolder
        
        Subject = self.mime_decode_header(mailHeader.get('subject',
                                                         'No Subject'))
        From = self.mime_decode_header(mailHeader.get('from','No From'))
        Title = "%s / %s" % (Subject, From)

        # maybe it's a reply ?
        if ':' in Subject:
            for currentFolder in monthFolder.objectValues(['Folder']):
                if difflib.get_close_matches(Subject,
                                             [currentFolder.mailSubject]):
                    mailFolder=currentFolder

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
        mailObject.manage_addProperty('mailSubject', Subject, 'string')
        mailObject.manage_addProperty('mailDate', time, 'date')
        mailObject.manage_addProperty('mailBody', mailBody, 'text')

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


    def mail_handler(self, list_obj, REQUEST, mail='', body=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        list_obj.manage_listboxer(REQUEST)
           
    def mail_header(self, context, REQUEST, title='', mail='', body=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        if hasattr(self, 'custom_header'):
            return self.custom_header(context, REQUEST, title=title,
                                      mail=mail, body=body)
        else:
            return """"""
        
    def mail_footer(self, context, REQUEST, title='', mail='', body=''):
        """ A hook used by the MailBoxer framework, which we provide here as
        a clean default.
        
        """
        if hasattr(self, 'custom_footer'):
            return self.custom_footer(context, REQUEST, title=title,
                                      mail=mail, body=body)
        else:
            return """"""

    security.declareProtected('Upgrade objects', 'upgrade')
    security.setPermissionDefault('Upgrade objects', ('Manager', 'Owner'))
    def upgrade(self):
        """ Upgrade to the latest version.
            
        """
        currversion = getattr(self, '_version', 0)
        if currversion == self.version:
            return 'already running latest version (%s)' % currversion

        self._setupMetadata()
        self._setupProperties()
        self._version = self.version
        
        return 'upgraded %s to version %s from version %s' % (self.getId(),
                                                              self._version,
                                                              currversion)
                                                              
    # an example of using value checking -- DOCUMENT ME PROPERLY!
    #def check_foo(self, value):
    #    """ Check the value for foo """
    #    return 'foobar'

manage_addXWFMailingListManagerForm = PageTemplateFile(
    'management/manage_addXWFMailingListManagerForm.zpt',
    globals(),
    __name__='manage_addXWFMailingListManagerForm')

def manage_addXWFMailingListManager(self, id, title='Mailing List Manager',
                                     REQUEST=None):
    """ Add an XWFMailingListManager to a container.

    """
    ob = XWFMailingListManager(id, title)
    self._setObject(id, ob)
    if REQUEST is not None:
        return self.manage_main(self,REQUEST)

InitializeClass(XWFMailingListManager)

def initialize(context):
    context.registerClass(
        XWFMailingListManager,
        permission="Add XWF MailingListManager",
        constructors=(manage_addXWFMailingListManagerForm,
                      manage_addXWFMailingListManager),
        )
