from zope.pagetemplate.pagetemplatefile import PageTemplateFile
from zope.interface import implements, Interface
from zope.component import createObject, adapts, provideAdapter
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from zope.contentprovider.interfaces import IContentProvider, UpdateNotCalled

from interfaces import IGSPostPrivacyContentProvider

class GSPostPrivacyContentProvider(object):
    """GroupServer Post Message Content Provider
    """
    implements( IGSPostPrivacyContentProvider )
    adapts(Interface, IDefaultBrowserLayer, Interface)
    
    def __init__(self, context, request, view):
        self.__parent = view
        self.__updated = False
        self.context = context
        self.request = request
        self.view = view

    def update(self):
        siteInfo = createObject('groupserver.SiteInfo', 
          self.context)
        groupInfo = createObject('groupserver.GroupInfo', 
          self.context)
        userInfo = createObject('groupserver.LoggedInUser', 
          self.context)
          
        self.visiblitiy = u''
        self.webVisibility = u''
        self.emailVisibility = u''

        assert type(self.visiblitiy) == unicode
        assert type(self.webVisibility) == unicode
        assert type(self.emailVisibility) == unicode
        self.__updated = True
            
    def render(self):
        if not self.__updated:
            raise UpdateNotCalled
        pageTemplate = PageTemplateFile(self.pageTemplateFileName)
        retval = pageTemplate(
                visiblitiy =      self.visiblitiy,
                webVisibility =   self.webVisibility,
                emailVisibility = self.emailVisibility)
        assert type(retval) == unicode
        return retval
        
provideAdapter(GSPostPrivacyContentProvider, provides=IContentProvider,
  name="groupserver.PostPrivacy")

