'''GroupServer-Content View Class
'''
import sys, re, datetime, time, types, string
import Products.Five, DateTime, Globals
#import Products.Five.browser.pagetemplatefile
import zope.schema
import zope.app.pagetemplate.viewpagetemplatefile
import zope.pagetemplate.pagetemplatefile
import zope.interface, zope.component, zope.publisher.interfaces
import zope.viewlet.interfaces, zope.contentprovider.interfaces 

import DocumentTemplate, Products.XWFMailingListManager.interfaces

import Products.GSContent, Products.XWFCore.XWFUtils

class GSSiteInfo:
    def __init__(self, context):
        assert context
        
        self.context = context
        self.siteObj = self.__get_site_object()
        self.config = self.__get_site_config()
        
    def __get_site_object(self):
        assert self.context
        retval = self.context
        markerAttr = 'is_division'
        
        while retval:
            try:
                if getattr(retval.aq_inner.aq_explicit, markerAttr, False):
                    break
                else:
                    retval = retval.aq_parent
            except:
                break
        retval = retval.aq_inner.aq_explicit
        assert retval 
        assert hasattr(retval, markerAttr)
        assert getattr(retval, markerAttr)
        return retval
                
    def __get_site_config(self):
        assert self.siteObj
        assert self.context
        retval = getattr(self.context, 'DivisionConfiguration', None)
        assert retval
        return retval
        
    def get_name(self):
        assert self.config
        
        retval = self.config.getProperty('siteName')
        if not retval:
            retval = self.siteObj.title_or_id()
            
        assert retval
        return retval
        
    def get_url(self):
        assert self.siteObj
        assert self.config
        retval = ''
        cannonicalHost = self.config.getProperty('canonicalHost', 'wibble')
        if cannonicalHost:
            retval = 'http://%s' % cannonicalHost
        else:
            retval = '/%s' % self.siteObj.absolute_url(1)

        assert retval
        return retval
        
class GSGroupInfo:
    def __init__(self, context):
        assert context
        self.context = context
        self.groupObj = self.__get_group_object()
        self.siteInfo = GSSiteInfo(context)

    def __get_group_object(self):
        assert self.context
        retval = self.context
        markerAttr = 'is_group'
        while retval:
            try:
                if getattr(retval.aq_inner.aq_explicit, markerAttr, False):
                    break
                else:
                    retval = retval.aq_parent
            except:
                break
        retval = retval.aq_inner.aq_explicit
        assert retval 
        assert hasattr(retval, markerAttr)
        assert getattr(retval, markerAttr)
        return retval

    def get_name(self):
        assert self.groupObj
        retval = self.groupObj.title_or_id()
        return retval
        
    def get_id(self):
        assert self.groupObj
        retval = self.groupObj.getId()
        return retval
        
    def get_url(self):
        assert self.groupObj
        assert self.siteInfo
        siteURL = self.siteInfo.get_url()
        retval = '%s/groups/%s' % (siteURL, self.get_id())
        return retval

class GSSiteObject:          
    def __init__(self, context):
          self.__set_site_info(GSSiteInfo(context))

    def __set_site_info(self, siteInfo):
          assert siteInfo
          self.__siteInfo = siteInfo
          assert self.__siteInfo
           
    def get_site_info(self):
          assert self.__siteInfo
          retval = self.__siteInfo
          assert retval
          return retval


class GSGroupObject(GSSiteObject):
    def __init__(self, context):
          GSSiteObject.__init__(self, context)
          self.__set_group_info(GSGroupInfo(context))

    def __set_group_info(self, groupInfo):
          assert groupInfo
          self.__groupInfo = groupInfo
          assert self.__groupInfo
           
    def get_group_info(self):
          assert self.__groupInfo
          retval = self.__groupInfo
          assert retval
          return retval
          
