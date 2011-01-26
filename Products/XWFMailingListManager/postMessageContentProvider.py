from zope.pagetemplate.pagetemplatefile import PageTemplateFile
from zope.interface import implements, Interface
from zope.component import createObject, adapts, provideAdapter
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from zope.contentprovider.interfaces import IContentProvider, UpdateNotCalled

from Products.XWFCore.cache import SimpleCache
from Products.GSGroupMember.usercanpost import GSGroupMemberPostingInfo
from gs.profile.email.base.emailuser import EmailUser

from interfaces import IGSPostMessageContentProvider

class GSPostMessageContentProvider(object):
    """GroupServer Post Message Content Provider
    """
    implements(IGSPostMessageContentProvider)
    adapts(Interface, IDefaultBrowserLayer, Interface)
    
    # We want a really simple cache for templates, because there aren't
    #  many of them
    cookedTemplates = SimpleCache("GSPostMessageContentProvider.cookedTemplates")
    
    def __init__(self, context, request, view):
        self.__parent = view
        self.__updated = False
        self.context = context
        self.request = request
        self.view = view
    
    def update(self):
        self.siteInfo = createObject('groupserver.SiteInfo', self.context)
        self.groupInfo = createObject('groupserver.GroupInfo', self.context)
        u = self.request.AUTHENTICATED_USER
        self.userInfo = createObject('groupserver.UserFromId',
                                     self.context, u.getId())
        self.userCanPost = self.postingInfo.canPost
    
        if self.userCanPost:
            eu = EmailUser(self.context, self.userInfo)
            self.fromEmailAddresses = eu.get_addresses()
            self.preferredEmailAddress = \
              eu.get_delivery_addresses()[0]
        else:
            self.fromEmailAddresses = []
            self.preferredEmailAddress = ''
                  
        self.__updated = True
        assert self.siteInfo
        assert self.groupInfo
        assert self.userInfo
        assert type(self.userCanPost) == bool
        assert type(self.fromEmailAddresses) == list
        assert type(self.preferredEmailAddress) == str
        
    def render(self):
        if not self.__updated:
            raise UpdateNotCalled
        retval = u''
        
        pageTemplate = self.cookedTemplates.get(self.pageTemplateFileName)
        if not pageTemplate:
            pageTemplate = PageTemplateFile(self.pageTemplateFileName)    
            self.cookedTemplates.add(self.pageTemplateFileName, pageTemplate)
        if self.userCanPost:
            retval = pageTemplate(startNew=self.startNew,
                                  topic=self.topic,
                                  groupName=self.groupInfo.name,
                                  groupId=self.groupInfo.id,
                                  siteId=self.siteInfo.id,
                                  replyToId=self.replyToId,
                                  fromEmailAddresses=self.fromEmailAddresses,
                                  preferredEmailAddress=self.preferredEmailAddress)
        else:
            retval = self.postingInfo.status
        return retval
        
    #########################################
    # Non standard methods below this point #
    #########################################
    
    @property
    def postingInfo(self):
        group = self.groupInfo.groupObj
        postingInfo = GSGroupMemberPostingInfo(group, self.userInfo)
        return postingInfo

provideAdapter(GSPostMessageContentProvider, provides=IContentProvider,
  name="groupserver.PostMessage")

