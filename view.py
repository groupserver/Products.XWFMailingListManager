'''GroupServer-Content View Class
'''
import sys, re, datetime, time, types
import Products.Five, DateTime, Globals
#import Products.Five.browser.pagetemplatefile
import zope.schema
import zope.app.pagetemplate.viewpagetemplatefile
zope.pagetemplate.pagetemplatefile
import zope.interface, zope.component, zope.publisher.interfaces
import zope.viewlet.interfaces, zope.contentprovider.interfaces 

import DocumentTemplate

import Products.GSContent

class GSPostView(Products.Five.BrowserView):
      
      def __init__(self, context, request):
          # Preconditions
          assert context
          assert request
           
          Products.Five.BrowserView.__init__(self, context, request)
          
          self.set_archive(self.context.messages)
          self.set_emailId(self.context.REQUEST.form.get('id', None))
          self.init_email()
          self.init_topic()
          
          # Postconditions
          assert self.archive
          assert self.emailId
          assert self.email
          assert self.topic
      
      def set_archive(self, archive):
          """Set the email message archive to "archive"."""
          assert archive
          self.archive = archive
          assert self.archive
      
      def get_archive(self):
          """Get the email message archive."""
          assert self.archive
          return self.archive
      
      # emailId
      def set_emailId(self, emailId):
          assert emailId
          self.emailId = emailId
          assert self.emailId
      
      def get_emailId(self):
          return self.emailId
      
      # email
      def init_email(self):
          # Missing error-handling
          assert self.emailId
          self.email = None
          self.email = self.archive.get_email(self.emailId)
          assert self.email
      
      def get_email(self):
          retval = self.email
          assert retval
          return retval

      # topic
      def init_topic(self):
          assert self.emailId
          assert self.archive
          assert self.email
          
          # Mostly taken from XWFVirtualMailingListArchive.view_email
          
          query = {'compressedTopic': '%s' % self.email.compressedSubject}
          result = self.archive.find_email(query)
          assert result
          
          self.topic = map(lambda x: x.getObject(), result)

          sortOrder = (('mailDate', 'cmp', 'asc'), 
                       ('mailSubject', 'nocase', 'asc'))
          DocumentTemplate.sequence.sort(self.topic, sortOrder)          
  
          assert self.topic
          assert self.topic.append
          assert len(self.topic) > 0
          
      def get_topic(self):
          assert self.topic
          assert self.topic.append
          return self.topic

      # Next and previous email messages
      def get_previous_email(self):
          assert self.topic
          assert self.email in self.topic
          
          retval = None
          
          emailPos = self.topic.index(self.email)
          previousPos = emailPos - 1
          
          if previousPos >= 0:
              retval = self.topic[previousPos]
          return retval
          
      def get_next_email(self):
          assert self.topic
          assert self.email in self.topic
          
          retval = None
          
          emailPos = self.topic.index(self.email)
          nextPos = emailPos + 1
          
          if nextPos < len(self.topic):
              retval = self.topic[nextPos]
          return retval

      def get_first_email(self):
          assert self.topic
          retval = self.topic[0]
          return retval
          
      def get_last_email(self):
          assert self.topic
          retval = self.topic[-1]
          return retval
          
      def process_form(self):
          pass

# <zope-3 weirdness="high">

class IGSPostContentProvider(zope.interface.Interface):
      """The Groupserver Post Content Provider Interface
      
      This interface defines the fields that must be set up, normally using
      TAL, before creating a "GSPostContentProvider" instance. See the
      latter for an example."""
      post = zope.schema.Field(title=u"Email Message Instance",
                               description=u"The email instance to display",
                               required=True, 
                               readonly=False)
zope.interface.directlyProvides(IGSPostContentProvider, 
                                zope.contentprovider.interfaces.ITALNamespaceData)

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

      zope.interface.implements(IGSPostContentProvider)
      zope.component.adapts(zope.interface.Interface,
                            zope.publisher.interfaces.browser.IDefaultBrowserLayer,
                            zope.interface.Interface)
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
      
          pageTemplateFileName = "browser/templates/email.pt"
          VPTF = zope.pagetemplate.pagetemplatefile.PageTemplateFile
          self.pageTemplate = VPTF(pageTemplateFileName)
      
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
          """
          assert self.post
          
          self.__updated = True
          
          self.authorId = self.post.mailUserId;
          self.authorName = self.get_author_realnames();
          self.authorExists = self.author_exists();
          self.authored = self.authorExists and self.user_authored();
          self.authorImage = self.get_author_image()
          assert self.__updated
          
      def render(self):
          """Render the post
          
          The donkey-work of this method is done by "self.pageTemplate", 
          which is set when the content-provider is created.
          
          RETURNS
              An HTML-snippet that represents the post."""
          if not self.__updated:
              raise interfaces.UpdateNotCalled
          return self.pageTemplate(authorId=self.authorId, 
                                   authorName=self.authorName,
                                   authorExists=self.authorExists,
                                   authorImage=self.authorImage,
                                   authored=self.authored,
                                   post=self.post)

      #########################################
      # Non-standard methods below this point #
      #########################################
      
      def user_authored(self):
          '''Did the user write the email message?
          
          ARGUMENTS
              None.
          
          RETURNS
              A boolean that is "True" if the current user authored the
              email message, "False" otherwise.
              
          SIDE EFFECTS
              None.'''
          assert self.post
          assert self.request
          
          user = self.request.AUTHENTICATED_USER
          retval = user.getId() == self.post['mailUserId']
          
          assert retval in (True, False)
          return retval

      def author_exists(self):
          '''Does the author of the post exist?
          
          RETURNS
             True if the author of the post exists on the system, False
             otherwise.
              
          SIDE EFFECTS
              None.'''
      
          assert self.post
          retval = False
          
          authorId = self.post['mailUserId']
          retval = self.context.Scripts.get.user_exists(authorId)
          
          assert retval in (True, False)
          return retval
      
      def get_author_image(self):
          """Get the URL for the image of the post's author.
          
          RETURNS
             A string, representing the URL, if the author has an image,
             "None" otherwise.
             
          SIDE EFFECTS
             None.
          """
          assert self.post

          retval = None          
          if self.author_exists():
              authorId = self.post['mailUserId']
              retval = self.context.Scripts.get.user_image(authorId)
          return retval
           
      def get_author_realnames(self):
          """Get the names of the post's author.
          
          RETURNS
              The name of the post's author. 
          
          SIDE EFFECTS
             None.
          """
          assert self.post
          
          authorId = self.post['mailUserId']
          retval = self.context.Scripts.get.user_realnames(authorId)
          
          return retval
# State that the GSPostContentProvider is a Content Provider, and attach
#     to "groupserver.Post".
zope.component.provideAdapter(GSPostContentProvider, 
                              provides=zope.contentprovider.interfaces.IContentProvider,
                              name="groupserver.Post")

# </zope-3 weirdness="high">
          
Globals.InitializeClass( GSPostView )
