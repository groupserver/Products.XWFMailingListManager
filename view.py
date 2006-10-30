'''GroupServer-Content View Class
'''
import sys, re, datetime, time, types, string
import Products.Five, DateTime, Globals
#import Products.Five.browser.pagetemplatefile
import zope.schema
import zope.app.pagetemplate.viewpagetemplatefile
zope.pagetemplate.pagetemplatefile
import zope.interface, zope.component, zope.publisher.interfaces
import zope.viewlet.interfaces, zope.contentprovider.interfaces 

import DocumentTemplate

import Products.GSContent, Products.XWFCore.XWFUtils

class GSBaseMessageView(Products.Five.BrowserView):
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
      
      def get_topic_name(self):
          assert self.email
          
          retval = self.email['mailSubject']
          
          return retval
          
      def process_form(self):
          pass

class GSTopicView(GSBaseMessageView):
      """View of a GroupServer Topic"""
      def __init__(self, context, request):
          # Preconditions
          assert context
          assert request
           
          GSBaseMessageView.__init__(self, context, request)

          self.init_threads()

      def init_threads(self):
          assert self.topic
          assert self.archive

          self.threads  = self.archive.get_all_threads({}, 'mailDate', 'asc')
          self.threadNames = map(lambda thread: thread[1][0]['mailSubject'], 
                                 self.threads)
          currThreadName = self.get_topic_name()
          assert currThreadName in self.threadNames
          self.currThreadIndex = self.threadNames.index(currThreadName)

      def get_next_topic(self):
          assert self.threads
          
          retval = None
          
          nextThreadIndex = self.currThreadIndex - 1
          if nextThreadIndex >= 0:
              ntID = self.threads[nextThreadIndex][1][0]['id']
              ntName = self.threads[nextThreadIndex][1][0]['mailSubject']
              retval = (ntID, ntName)
          else:
              retval = (None, None)
      
          assert len(retval) == 2
          return retval
          
      def get_previous_topic(self):
          assert self.threads
          
          retval = None

          previousThreadIndex = self.currThreadIndex + 1
          if previousThreadIndex < len(self.threads):
              ptID = self.threads[previousThreadIndex][1][0]['id']
              ptName = self.threads[previousThreadIndex][1][0]['mailSubject']
              retval = (ptID, ptName)
          else:
              retval = (None, None)
      
          assert len(retval) == 2
          return retval

