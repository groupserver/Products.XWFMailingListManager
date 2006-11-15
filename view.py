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

import DocumentTemplate
import Products.XWFMailingListManager.interfaces
import Products.XWFMailingListManager.postContentProvider
import Products.XWFMailingListManager.topicIndexContentProvider
import Products.XWFMailingListManager.postMessageContentProvider

import Products.GSContent, Products.XWFCore.XWFUtils

class GSGroupInfo:
    def __init__(self, context):
        assert context
        self.context = context
        self.groupObj = self.__get_group_object()
        self.siteInfo = Products.GSContent.view.GSSiteInfo(context)

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
          self.__set_site_info(Products.GSContent.view.GSSiteInfo(context))

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

class GSNewTopicView(Products.Five.BrowserView, GSGroupObject):
      def __init__(self, context, request):
          # Preconditions
          assert context
          assert request
           
          Products.Five.BrowserView.__init__(self, context, request)
          GSGroupObject.__init__(self, context)

      def process_form(self):
        form = self.context.REQUEST.form
        result = {}
        if form.has_key('submitted'):
            model = form['model']
            instance = form['instance']
            
            oldScripts = self.context.Scripts.forms
            if hasattr(oldScripts, model):
                modelDir = getattr(oldScripts, model)
                if hasattr(modelDir, instance):
                    script = getattr(modelDir, instance)
                    return script()
                else:
                    m = """<p>Could not find the instance
                           <code>%s</code></p>.""" % instance
                    result['error'] = True
                    result['message'] = m
            else:
                m = """<p>Could not find the model 
                       <code>%s</code></p>.""" % model
                result['error'] = True
                result['message'] = m
            assert result.has_key('error')
            assert result.has_key('message')
            assert result['message'].split
    
        result['form'] = form            
        return result

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

      def post_date_storter(self, a, b):
          if a['mailDate'] > b['mailDate']:
              retval = 1
          elif a['mailDate'] == b['mailDate']:
              retval = 0
          else:
              retval = -1
          assert retval in (1, 0, -1)
          return retval
          
      # topic
      def init_topic(self):
          GSBaseMessageView.init_topic(self)
          
          self.topic.sort(self.post_date_storter)
          
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
          
      def process_form(self):
        form = self.context.REQUEST.form
        result = {}
        if form.has_key('submitted'):
            model = form['model']
            instance = form['instance']
            
            oldScripts = self.context.Scripts.forms
            if hasattr(oldScripts, model):
                modelDir = getattr(oldScripts, model)
                if hasattr(modelDir, instance):
                    script = getattr(modelDir, instance)
                    return script()
                else:
                    m = """<p>Could not find the instance
                           <code>%s</code></p>.""" % instance
                    result['error'] = True
                    result['message'] = m
            else:
                m = """<p>Could not find the model 
                       <code>%s</code></p>.""" % model
                result['error'] = True
                result['message'] = m
            assert result.has_key('error')
            assert result.has_key('message')
            assert result['message'].split
    
        result['form'] = form            
        return result

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

class GSCurrentUserInfo:
    """Information about the current user"""
    zope.interface.implements(Products.XWFMailingListManager.interfaces.IGSUserInfo)
    
    def __init__(self):
        pass
    
    def exists(self):
        return True
    def get_id(self):
        pass
    def get_image(self):
        pass
    def get_real_names(self, preferredNameOnly=True):
        pass
          
Globals.InitializeClass( GSPostView )
