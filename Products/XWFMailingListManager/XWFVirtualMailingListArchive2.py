# Copyright IOPEN Technologies Ltd., 2003
# richard@iopen.net
#
# For details of the license, please see LICENSE.
#
# You MUST follow the rules in README_STYLE before checking in code
# to the head. Code which does not follow the rules will be rejected.  
#
from App.class_init import InitializeClass

from Products.PageTemplates.PageTemplateFile import PageTemplateFile

from AccessControl import ClassSecurityInfo
from OFS.Folder import Folder

class XWFVirtualMailingListArchive2(Folder):
    """ A folder for virtualizing mailing list content.
        
    """
    security = ClassSecurityInfo()
    
    meta_type = 'XWF Virtual Mailing List Archive II'
    version = 0.1
    
    manage_options = Folder.manage_options + \
                     ({'label': 'Configure',
                       'action': 'manage_configure'},)
        
    default_nsprefix = 'list'
    
    _properties=(
        {'id':'title', 'type':'string', 'mode':'w'},
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

    def get_xwfMailingListManager(self):
        """ Get the reference to the xwfMailingListManager we are associated with.
        
        """
        if not self.xwf_mailing_list_manager_path:
            raise XWFVirtualListError, 'Unable to retrieve list manager, no path set'
            
        return self.restrictedTraverse(self.xwf_mailing_list_manager_path)

    def get_listProperty(self, list_id, property, default=None):
        """ Get the given property of a given list or return the default.
        
        """
        if list_id not in self.xwf_mailing_list_ids:
            raise (XWFVirtualListError,
                  'Unable to retrieve list_id %s, list not registered' % list_id)
        list_manager = self.get_xwfMailingListManager()
        
        return list_manager.get_listProperty(list_id, property, default)

    #   
    # Views and Workflow
    #
    def index_html(self, REQUEST, RESPONSE):
        """ """
        url = '%s/topics.html' % REQUEST.BASE4
        return RESPONSE.redirect(url)


InitializeClass(XWFVirtualMailingListArchive2)
#
# Zope Management Methods
#
manage_addXWFVirtualMailingListArchive2Form = PageTemplateFile(
    'management/manage_addXWFVirtualMailingListArchive2Form.zpt',
    globals(), __name__='manage_addXWFVirtualMailingListArchive2Form')

def manage_addXWFVirtualMailingListArchive2(self, id, title=None,
                               REQUEST=None, RESPONSE=None, submit=None):
    """ Add a new instance of XWFVirtualMailingListArchive2
        
    """
    obj = XWFVirtualMailingListArchive2(id, title)
    self._setObject(id, obj)
    
    obj = getattr(self, id)
    
    if RESPONSE and submit:
        if submit.strip().lower() == 'add':
            RESPONSE.redirect('%s/manage_main' % self.DestinationURL())
        else:
            RESPONSE.redirect('%s/manage_main' % id)

def initialize(context):
    context.registerClass(
        XWFVirtualMailingListArchive2,
        permission='Add XWF Virtual Mailing List Archive II',
        constructors=(manage_addXWFVirtualMailingListArchive2Form,
                      manage_addXWFVirtualMailingListArchive2)
    )
#        #icon='icons/ic-virtualfolder.png'
#        )
