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

class Record:
    pass

class XWFMailingListManager(Folder, XWFMetadataProvider):
    """ A searchable, self indexing mailing list manager.

    """
    security = ClassSecurityInfo()
    
    meta_type = 'XWF Mailing List Manager'
    version = 0.3
    
    manage_options = Folder.manage_options + \
                     ({'label': 'Configure',
                       'action': 'manage_configure'},)
    
    manage_configure = PageTemplateFile('management/main.zpt',
                                        globals(),
                                        __name__='manage_main')
    
    def __init__(self, id, title=''):
        """ Initialise a new instance of XWFMailingListManager.
        
        """
        self.__name__ = id
        self.id = id
        self.title = title
        self._setupMetadata()
            
    def _setupMetadata(self):
        """ Setup the metadata to be provided by default in our library.
        
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
              ('title','','FieldIndex'),
              ('mailDate','','DateIndex'),
              ('mailFrom','','ZCTextIndex'),
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
                
        # make sure we store the ID of the object in the metadata of the catalog
        item.Catalog.addColumn('id')

        item.manage_addProduct['MailHost'].manage_addMailHost('MailHost', 
                                                              smtp_host='127.0.0.1')


    security.declareProtected('Upgrade objects', 'upgrade')
    security.setPermissionDefault('Upgrade objects', ('Manager', 'Owner'))
    def upgrade(self):
        """ Upgrade to the latest version.
            
        """
        currversion = getattr(self, '_version', 0)
        if currversion == self.version:
            return 'already running latest version (%s)' % currversion

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
