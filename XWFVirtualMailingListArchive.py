# Copyright IOPEN Technologies Ltd., 2003
# richard@iopen.net
#
# For details of the license, please see LICENSE.
#
# You MUST follow the rules in README_STYLE before checking in code
# to the head. Code which does not follow the rules will be rejected.  
#
import os, Globals

from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Products.XWFIdFactory.XWFIdFactoryMixin import XWFIdFactoryMixin

from AccessControl import getSecurityManager, ClassSecurityInfo
from types import *
from Globals import InitializeClass, PersistentMapping
from OFS.Folder import Folder
from Products.XWFCore.XWFUtils import createBatch

class XWFVirtualListError(Exception):
    pass


class XWFVirtualMailingListArchive(Folder, XWFIdFactoryMixin):
    """ A folder for virtualizing mailing list content.
        
    """
    security = ClassSecurityInfo()
    
    meta_type = 'XWF Virtual Mailing List Archive'
    version = 0.1
    
    manage_options = Folder.manage_options + \
                     ({'label': 'Configure',
                       'action': 'manage_configure'},)
        
    #id_factory = 'IdFactory'
    #id_namespace = 'http://xwft.org/namespaces/xwft/virtualfolder'
    
    default_nsprefix = 'list'
    
    _properties=(
        {'id':'title', 'type':'string', 'mode':'w'},
        {'id':'id_factory', 'type':'string', 'mode':'w'},
        {'id':'xwf_mailing_list_manager_path', 'type':'string', 'mode':'w'},
        {'id':'xwf_mailing_list_ids', 'type':'lines', 'mode':'w'},
                )
    
    def __init__(self, id, title=None):
        """ Initialise a new instance of XWFVirtualMailingListManager.
            
        """
        self.__name__ = id
        self.id = id
        self.title = title or id
        self.xwf_mailing_list_manager_path = ''
        self.xwf_mailing_list_ids = []

    def manage_afterAdd(self, item, container):
        """ For configuring the object post-instantiation.
            
        """
        # note that the UCID is a string
        #self.ucid = str(self.get_nextId())
        
    def get_xwfMailingListManager(self):
        """ Get the reference to the xwfMailingListManager we are associated with.
        
        """
        if not self.xwf_mailing_list_manager_path:
            raise XWFVirtualListError, 'Unable to retrieve list manager, no path set'
            
        return self.restrictedTraverse(self.xwf_mailing_list_manager_path)

    def get_xml(self, set_top=0):
        """ Generate an XML representation of this folder.
        
        """
        xml_stream = ['<%s:folder rdf:id="%s" %s:top="%s"' % (
                                                   self.default_nsprefix,
                                                   self.getId(),
                                                   self.default_nsprefix,
                                                   set_top)]
        xa = xml_stream.append
        
        xa('xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">')
        
        xa('</%s:folder>' % self.default_nsprefix)
    
        return '\n'.join(xml_stream)
    
    security.declareProtected('View', 'find_email')
    def find_email(self, query={}):
        """ Perform a search against the email associated with this 
            VirtualMailingListArchive.
            
            Takes:
              query: a catalog query dictionary
              
           The results returned act as a lazy sequence, from the ZCatalog.Lazy
           module, so it is possible to slice the returned sequence in order to
           limit the result set.
           
           It is possible to sort the result set using the sort_on, sort_order
           and sort_limit index names in the query dictionary. See the ZCatalog
           documentation for further information on the query dictionary.
           
        """
        list_manager = self.get_xwfMailingListManager()

        mlids = filter(None, self.xwf_mailing_list_ids)
        if mlids:
            query['listId'] = mlids
        
        if list_manager.meta_type == 'XWF Virtual Mailing List Archive':
            raise (XWFVirtualListError, 
            'Caught potential recursion, mailing list archive is a virtual list archive')
            
        return list_manager.find_email(query)

    def get_email(self, id):
        """ Get an email given its unique identifier.
        
        """
        object = self.find_email({'id': id})[0].getObject()
        
        return object

    #   
    # Views and Workflow
    #
    def index_html(self):
        """ Return the default view.
        
        """
        presentation = self.Presentation.Tofu.MailingListManager.xml
        
        return presentation.default()
        
    def view_email(self, id, show_thread=0):
        """ Return the email view.
        
        """
        from DocumentTemplate import sequence
        presentation = self.Presentation.Tofu.MailingListManager.xml
        
        email_object = self.get_email(id)
        
        if show_thread:
            result_set = map(lambda x: x.getObject(),
                             self.find_email(query={'mailSubject': '"%s"' % email_object.mailSubject}))
            
            # we probably did really well with the exact phrase search, but we need to be bang on
            result_set = filter(lambda x: x and x.mailSubject == email_object.mailSubject, result_set)
            result_set = sequence.sort(result_set, (('mailDate', 'cmp', 'asc'),
                                                    ('mailSubject', 'nocase', 'asc')))
        else:
            result_set = (email_object,)
        
        return presentation.email(result_set=result_set)
        
    def view_threads(self, REQUEST, b_start=1, b_size=20, s_on='mailDate', s_order='desc'):
        """ Return the threaded view.
        
        """
        from DocumentTemplate import sequence
        presentation = self.Presentation.Tofu.MailingListManager.xml
        
        def thread_sorter(a, b):
            if s_on in ('mailDate', 'mailSubject'):
                a = getattr(a[1][0], s_on); b = getattr(b[1][0], s_on)
            elif s_on in ('mailCount', ):
                a = a[0]; b = b[0]
            else:
                return 0
                
            if not a > b:
                return s_order == 'asc' and -1 or 1
            elif not a < b:
                return s_order == 'asc' and 1 or -1
            else:
                return 0 
        
        result_set = self.find_email(REQUEST)
        result_set = sequence.sort(result_set, (('mailSubject', 'nocase'), ('mailDate', 'cmp', 'desc')))
        threads = []
        curr_thread = None
        curr_thread_results = []
        for result in result_set:
            if result.mailSubject == curr_thread: # existing thread
                curr_thread_results.append(result)
            else: # new thread
                if curr_thread_results:
                    fr = curr_thread_results[0]
                    threads.append((len(curr_thread_results),
                                    curr_thread_results))
                curr_thread_results = [result]
                curr_thread = result.mailSubject

        threads.sort(thread_sorter)

        (b_start, b_end, b_size, result_size, result_set) = createBatch(threads, b_start, b_size)
        
        return presentation.threaded(result_set=result_set,
                                     b_start=b_start+1, b_size=b_size, b_end=b_end,
                                     result_size=result_size)


    def view_search(self):
        """ Return the search view.
        
        """
        presentation = self.Presentation.Default.MailingListManager.xml
        
        return presentation.search()

    security.declarePublic('view_results')
    def view_results(self, REQUEST, b_start=1, b_size=20, s_on='mailDate', s_order='desc'):
        """ Return the results view.
        
            Optionally specify the start and end point of the result set,
            term to sort on, and the sort order.
        
        """ 
        from DocumentTemplate import sequence
        presentation = self.Presentation.Tofu.MailingListManager.xml
        
        result_set = self.find_email(REQUEST)
        
        if s_on == 'mailDate':
            result_set = sequence.sort(result_set, (('mailDate', 'cmp', s_order),
                                                    ('mailSubject', 'nocase', s_order)))
        else:
            result_set = sequence.sort(result_set, ((s_on, 'nocase', s_order),
                                                    ('mailDate', 'cmp', s_order)))
        
        (b_start, b_end, b_size, result_size, result_set) = createBatch(result_set, b_start, b_size)

        return presentation.results(result_set=result_set,
                                    b_start=b_start+1, b_size=b_size, b_end=b_end,
                                    result_size=result_size)        
        
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


Globals.InitializeClass(XWFVirtualMailingListArchive)
#
# Zope Management Methods
#
manage_addXWFVirtualMailingListArchiveForm = PageTemplateFile(
    'management/manage_addXWFVirtualMailingListArchiveForm.zpt',
    globals(), __name__='manage_addXWFVirtualMailingListArchiveForm')

def manage_addXWFVirtualMailingListArchive(self, id, title=None,
                               REQUEST=None, RESPONSE=None, submit=None):
    """ Add a new instance of XWFVirtualMailingListArchive
        
    """
    obj = XWFVirtualMailingListArchive(id, title)
    self._setObject(id, obj)
    
    obj = getattr(self, id)
    
    if RESPONSE and submit:
        if submit.strip().lower() == 'add':
            RESPONSE.redirect('%s/manage_main' % self.DestinationURL())
        else:
            RESPONSE.redirect('%s/manage_main' % id)

def initialize(context):
    import os
    context.registerClass(
        XWFVirtualMailingListArchive,
        permission='Add XWF Virtual Mailing List Archive',
        constructors=(manage_addXWFVirtualMailingListArchiveForm,
                      manage_addXWFVirtualMailingListArchive)
    )
#        #icon='icons/ic-virtualfolder.png'
#        )