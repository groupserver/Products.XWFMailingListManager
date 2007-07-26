from Products.GSContent.view import GSSiteInfo
from Products.XWFCore.XWFUtils import get_user, get_user_realnames
from Products.XWFCore.cache import LRUCache, SimpleCache
from interfaces import IGSPostContentProvider
import textwrap, re

from zope.contentprovider.interfaces import IContentProvider, UpdateNotCalled
from zope.interface import implements, Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from zope.component import adapts, provideAdapter, createObject
from zope.pagetemplate.pagetemplatefile import PageTemplateFile

from emailbody import get_email_intro_and_remainder

# <zope-3 weirdness="high">

class GSPostContentProvider(object):
      """GroupServer Post Content Provider: display a single post
      
      This content provider, which implements the "IGSPostContentProvider"
      and "IContentProvider" interfaces, displays a single post. The post
      is specified by setting the "post" variable to an instance of an 
      email-object. The post-instance is examined, during the "update", to
      determine additional information, which is passed to the email 
      page-template during the "render" phase.
      
      EXAMPLE
         <p tal:define="post python:view.get_email()"
            tal:replace="structure provider:groupserver.Post">
            The email message is rendered by the Post content provider,
            not by this page.
         </p>
      """

      implements(IGSPostContentProvider)
      adapts(Interface,
             IDefaultBrowserLayer, 
             Interface)
      
      # These following are *CLASS* attributes, because we want the cache to
      # be accessible across all instances!
      
      # We want a really simple cache for templates, because there aren't
      #  many of them
      cookedTemplates = SimpleCache()
      
      # Setup a least recently used expiry cache for results, with a K
      #   of posts, maximum.
      cookedResult = LRUCache()
      cookedResult.set_max_objects(1024)
      
      post = None
      def __init__(self, context, request, view):
          """Create a GSPostContentProvider instance.
          
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
          """Update the internal state of the post content-provider.
          
          This method can be considered the main "setter" for the 
          content provider; for the most part, information about the post's 
          author is set.
          
          SIDE EFFECTS
            The following attributes are set.
              * "self.__updated"     Set to "True"
              * "self.authorId"      Set to the user-id of the post author.
              * "self.authorName"    Set to the name of the post author.
              * "self.authorExists"  Set to "True" if the author exists
              * "self.authored"      Set to "True" if the current user 
                                     authored the post.
              * "self.authorImage"   Set to the URL of the author's image.
              * "self.siteInfo"     Set to an instance of GSSiteInfo
              * "self.groupInfo"    Set to an instance of GSGroupInfo
          """
          assert self.post
          
          self.__updated = True
          
          # setup a cache key based on the unique attributes of this post
          self.cacheKey = '%s:%s:%s' % (self.post['post_id'], self.position,
                                   self.topicName)
          
          if not self.cookedResult.has_key(self.cacheKey):
              self.authorId = self.post['author_id']
              self.authorName = self.get_author_realnames()
              self.authored = self.user_authored()
              self.authorExists = self.author_exists()
              self.authorImage = self.get_author_image()
             
              ir = get_email_intro_and_remainder(self.post['body'])
              self.postIntro, self.postRemainder = ir
              
              self.cssClass = self.get_cssClass()
              
              self.filesMetadata = self.post['files_metadata']
              
              self.siteInfo = GSSiteInfo(self.context)
              self.groupInfo = createObject('groupserver.GroupInfo', 
                self.context)
          
      def render(self):
          """Render the post
          
          The donkey-work of this method is done by "self.pageTemplate", 
          which is set when the content-provider is created.
          
          RETURNS
              An HTML-snippet that represents the post.
              
          """
          if not self.__updated:
              raise UpdateNotCalled
          
          r = self.cookedResult.get(self.cacheKey)
          if not r:
              pageTemplate = self.cookedTemplates.get(self.pageTemplateFileName)
              if not pageTemplate:
                  pageTemplate = PageTemplateFile(self.pageTemplateFileName)    
                  self.cookedTemplates.add(self.pageTemplateFileName, pageTemplate)
              
              r = pageTemplate(authorId=self.authorId, 
                                  authorName=self.authorName, 
                                  authorImage=self.authorImage, 
                                  authorExists=self.authorExists, 
                                  showPhoto=self.showPhoto, 
                                  authored=self.authored, 
                                  postIntro=self.postIntro, 
                                  postRemainder=self.postRemainder, 
                                  cssClass=self.cssClass, 
                                  topicName=self.topicName, 
                                  filesMetadata=self.filesMetadata,
                                  post=self.post, 
                                  context=self.context, 
                                  siteName = self.siteInfo.get_name(), 
                                  siteURL = self.siteInfo.get_url(), 
                                  groupId = self.groupInfo.get_id())
              
              self.cookedResult.add(self.post['post_id'], r)
          
          return r

      #########################################
      # Non-standard methods below this point #
      #########################################

      def get_cssClass(self):
          retval = ''
          even = (self.position % 2) == 0
          if even:
              if self.authored:
                  retval = 'emaildetails-self-even'
              else:
                  retval = 'emaildetails-even'
          else:
              if self.authored:
                  retval = 'emaildetails-self-odd'
              else:
                  retval = 'emaildetails-odd'
                  
          assert retval
          return retval

      def user_authored(self):
          """Did the user write the email message?
          
          ARGUMENTS
              None.
          
          RETURNS
              A boolean that is "True" if the current user authored the
              email message, "False" otherwise.
              
          SIDE EFFECTS
              None.
              
          """
          user = self.request.AUTHENTICATED_USER
          retval = False
          if user.getId():
              retval = user.getId() == self.authorId
              
          assert retval in (True, False)
          return retval

      def get_author(self):
          """ Get the user object associated with the author.
          
          RETURNS
             The user object if the author has an account, otherwise None.
          
          """
          author_cache = getattr(self.view, '__author_object_cache', {})
          user = author_cache.get(self.authorId, None)
          if not user:
              user = get_user(self.context, self.authorId)
              author_cache[self.authorId] = user
              self.view.__author_object_cache = author_cache
              
          return user

      def author_exists(self):
          """ Does the author exist?
          
          """
          return self.get_author() and True or False
      
      def get_author_image(self):
          """Get the URL for the image of the post's author.
          
          RETURNS
             A string, representing the URL, if the author has an image,
             "None" otherwise.
             
          SIDE EFFECTS
             None.
          
          """
          user = self.get_author()
          retval = None
          if user:
              retval = user.get_image()
              
          return retval
           
      def get_author_realnames(self):
          """Get the names of the post's author.
          
          RETURNS
              The name of the post's author. 
          
          SIDE EFFECTS
             None.
          
          """
          retval = get_user_realnames( self.get_author(), self.authorId )
          
          return retval
          
# State that the GSPostContentProvider is a Content Provider, and attach
#     to "groupserver.Post".
provideAdapter(GSPostContentProvider, 
               provides=IContentProvider, 
               name="groupserver.Post")

provideAdapter(GSPostContentProvider, 
               provides=IContentProvider, 
               name="groupserver.PostAtom")
# </zope-3 weirdness="high">

