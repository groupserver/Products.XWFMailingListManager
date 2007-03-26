from interfaces import IGSTopicIndexContentProvider
from view import GSGroupInfo
from zope.component import adapts
from zope.component import provideAdapter
from zope.contentprovider.interfaces import IContentProvider, UpdateNotCalled
from zope.interface import implements
from zope.interface.interface import Interface
from zope.pagetemplate.pagetemplatefile import PageTemplateFile
from zope.publisher.interfaces.browser import IDefaultBrowserLayer

import Products.GSContent
import Products.XWFCore.XWFUtils
import Products.XWFMailingListManager

class GSTopicIndexContentProvider(object):
      """GroupServer Topic Index Content Provider
      
      """
      implements( IGSTopicIndexContentProvider )
      adapts(Interface,
             IDefaultBrowserLayer,
             Interface)
      
      def __init__(self, context, request, view):
          self.__parent = view
          self.__updated = False
          self.context = context
          self.request = request
          self.view = view       
          
      def update(self):
          # The entries list is made up of 4-tuples representing the
          #   post ID, files, author, user authored, and post-date.
          hr = 'topic/%s' % self.view.lastPostId
          self.entries = [{'href':  '%s#post-%s' % (hr, post['post_id']),
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
              raise UpdateNotCalled
          
          pageTemplateFileName = "browser/templates/topicIndex.pt"
          self.pageTemplate = PageTemplateFile(pageTemplateFileName)
          
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
          
          authorId = post['author_id']
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
          retval = user.getId() == post['author_id']
          
          assert retval in (True, False)
          return retval

      def get_date_from_post(self, post):
          assert post
          retval = post['date']
          assert retval
          return retval
      
      def get_file_from_post(self, post):
          assert post
          retval = ()
          if hasattr(post, 'x-xwfnotification-file-id'):
              # Just work with the first ID
              fileId = post['x-xwfnotification-file-id'].split()[0]
              filesArchive = self.context.files
              files = filesArchive.find_files({'id': fileId})
              if files:
                  fileType = files[0].content_type
                  retval = (fileId, fileType)
          return retval

provideAdapter(GSTopicIndexContentProvider, 
               provides=IContentProvider,
               name="groupserver.TopicIndex")
