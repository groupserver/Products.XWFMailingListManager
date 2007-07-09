from zope.pagetemplate.pagetemplatefile import PageTemplateFile
from zope.interface import implements, Interface
from zope.component import createObject, adapts, provideAdapter
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from zope.contentprovider.interfaces import IContentProvider, UpdateNotCalled
import Products.GSContent
from Products.XWFCore.cache import LRUCache, SimpleCache
from interfaces import IGSPostMessageContentProvider

class GSPostMessageContentProvider(object):
      """GroupServer Post Message Content Provider
      """
      implements( IGSPostMessageContentProvider )
      adapts(Interface, IDefaultBrowserLayer, Interface)

      # We want a really simple cache for templates, because there aren't
      #  many of them
      cookedTemplates = SimpleCache()
      
      def __init__(self, context, request, view):
          self.__parent = view
          self.__updated = False
          self.context = context
          self.request = request
          self.view = view

      def update(self):
          self.siteInfo = Products.GSContent.view.GSSiteInfo( self.context )
          self.groupInfo = createObject('groupserver.GroupInfo', 
            self.context)

          self.groupName = self.groupInfo.get_name()
          self.groupId = self.groupInfo.get_id()
          self.siteId = self.siteInfo.get_id()
          user = self.request.AUTHENTICATED_USER
          if user.getId() != None:
              self.fromEmailAddresses = user.get_emailAddresses()
              assert (len(self.fromEmailAddresses) > 0), \
                "User has no email addresses set."
              self.preferredEmailAddresses = \
                user.get_defaultDeliveryEmailAddresses()
              assert (len(self.preferredEmailAddresses) > 0), \
                "User has no preferred email addresses set."
              self.preferredEmailAddress = self.preferredEmailAddresses[0]
              if self.preferredEmailAddress not in self.fromEmailAddresses:
                  self.preferredEmailAddress = self.fromEmailAddresses[0]
          else:
              self.fromEmailAddresses = []
              self.preferredEmailAddress = None
          
          self.__updated = True
          
      def render(self):
          if not self.__updated:
              raise UpdateNotCalled
          
          pageTemplate = self.cookedTemplates.get(self.pageTemplateFileName)
          if not pageTemplate:
              pageTemplate = PageTemplateFile(self.pageTemplateFileName)    
              self.cookedTemplates.add(self.pageTemplateFileName, pageTemplate)
              
          return pageTemplate(startNew=self.startNew,
                              topic=self.topic,
                              groupName=self.groupName,
                              groupId=self.groupId,
                              siteId=self.siteId,
                              replyToId=self.replyToId,
                              fromEmailAddresses=self.fromEmailAddresses,
                              preferredEmailAddress=self.preferredEmailAddress)
          
      #########################################
      # Non standard methods below this point #
      #########################################

provideAdapter(GSPostMessageContentProvider, provides=IContentProvider,
  name="groupserver.PostMessage")

