import sys, re, datetime, time, types, string
import Products.Five, DateTime, Globals
#import Products.Five.browser.pagetemplatefile
import zope.schema
import zope.pagetemplate.pagetemplatefile
import zope.interface, zope.component, zope.publisher.interfaces
import zope.viewlet.interfaces, zope.contentprovider.interfaces 

import DocumentTemplate
import Products.XWFMailingListManager.view

import Products.GSContent, Products.XWFCore.XWFUtils

from interfaces import IGSStickyTopicToggleContentProvider

class GSStickyTopicToggleContentProvider(object):
      """GroupServer Post Message Content Provider
      """

      zope.interface.implements( IGSStickyTopicToggleContentProvider )
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
          self.__updated = True
          
          stickyTopics = self.view.get_sticky_topics()
          stickyTopicIds = [topic['topic_id'] for topic in stickyTopics]
          # Add or remove the topic.
          self.add = self.topicId not in stickyTopicIds
          
      def render(self):
          if not self.__updated:
              raise interfaces.UpdateNotCalled
          VPTF = zope.pagetemplate.pagetemplatefile.PageTemplateFile
          self.pageTemplate = VPTF(self.pageTemplateFileName)

          addOrRemove = self.add and 'add' or 'remove'
          return self.pageTemplate(instance=addOrRemove,
                                   add=self.add,
                                   groupId=self.groupInfo.get_id(),
                                   siteId=self.siteInfo.get_id(),
                                   topicId=self.view.topicId)
          
      #########################################
      # Non standard methods below this point #
      #########################################

zope.component.provideAdapter(GSStickyTopicToggleContentProvider, 
                              provides=zope.contentprovider.interfaces.IContentProvider,
                              name="groupserver.StickyTopicToggle")
