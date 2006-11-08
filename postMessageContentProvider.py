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
          self.groupName = 'foo'
          self.groupId = 'foo'
          self.__updated = True
          
      def render(self):
          if not self.__updated:
              raise interfaces.UpdateNotCalled
          pageTemplateFileName = "browser/templates/postMessage.pt"
          VPTF = zope.pagetemplate.pagetemplatefile.PageTemplateFile
          self.pageTemplate = VPTF(pageTemplateFileName)
          
          return self.pageTemplate(startNew=self.startNew,
                                   topic=self.topic,
                                   groupName=self.groupName,
                                   groupId=self.groupId)
          
      #########################################
      # Non standard methods below this point #
      #########################################

zope.component.provideAdapter(GSPostMessageContentProvider, 
                              provides=zope.contentprovider.interfaces.IContentProvider,
                              name="groupserver.PostMessage")

class GSPostMessageDataContentProvider(GSPostMessageContentProvider):
      """Form data for posting a message
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
          self.groupName = 'foo'
          self.groupId = 'foo'
          self.siteId = 'foo'
          self.__updated = True
          
      def render(self):
          if not self.__updated:
              raise interfaces.UpdateNotCalled
          pageTemplateFileName = "browser/templates/postMessageData.pt"
          VPTF = zope.pagetemplate.pagetemplatefile.PageTemplateFile
          self.pageTemplate = VPTF(pageTemplateFileName)
          
          return self.pageTemplate(startNew=self.startNew,
                                   topic=self.topic,
                                   replyToId=self.replyToId,
                                   groupId = self.groupId,
                                   groupName = self.groupName,
                                   siteId = self.siteId)
          
      #########################################
      # Non standard methods below this point #
      #########################################

zope.component.provideAdapter(GSPostMessageDataContentProvider, 
                              provides=zope.contentprovider.interfaces.IContentProvider,
                              name="groupserver.PostMessageData")
