import sys, re, datetime, time, types, string
import Products.Five, DateTime, Globals
#import Products.Five.browser.pagetemplatefile
import zope.schema
import zope.app.pagetemplate.viewpagetemplatefile
import zope.pagetemplate.pagetemplatefile
import zope.interface, zope.component, zope.publisher.interfaces
import zope.viewlet.interfaces, zope.contentprovider.interfaces 

import DocumentTemplate
import Products.XWFMailingListManager.view

import Products.GSContent, Products.XWFCore.XWFUtils

class GSPostMessageContentProvider(object):
      """GroupServer Post Message Content Provider
      """

      zope.interface.implements(Products.XWFMailingListManager.interfaces.IGSPostMessageContentProvider)
      zope.component.adapts(zope.interface.Interface,
                            zope.publisher.interfaces.browser.IDefaultBrowserLayer,
                            zope.interface.Interface)
      
      
      def __init__(self, context, request, view):
          self.__parent = view
          self.__updated = False
          self.context = context
          self.request = request
          self.view = view

          #GSGroupObject.__init__(self, context)
          
      def update(self):
          #groupInfo = self.get_group_info()
          self.groupName = self.groupInfo.get_name()
          self.groupId = self.groupInfo.get_id()
          self.siteId = self.siteInfo.get_id()
          user = self.request.AUTHENTICATED_USER
          self.fromEmailAddresses = user.emailAddresses
          self.preferredEmailAddress = user.preferredEmailAddresses[0]
          if self.preferredEmailAddress not in self.fromEmailAddresses:
              self.preferredEmailAddress = self.fromEmailAddresses[0]
          self.__updated = True
          
      def render(self):
          if not self.__updated:
              raise interfaces.UpdateNotCalled
          VPTF = zope.pagetemplate.pagetemplatefile.PageTemplateFile
          self.pageTemplate = VPTF(self.pageTemplateFileName)
          
          return self.pageTemplate(startNew=self.startNew,
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
