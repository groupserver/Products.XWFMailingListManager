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

from interfaces import IGSTopicSummaryContentProvider
from view import GSGroupInfo

# <zope-3 weirdness="high">
          
class GSTopicSummaryContentProvider(object):
      """GroupServer Topic Simmary Content Provider: summarise a topic
      """

      zope.interface.implements( IGSTopicSummaryContentProvider )
      zope.component.adapts(zope.interface.Interface,
                            zope.publisher.interfaces.browser.IDefaultBrowserLayer,
                            zope.interface.Interface)
      post = None
      def __init__(self, context, request, view):
          """Create a GSTopicSummaryContentProvider instance.
          
          Like any other content-provider class, the context, request and
          view are passed as arguments to "__init__". However, this is
          normally done by TAL, rather than explicitly by the coders.
          
          SIDE EFFECTS
            The following attributes are set.
              * "self.__parent"     Set to "view".
              * "self.__updated"    Set to "False"
              * "self.context"      Set to "context"
              * "self.request"      Set to "request"
              * "self.pageTemplate" Set to the hard-coded page template 
                                    object, which is used to render the 
                                    post.
              """
          self.__parent__ = self.view = view
          self.__updated = False
      
          self.context = context
          self.request = request

      def update(self):
          self.__updated = True
          self.lastPost = self.topic[-1]
          self.authorId = self.lastPost['author_id']
          self.authorName = self.get_author_realnames()
          self.authorExists = self.author_exists()
         
          self.siteInfo = Products.GSContent.view.GSSiteInfo( self.context )
          self.groupInfo = GSGroupInfo( self.context )
           
          assert self.__updated
          
      def render(self):
          """Render the post
          
          The donkey-work of this method is done by "self.pageTemplate", 
          which is set when the content-provider is created.
          
          RETURNS
              An HTML-snippet that represents the post."""
          if not self.__updated:
              raise interfaces.UpdateNotCalled
      
          VPTF = zope.pagetemplate.pagetemplatefile.PageTemplateFile
          pageTemplate = VPTF(self.pageTemplateFileName)          

          return pageTemplate(length=len(self.topic),
                              lastPostId = self.lastPost['post_id'],
                              lastPostDate = self.lastPost['date'],
                              authorId=self.authorId, 
                              authorName=self.authorName,
                              authorExists=self.authorExists,
                              context=self.context,
                              siteName = self.siteInfo.get_name(),
                              siteURL = self.siteInfo.get_url(),
                              groupId = self.groupInfo.get_id())

      #########################################
      # Non-standard methods below this point #
      #########################################
          

      def user_authored(self):
          """Did the user write the email message?
          
          ARGUMENTS
              None.
          
          RETURNS
              A boolean that is "True" if the current user authored the
              email message, "False" otherwise.
              
          SIDE EFFECTS
              None."""
          assert self.lastPost
          assert self.request
          assert self.authorId
          
          user = self.request.AUTHENTICATED_USER
          retval = user.getId() == self.authorId
          
          assert retval in (True, False)
          return retval

      def author_exists(self):
          """Does the author of the post exist?
          
          RETURNS
             True if the author of the post exists on the system, False
             otherwise.
              
          SIDE EFFECTS
              None."""
          assert self.authorId

          retval = False          
          retval = self.context.Scripts.get.user_exists(self.authorId)
          
          assert retval in (True, False)
          return retval

      def get_author_realnames(self):
          """Get the names of the post's author.
          
          RETURNS
              The name of the post's author. 
          
          SIDE EFFECTS
             None.
          """
          retval = self.context.Scripts.get.user_realnames(self.authorId)
          
          return retval
          
# State that the GSPostContentProvider is a Content Provider, and attach
#     to "groupserver.Post".
zope.component.provideAdapter(GSTopicSummaryContentProvider,
                              provides=zope.contentprovider.interfaces.IContentProvider,
                              name="groupserver.TopicSummary")
# </zope-3 weirdness="high">
