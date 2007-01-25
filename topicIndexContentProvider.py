import sys, re, datetime, time, types, string
import Products.Five, DateTime, Globals
#import Products.Five.browser.pagetemplatefile
import zope.schema
import zope.app.pagetemplate.viewpagetemplatefile
import zope.pagetemplate.pagetemplatefile
import zope.interface, zope.component, zope.publisher.interfaces
import zope.viewlet.interfaces, zope.contentprovider.interfaces 

import DocumentTemplate, Products.XWFMailingListManager

import Products.GSContent, Products.XWFCore.XWFUtils

from interfaces import IGSTopicIndexContentProvider
from view import GSGroupInfo

class GSTopicIndexContentProvider(object):
      """GroupServer Topic Index Content Provider
      
      """

      zope.interface.implements( IGSTopicIndexContentProvider )
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
          # The entries list is made up of 4-tuples representing the
          #   post ID, files, author, user authored, and post-date.
          self.topicId = self.view.get_emailId() 
          hr = 'topic.html?id=%s' % self.topicId
          self.entries = [{'href':  '%s#%s' % (hr, post['id']),
                           'files': self.get_file_from_post(post),
                           'name':  self.get_author_realnames_from_post(post),
                           'user':  self.get_user_authored_from_post(post),
                           'date':  self.get_date_from_post(post)} 
                           for post in self.topic ]

          self.siteInfo = Products.GSContent.view.GSSiteInfo( self.context )
          self.groupInfo = GSGroupInfo( self.context )
          
          self.__updated = True
          
      def render(self):
          if not self.__updated:
              raise interfaces.UpdateNotCalled
          pageTemplateFileName = "browser/templates/topicIndex.pt"
          VPTF = zope.pagetemplate.pagetemplatefile.PageTemplateFile
          self.pageTemplate = VPTF(pageTemplateFileName)
          
          return self.pageTemplate(entries=self.entries, 
                                   context=self.context)
          
      #########################################
      # Non standard methods below this point #
      #########################################
      
      def get_author_realnames_from_post(self, post):
          """Get the names of the post's author.
          
          ARGUMENTS
              "post" A post object.
              
          RETURNS
              The name of the post's author. 
          
          SIDE EFFECTS
             None.
          """
          assert post
          
          retval = ''
          authorId = post['mailUserId']
          retval = self.context.Scripts.get.user_realnames(authorId)

          return retval
          
      def get_user_authored_from_post(self, post):
          """Did the user write the email message?
          
          ARGUMENTS
              None.
          
          RETURNS
              A boolean that is "True" if the current user authored the
              email message, "False" otherwise.
              
          SIDE EFFECTS
              None."""
          assert post
          assert self.request
          
          user = self.request.AUTHENTICATED_USER
          retval = user.getId() == post['mailUserId']
          
          assert retval in (True, False)
          return retval

      def get_date_from_post(self, post):
          assert post
          retval = post['mailDate']
          assert retval
          return retval
      
      def get_file_from_post(self, post):
          assert post
          retval = ''
          if hasattr(post, 'x-xwfnotification-file-id'):
              # Just work with the first ID
              fileId = post['x-xwfnotification-file-id'].split()[0]
              retval = fileId
          return retval
zope.component.provideAdapter(GSTopicIndexContentProvider, 
                              provides=zope.contentprovider.interfaces.IContentProvider,
                              name="groupserver.TopicIndex")