class GSLatestPostsView(Products.Five.BrowserView, GSGroupObject):
      def __init__(self, context, request):
          # Preconditions
          assert context
          assert request
           
          Products.Five.BrowserView.__init__(self, context, request)
          GSGroupObject.__init__(self, context)
          self.set_archive(self.context.messages)
          self.__init_start_and_end()
          self.__init_posts()
                
      def set_archive(self, archive):
          """Set the email message archive to "archive"."""
          assert archive
          self.archive = archive
          assert self.archive
      
      def get_archive(self):
          """Get the email message archive."""
          assert self.archive
          return self.archive
          
      def __init_start_and_end(self):
          assert self.request
          self.start = int(self.request.form.get('start', 0))
          if self.start < 0:
              self.start = 0
          self.end = int(self.request.form.get('end', 20))
          if self.start > self.end:
              self.end = self.start + 1
              
          assert self.start >= 0
          assert self.end
          assert self.start < self.end

      def __init_posts(self):
          assert self.start >= 0
          assert self.end >= self.start
          query = {}
          resultSet = self.archive.find_email(query)
          resultSet = DocumentTemplate.sequence.sort(resultSet,
                                                     (('mailDate', 
                                                       'cmp', 'desc'),
                                                      ('mailSubject',
                                                       'nocase')))
          self.posts = [post.getObject() for post in resultSet]
          
      def get_posts_length(self):
          assert self.start >= 0
          assert self.end
          
          retval = self.end - self.start
          
          assert retval
          assert retval > 0
          return retval

      def get_chunk_length(self):
          assert self.start >= 0
          assert self.end
          
          retval = self.end - self.start
          
          assert retval
          assert retval > 0
          return retval

      def get_posts(self):
          assert self.posts
          if len(self.posts) > self.start:
              retval = self.posts[self.start:self.end]
          else:
              retval = []
          assert retval.append
          assert len(retval) <= self.get_posts_length()
          return retval
         
      def get_previous_chunk_url(self):
          newStart = self.start - self.get_chunk_length()
          if newStart < 0:
              newStart = 0
          newEnd = newStart + self.get_chunk_length()
          
          if newStart != self.start and newStart:
              retval = 'posts.html?start=%d&end=%d' % (newStart, newEnd)
          elif newStart != self.start and not newStart:
              retval = 'posts.html'
          else:
              retval = ''
          return retval

      def get_next_chunk_url(self):
          newStart = self.end
          newEnd = newStart + self.get_chunk_length()
          if newStart < len(self.posts):
              retval = 'posts.html?start=%d&end=%d' % (newStart, newEnd)
          else:
              retval = ''
          return retval

      def get_last_chunk_url(self):
          newStart = len(self.posts) - self.get_chunk_length()
          newEnd = len(self.posts)
          return 'posts.html?start=%d&end=%d' % (newStart, newEnd)

      def process_form(self):
          pass

class GSTopicSummaryView(Products.Five.BrowserView, GSGroupObject):
      __groupInfo = None
      def __init__(self, context, request):
          # Preconditions
          assert context
          assert request
           
          Products.Five.BrowserView.__init__(self, context, request)
          GSGroupObject.__init__(self, context)
          
          self.set_archive(self.context.messages)
          self.__init_start_and_end()
          self.__init_threads()
                
      def set_archive(self, archive):
          """Set the email message archive to "archive"."""
          assert archive
          self.archive = archive
          assert self.archive
      
      def get_archive(self):
          """Get the email message archive."""
          assert self.archive
          return self.archive
          
      def __init_start_and_end(self):
          assert self.request
          self.start = int(self.request.form.get('start', 0))
          if self.start < 0:
              self.start = 0
          self.end = int(self.request.form.get('end', 20))
          if self.start > self.end:
              self.end = self.start + 1
              
          assert self.start >= 0
          assert self.end
          assert self.start < self.end

      def __init_threads(self):
          assert self.start >= 0
          assert self.end >= self.start
          query = {}
          resultSet = self.archive.find_email(query)
          resultSet = DocumentTemplate.sequence.sort(resultSet,
                                                     (('mailSubject',
                                                       'nocase'),
                                                      ('mailDate', 
                                                       'cmp', 'desc')))
          threads = []
          currThread = None
          currThreadResults = []
          threads = []
          
          for result in resultSet:
              subj = result.mailSubject.lower() 
              if subj != currThread:
                  currThread = subj
                  threadInfo = {'id':     result.id,
                                'name':   result.mailSubject,
                                'date':   result.mailDate,
                                'length': 1}
                  threads.append(threadInfo)
              else:
                  threads[-1]['length'] = threads[-1]['length'] + 1
          threads.sort(self.__thread_sorter)
          threads.reverse()
          
          self.threads = threads
          assert self.threads
      
      def get_summary_length(self):
          assert self.start >= 0
          assert self.end
          
          retval = self.end - self.start
          
          assert retval
          assert retval > 0
          return retval
      
      def get_previous_summary_url(self):
          newStart = self.start - self.get_summary_length()
          if newStart < 0:
              newStart = 0
          newEnd = newStart + self.get_summary_length()
          
          if newStart != self.start and newStart:
              retval = 'topics.html?start=%d&end=%d' % (newStart, newEnd)
          elif newStart != self.start and not newStart:
              retval = 'topics.html'
          else:
              retval = ''
          return retval
      
      def get_next_summary_url(self):
          newStart = self.end
          newEnd = newStart + self.get_summary_length()
          if newStart < len(self.threads):
              retval = 'topics.html?start=%d&end=%d' % (newStart, newEnd)
          else:
              retval = ''
          return retval
      
      def get_last_summary_url(self):
          newStart = len(self.threads) - self.get_summary_length()
          newEnd = len(self.threads)
          return 'topics.html?start=%d&end=%d' % (newStart, newEnd)
          
      def get_topics(self):
          assert self.threads
          if len(self.threads) > self.start:
              retval = self.threads[self.start:self.end]
          else:
              retval = []
          assert retval.append
          assert len(retval) <= self.get_summary_length()
          return retval
          
      def __thread_sorter(self, a, b):
          assert a
          assert a['date']
          assert b
          assert b['date']
          
          retval = 0
          valA = a['date']
          valB = b['date']
          if valA < valB:
              retval = -1
          elif valA == valB:
              retval = 0
          else:
              retval = 1
          
          assert retval in (-1, 0, 1)
          return retval
          
      def process_form(self, *args):
          pass

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

