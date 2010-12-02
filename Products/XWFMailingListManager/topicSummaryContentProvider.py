# coding=utf-8
from zope.component import createObject, adapts, provideAdapter
from zope.interface import implements, Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
import Products.Five, Products.GSContent 
from zope.app.pagetemplate import ViewPageTemplateFile
from zope.contentprovider.interfaces import IContentProvider
from interfaces import IGSTopicSummaryContentProvider

from Products.XWFCore.XWFUtils import get_user, get_user_realnames

# <zope-3 weirdness="high">
          
class GSTopicSummaryContentProvider(object):
      """GroupServer Topic Simmary Content Provider: summarise a topic
      """

      implements( IGSTopicSummaryContentProvider )
      adapts(Interface, IDefaultBrowserLayer, Interface)
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
          self.authorInfo = createObject('groupserver.UserFromId', 
            self.context, self.authorId)

          authorIds = []
          for post in self.topic:
              if post['author_id'] not in authorIds:
                  authorIds.append(post['author_id'])
          self.lenAuthors = len(authorIds)
          
          self.siteInfo = Products.GSContent.view.GSSiteInfo( self.context )
          self.groupInfo = createObject('groupserver.GroupInfo', self.context)
           
          assert self.__updated
          
      def render(self):
          """Render the post
          
          The donkey-work of this method is done by "self.pageTemplate", 
          which is set when the content-provider is created.
          
          RETURNS
              An HTML-snippet that represents the post."""
          if not self.__updated:
              raise interfaces.UpdateNotCalled
      
          pageTemplate = ViewPageTemplateFile(self.pageTemplateFileName)          

          return pageTemplate(self, length=len(self.topic),
                              lenAuthors=self.lenAuthors,
                              lastPostId = self.lastPost['post_id'],
                              lastPostDate = self.lastPost['date'],
                              authorInfo=self.authorInfo, 
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
                    
# State that the GSPostContentProvider is a Content Provider, and attach
#     to "groupserver.Post".
provideAdapter(GSTopicSummaryContentProvider, provides=IContentProvider,
 name="groupserver.TopicSummary")
# </zope-3 weirdness="high">