class GSPostView(GSBaseMessageView):
      """A view of a single post in a topic.
      
      A view of a single post shares much in common with a view of an 
      entire topic, which is why it inherits from "GSTopicView". The main
      semantic difference is the ID specifies post to display, rather than
      the first post in the topic.   
      """      
      def __init__(self, context, request):
          # Preconditions
          assert context
          assert request
           
          GSBaseMessageView.__init__(self, context, request)

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
      
      def __markup_text(self, messageText):
          """Mark up the plain text
          
          Used to mark up the email: the URLs are escaped, and "@"
          characters are  replaced with "( at )". 
          
          ARGUMENTS
              "messageText" The text to alter.
               
          RETURNS
              A string containing the marked-up text.
              
          SIDE EFFECTS
              None.

          NOTE    
              Originally found in XWFCore."""
          import re, cgi
          retval = ''
          
          text = cgi.escape(messageText)
          text = re.sub('(?i)(http://|https://)(.+?)(\&lt;|\&gt;|\)|\]|\}|\"|\'|$|\s)',
                 '<a href="\g<1>\g<2>">\g<1>\g<2></a>\g<3>',
                 text)
          text = text.replace('@', ' ( at ) ')
      
          retval =  text
          
          assert retval
          assert retval.append
          return retval
      
      def __wrap_message(self, messageText, width=79):
          retval = ''
          remaining = messageText
          wrapped = []
          
          while len(remaining) > width:
              cut = width
              newline = find(remaining, '\n', 0, cut)
          
              if newline != -1:
                  cut = newline
              elif remaining[cut] != ' ':
                  temp = rfind(remaining, ' ', 0, cut-1)
                  if temp == -1:temp = find(remaining, ' ', cut-1, len(remaining))
                  if temp == -1: temp = len(remaining)
                  cut = temp
              wrapped.append(remaining[:cut])
              remaining = remaining[cut+1:]
          
          if remaining:
              wrapped.append(remaining)
          
          retval = join(wrapped, '\n')
          
          assert retval
          assert retval.append 
          return retval

      def __split_message(self, messageText, lines=0, 
                          max_consecutive_comment=12, 
                          max_consecutive_whitespace=3):
                          
          retval = ('', '')
          slines = text.split('\n')

          intro = []; body = []; i = 1;
          bodystart = 0; consecutive_comment = 0; 
          consecutive_whitespace = 0
          
          for line in slines:
              if (line[:2] == '--' or line[:2] == '==' or line[:2] == '__' or
                  line[:2] == '~~' or line [:3] == '- -'):
                  bodystart = 1
              
              # if we've started on the body, just append to body
              if bodystart: 
                  body.append(line)
              # count comments, but don't penalise top quoting as badly
              elif consecutive_comment >= max_consecutive_comment and i > 25: 
                  body.append(line)
                  bodystart = 1
              # if we've got less than 15 lines, just put it in the intro
              elif (i <= 15):
                  intro.append(line)
              elif (len(line) > 3 and line[:4] != '&gt;'):
                  intro.append(line)
              elif consecutive_whitespace <= max_consecutive_whitespace:
                  intro.append(line)
              else:
                  body.append(line)
                  bodystart = 1
              
              if len(line) > 3 and (line[:4] == '&gt;' or line.lower().find('wrote:') != -1):
                  consecutive_comment += 1
              else:
                  consecutive_comment = 0
              
              if len(line.strip()):
                  consecutive_whitespace = 0
              else:
                  consecutive_whitespace += 1
              
              i += 1
          
          rintro = []; trim = 1
          for line in intro[::-1]:
              if len(intro) < 5:
                  trim = 0
              if len(line) > 3:
                  ls = line[:4]
              elif line.strip():
                  ls = line.strip()[0]
              else:
                  ls = ''
              
              if trim and (ls == '&gt;' or ls == ''):
                  body.insert(0, line)
              elif trim and line.find('wrote:') > 2:
                  body.insert(0, line)
              elif trim and line.strip() and len(line.strip().split()) == 1:
                  body.insert(0, line)
              else:
                  trim = 0
                  rintro.insert(0, line)
          
          intro = '\n'.join(rintro)
          body = '\n'.join(body)
          retval = (intro, body)
          
          assert retval
          assert len(retval) == 2
          assert retval[0].append
          assert retval[1].append
          return retval
          
      def get_mail_body(self):
          assert self.post
          assert self.post['mailBody']

          body = self.post['mailBody']
          contentType = getattr(self.post, 'content-type', None)

          ctct = Products.XWFCore.XWFUtils.convertTextUsingContentType
          fullBody = ctct(body, contentType)  

          messageLength = int(getattr(email, 'x-xwfnotification-message-length', 
                              len(fullBody)))
          
          markedUpPost = self.__markup_text(fullBody[:messageLength]).strip()

          assert retval
          assert retval.append
          return retval

      def get_wrapped_email(self):
          retval = self.__wrap_message(self.get_mail_body())
          assert retval
          assert retval.append
          return retval
      
      def get_email_intro_and_remainder(self):
          retval = self.__split_message(self.get_wrapped_email())
          return retval
      
      def user_authored(self):
          """Did the user write the email message?
          
          ARGUMENTS
              None.
          
          RETURNS
              A boolean that is "True" if the current user authored the
              email message, "False" otherwise.
              
          SIDE EFFECTS
              None."""
          assert self.post
          assert self.request
          
          user = self.request.AUTHENTICATED_USER
          retval = user.getId() == self.post['mailUserId']
          
          assert retval in (True, False)
          return retval

      def author_exists(self):
          """Does the author of the post exist?
          
          RETURNS
             True if the author of the post exists on the system, False
             otherwise.
              
          SIDE EFFECTS
              None."""
      
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