class GSTopicView(GSBaseMessageView, GSGroupObject):
      """View of a GroupServer Topic"""
      def __init__(self, context, request):
          # Preconditions
          assert context
          assert request
           
          GSBaseMessageView.__init__(self, context, request)
          GSGroupObject.__init__(self, context)
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

class GSPostView(GSBaseMessageView, GSGroupObject):
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
          GSGroupObject.__init__(self, context)
          
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

      zope.interface.implements(Products.XWFMailingListManager.interfaces.IGSPostContentProvider)
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
          
          ir = self.get_email_intro_and_remainder()
          self.postIntro, self.postRemainder = ir
          
          self.cssClass = self.get_cssClass()
           
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

          return pageTemplate(authorId=self.authorId, 
                              authorName=self.authorName,
                              authorExists=self.authorExists,
                              authorImage=self.authorImage,
                              authored=self.authored,
                              postIntro=self.postIntro,
                              postRemainder=self.postRemainder,
                              cssClass=self.cssClass,
                              topicName=self.topicName,
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
          retval = text.replace('@', ' ( at ) ')
         
          assert retval
          return retval
      
      def __wrap_message(self, messageText, width=79):
          """Word-wrap the message
          
          ARGUMENTS
              "messageText" The text to alter.
              "width"       The column-number which to wrap at.
              
          RETURNS
              A string containing the wrapped text.
              
          SIDE EFFECTS
              None.
              
          NOTE
              Originally a stand-alone script in
              "Presentation/Tofu/MailingListManager/lscripts"."""
          retval = ''
          remaining = messageText
          wrapped = []
          
          while len(remaining) > width:
              cut = width
              newline = string.find(remaining, '\n', 0, cut)
          
              if newline != -1:
                  cut = newline
              elif remaining[cut] != ' ':
                  temp = string.rfind(remaining, ' ', 0, cut-1)
                  if temp == -1:temp = string.find(remaining, ' ', cut-1, len(remaining))
                  if temp == -1: temp = len(remaining)
                  cut = temp
              wrapped.append(remaining[:cut])
              remaining = remaining[cut+1:]
          
          if remaining:
              wrapped.append(remaining)
          
          retval = string.join(wrapped, '\n')
          
          assert retval
          return retval

      def __split_message(self, messageText, 
                          max_consecutive_comment=12, 
                          max_consecutive_whitespace=3):
          """Split the message into main body and the footer.
          
          Email messages often contain a footer at the bottom, which
          identifies the user, and who they work for. However, GroupServer
          has lovely profiles which do this, so normally we want to snip
          the footer, to reduce clutter.
          
          In addition, many users only write a short piece of text at the
          top of the email, while the remainder of the message consists
          of all the previous posts. This method also removes the
          "bottom quoting".
          
          ARGUMENTS
              "messageText" The text to process.
              "max_consecutive_comment"    The maximum number of lines
                  of quoting to allow before snipping.
              "max_consecutive_whitespace" The maximum number of lines 
                  that just contain whitespace to allow before snipping.
          
          RETURNS
              2-tuple, containing the strings representing the main-body
              of the message, and the footer.
          
          SIDE EFFECTS
              None.

          NOTE
              Originally a stand-alone script in
              "Presentation/Tofu/MailingListManager/lscripts".
          """
          retval = ('', '')
          slines = messageText.split('\n')

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
          retval = (intro.strip(), body.strip())
          
          assert retval
          assert len(retval) == 2
          return retval
      
      def __remove_file_notification(self, messageText):
          """Remove the file notification from the end of the message
          
          If an file notification was sent with the message, then
          we want to remove this from the message, as the view has
          its own way of presenting files.
          
          ARGUMENTS
              "messageText" The text to snip.
          
          RETURNS
              The message without the fine notification.
          
          ENVIRONMENT
              "self.post['xwf-notification-message-length']" The length of
                  the message, without the file-notfication.
          """
          xwf_header = 'x-xwfnotification-message-length'
          messageLength = int(getattr(self.post, xwf_header, len(messageText)))
          retval = messageText[:messageLength]
          return retval
                    
      def get_mail_body(self):
          """Get the body of the mail message, formatted for the Web.
          
          The "self.post" instance contains the plain-text version
          of the message, as was sent out to the user's via email.
          For formatting on the Web it is necessary to convert the
          text to the correct content-type, replace all URLs with
          anchor-elements, remove all at signs, wrap the message to
          80 characters, and remove the file-notification. This method
          does these things.  
          
          ARGUMENTS
              None.
          
          RETURNS
              A string representing the formatted body of the email 
              message.
          
          SIDE EFFECTS
              None.  
          """
          assert self.post
          assert self.post['mailBody']

          body = self.post['mailBody']
          
          contentType = getattr(self.post, 'content-type', None)
          ctct = Products.XWFCore.XWFUtils.convertTextUsingContentType
          text = ctct(body, contentType)  
          
          text = self.__remove_file_notification(text)
          markedUpPost = self.__markup_text(text).strip()
          retval = self.__wrap_message(markedUpPost)
          
          assert retval
          return retval

      def get_email_intro_and_remainder(self):
          """Get the intoduction and remainder text of the formatted post
          
          ARGUMENTS
              None.
              
          RETURNS
              A 2-tuple of the strings that represent the email intro
              and the remainder.
              
          SIDE EFFECTS
              None.
          """
          retval = self.__split_message(self.get_mail_body())
          return retval
      
      def get_cssClass(self):
          retval = ''
          even = (self.position % 2) == 0
          if even:
              if self.authored:
                  retval = 'emaildetails-self-even'
              else:
                  retval = 'emaildetials-even'
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

zope.component.provideAdapter(GSPostContentProvider, 
                              provides=zope.contentprovider.interfaces.IContentProvider,
                              name="groupserver.PostAtom")


class GSTopicIndexContentProvider(object):
      """GroupServer Topic Index Content Provider
      
      """

      zope.interface.implements(Products.XWFMailingListManager.interfaces.IGSTopicIndexContentProvider)
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
          self.topciId = self.view.get_emailId() 
          hr = 'topic.html?id=%s' % self.topciId
          self.entries = [{'href':  '%s#%s' % (hr, post['id']),
                           'files': '', 
                           'name':  self.get_author_realnames_from_post(post),
                           'user':  self.get_user_authored_from_post(post),
                           'date':  self.get_date_from_post(post)} 
                           for post in self.topic ]
          self.__updated = True
          
      def render(self):
          if not self.__updated:
              raise interfaces.UpdateNotCalled
          pageTemplateFileName = "browser/templates/topicIndex.pt"
          VPTF = zope.pagetemplate.pagetemplatefile.PageTemplateFile
          self.pageTemplate = VPTF(pageTemplateFileName)
          
          return self.pageTemplate(entries=self.entries)
          
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
zope.component.provideAdapter(GSTopicIndexContentProvider, 
                              provides=zope.contentprovider.interfaces.IContentProvider,
                              name="groupserver.TopicIndex")

# </zope-3 weirdness="high">
          
Globals.InitializeClass( GSPostView )
