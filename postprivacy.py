# coding=utf-8
from AccessControl.PermissionRole import rolesForPermissionOn
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
        roles = rolesForPermissionOn('View', self.context)
        anonView = 'Anonymous' in roles
          
        self.visibility = anonView and u'public' or u'private'
        
        if anonView:
            self.webVisibility = u'<strong>Anyone</strong> &#8213; '\
              u'including search engines and people who are not '\
              u' logged in &#8213;'
            self.emailVisibility = u'<strong>group</strong> members' 
        elif 'DivisionMember' in roles:
            self.webVisibility = u'<strong>Group</strong> members '\
              u'and <strong>site</strong> members'
            self.emailVisibility = u'<strong>group</strong> members' 
        else:
            self.webVisibility = u'<strong>Group</strong> members'
            self.emailVisibility = u'' 
        
        assert type(self.visibility) == unicode
        assert type(self.webVisibility) == unicode
        assert type(self.emailVisibility) == unicode
        self.__updated = True
            
    def render(self):
        if not self.__updated:
            raise UpdateNotCalled
        pageTemplate = PageTemplateFile(self.pageTemplateFileName)
        retval = pageTemplate(
                visibility =      self.visibility,
                webVisibility =   self.webVisibility,
                emailVisibility = self.emailVisibility)
        assert type(retval) == unicode
        return retval
        
provideAdapter(GSPostPrivacyContentProvider, provides=IContentProvider,
  name="groupserver.PostPrivacy")

