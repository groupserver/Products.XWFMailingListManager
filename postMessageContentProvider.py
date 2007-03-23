import sys, re, datetime, time, types, string
import Products.Five, DateTime, Globals
#import Products.Five.browser.pagetemplatefile
import zope.schema
import zope.app.pagetemplate.viewpagetemplatefile
import zope.pagetemplate.pagetemplatefile
import zope.interface, zope.component, zope.publisher.interfaces
import zope.viewlet.interfaces, zope.contentprovider.interfaces 

import DocumentTemplate

import Products.GSContent, Products.XWFCore.XWFUtils

from view import GSGroupInfo
from interfaces import IGSPostMessageContentProvider

COOKED_TEMPLATES = {}

class GSPostMessageContentProvider(object):
      """GroupServer Post Message Content Provider
      """

      zope.interface.implements( IGSPostMessageContentProvider )
      zope.component.adapts(zope.interface.Interface,
                            zope.publisher.interfaces.browser.IDefaultBrowserLayer,
                            zope.interface.Interface)
            
      def __init__(self, context, request, view):
          self.__parent = view
          self.__updated = False
          self.context = context
          self.request = request
          self.view = view

      def update(self):
          self.siteInfo = Products.GSContent.view.GSSiteInfo( self.context )
          self.groupInfo = GSGroupInfo( self.context )

          self.groupName = self.groupInfo.get_name()
          self.groupId = self.groupInfo.get_id()
          self.siteId = self.siteInfo.get_id()
          user = self.request.AUTHENTICATED_USER
          if user.getId() != None:
              assert (len(user.emailAddresses) > 0), \
                "User has no email addresses set."
              self.fromEmailAddresses = user.emailAddresses
              assert (len(user.preferredEmailAddresses) > 0), \
                "User has no preferred email addresses set."
              self.preferredEmailAddress = user.preferredEmailAddresses[0]
              if self.preferredEmailAddress not in self.fromEmailAddresses:
                  self.preferredEmailAddress = self.fromEmailAddresses[0]
          else:
              self.fromEmailAddresses = []
              self.preferredEmailAddress = None
          
          self.__updated = True
          
      def render(self):
          if not self.__updated:
              raise interfaces.UpdateNotCalled
          VPTF = zope.pagetemplate.pagetemplatefile.PageTemplateFile
          self.pageTemplate = VPTF(self.pageTemplateFileName)

          if COOKED_TEMPLATES.has_key(self.pageTemplateFileName):
              pageTemplate = COOKED_TEMPLATES[self.pageTemplateFileName]
          else:
              VPTF = zope.pagetemplate.pagetemplatefile.PageTemplateFile
              pageTemplate = VPTF(self.pageTemplateFileName)    
              COOKED_TEMPLATES[self.pageTemplateFileName] = pageTemplate      
          
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

zope.component.provideAdapter(GSPostMessageContentProvider, 
                              provides=zope.contentprovider.interfaces.IContentProvider,
                              name="groupserver.PostMessage")
