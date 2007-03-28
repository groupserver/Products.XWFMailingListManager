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
from Products.XWFIdFactory.XWFIdFactoryMixin import XWFIdFactoryMixin
from Products.XWFCore.XWFCatalog import XWFCatalog
from Products.MailBoxer.MailBoxer import MailBoxer, MailBoxerTools

import os, time

MAILDROP_SPOOL = '/tmp/mailboxer_spool2'

class Record:
    pass

class XWFMailingListManager(Folder, XWFMetadataProvider, XWFIdFactoryMixin):
    """ A searchable, self indexing mailing list manager.

    """
    security = ClassSecurityInfo()
    security.setPermissionDefault('View', ('Manager',))
    
    meta_type = 'XWF Mailing List Manager'
    version = 0.43
    
    manage_options = Folder.manage_options + \
                     ({'label': 'Configure',
                       'action': 'manage_configure'},)
    
    manage_configure = PageTemplateFile('management/main.zpt',
                                        globals(),
                                        __name__='manage_main')

    archive_options = MailBoxer.archive_options
    
    id_namespace = 'http://xwft.org/ns/mailinglistmanager'
    _properties = MailBoxer._properties
        
    def __init__(self, id, title=''):
        """ Initialise a new instance of XWFMailingListManager.
        
        """
        self.__name__ = id
        self.id = id
        self.title = title
        self._setupMetadata()
        self._setupProperties()
        self.__initialised = 0
        
    def _setupProperties(self):
        """ Setup the propertiesheet.
        
        """
        for property in MailBoxer._properties:
            propval = getattr(self, property['id'], None)
            if propval == None:
                propval = getattr(MailBoxer, property['id'])
            setattr(self, property['id'], propval)
        self._properties = MailBoxer._properties 
       
        return True
        
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
              ('compressedSubject', '', 'ZCTextIndex'),
              )
              
        for mdi in fl:
            apply(self.set_metadataIndex, mdi)
        
        return True
       
    security.declareProtected('Add Mail Boxers','manage_afterAdd') 
    def manage_afterAdd(self, item, container):
        """ For configuring the object post-instantiation.
                        
        """
        if getattr(self, '__initialised', 1):
            return 1
            
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
        
        return True

    security.declareProtected('View','get_catalog')
    def get_catalog(self):
        """ Get the catalog associated with this file library.
        
        """
        return self.Catalog

    security.declareProtected('View','find_email')
    def find_email(self, query):
        """ Return the catalog 'brains' objects representing the results of
        our query.
        
        """
        catalog = self.get_catalog()
        
        return catalog.searchResults(query)

    security.declareProtected('Manage properties', 'unrestricted_find_email')
    def unrestricted_find_email(self, query):
        """ Similar to find email, but using the unrestricted version of
        searchResults.
        
        """
        catalog = self.get_catalog()
        
        return catalog.unrestrictedSearchResults(query)

    security.declareProtected('View','get_list')
    def get_list(self, list_id):
        """ Get a contained list, given the list ID.
        
        """
        return getattr(self.aq_explicit, list_id)

    security.declareProtected('View','get_listPropertiesFromMailto')
    def get_listPropertiesFromMailto(self, mailto):
        """ Get a contained list, given the list mailto.
        
        """
        list_props = {}
        for listobj in self.objectValues('XWF Mailing List'):
            if getattr(listobj, 'mailto', '').lower() == mailto.lower():
                for prop in self._properties:
                    pid = prop['id']
                    list_props[pid] = getattr(listobj, pid, None)
                list_props['id'] = listobj.getId()
                return list_props
        return {}

    security.declareProtected('View','get_listProperty')
    def get_listProperty(self, list_id, property, default=None):
        """ Get the given property of the given list_id.
        
        """
        list = self.get_list(list_id)
                
        return list.getProperty(property, default)

    def processSpool(self):
        """ Process the deferred spool files.

        """
        objdir = os.path.join(*self.getPhysicalPath())
        spooldir = os.path.join(MAILDROP_SPOOL, objdir)
        if not os.path.exists(spooldir): # no spool to process yet
            return
        for spoolfilepath in os.listdir(spooldir):
            if os.path.exists(os.path.join(spooldir, '%s.lck' % spoolfilepath)):
                continue # we're locked
            spoolfilepath = os.path.join(spooldir, spoolfilepath)
            spoolfile = file(spoolfilepath)
            line = spoolfile.readline().strip()
            if len(line) < 5 or line[:2] != ';;' or line[-2:] != ';;':
                #logger.error('No group was specified (line was "%s")' % line)
                continue

            groupname = line[2:-2]
            group = self.get_list(groupname)
            if not group:
                #logger.error('No such group "%s"' % groupname)
                continue

            mailString = spoolfile.read()
            (header, body) = MailBoxerTools.splitMail(mailString)
            # a robustness check -- if we have an archive ID, and we aren't in
            # the archive, what are we doing here?
            archive = getattr(group, group.getValueFor('storage'))
            archive_id = header.get('x-archive-id', '').strip()
            # TODO: fix for relational database
            if archive and archive_id and not hasattr(archive.aq_explicit, archive_id):
                #logger.error('Spooled email had archive_id, but did not exist in archive')
                continue

            try:
                group.sendMail(mailString)
                spoolfile.close()
                os.remove(spoolfilepath)
                # sleep a little
                time.sleep(0.5)
            except:
                pass
                
    security.declareProtected('Upgrade objects', 'upgrade')
    security.setPermissionDefault('Upgrade objects', ('Manager', 'Owner'))
    def upgrade(self):
        """ Upgrade to the latest version.
            
        """
        currversion = getattr(self, '_version', 0)
        if currversion == self.version:
            return 'already running latest version (%s)' % currversion

        self.__initialised = 1
        self._setupMetadata()
        self._setupProperties()
        self._version = self.version

        return 'upgraded %s to version %s from version %s' % (self.getId(),
                                                              self._version,
                                                              currversion)

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
        icon='icons/ic-mailinglistmanager.png'
        )
