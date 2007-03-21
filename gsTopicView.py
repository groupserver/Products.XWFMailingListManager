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
import Products.PythonScripts.standard
import transaction

import DocumentTemplate
import Products.XWFMailingListManager.stickyTopicToggleContentProvider
import queries

import Products.GSContent, Products.XWFCore.XWFUtils
from interfaces import IGSUserInfo
import addapost, view

class GSTopicView(view.GSPostingInfo):
      """View of a GroupServer Topic"""
      def __init__(self, context, request):
          self.retval = {}
          self.context = context
          self.request = request

          self.siteInfo = Products.GSContent.view.GSSiteInfo( context )
          self.groupInfo = view.GSGroupInfo( context )

          groupList = context.messages.get_xwfMailingListManager()
          useRdb = getattr(groupList, 'use_rdb', False)
         
          self.archive = context.messages
          self.emailId = request.form.get('id', None)
               
          if useRdb:
              da = None
              self.messageQuery = queries.MessageQuery(context, da)
              e = self.get_email_id()
              self.topicId = self.messageQuery.topic_id_from_post_id(e)
          else:
              self.messageQuery = None
              self.init_email_old()
              self.init_topic_old()

      def get_email(self):
          retval = self.email
          assert retval
          return retval
      def get_emailId(self):
          return self.emailId
      def init_email_old(self):
          # Missing error-handling
          assert self.emailId
          self.email = None
          self.email = self.archive.get_email(self.emailId)
          assert self.email

      def init_topic_old(self):
          assert self.emailId
          assert self.archive
          assert self.email
          
          # Mostly taken from XWFVirtualMailingListArchive.view_email
          
          query = {'compressedTopic': '%s' % self.email.compressedSubject}
          result = self.archive.find_email(query)
          
          query = {}
          resultSet = self.archive.find_email(query)
          sortFields = (('mailSubject', 'nocase'),
                        ('mailDate', 'cmp','desc'))
          result = DocumentTemplate.sequence.sort(resultSet,
                                                   sortFields)
          assert result
          r = [p.getObject() for p in result]
          cs = self.email.compressedSubject.lower()
          self.topic = [p for p in r 
                        if p['compressedSubject'].lower() == cs]
          self.topic.reverse()
          #self.topic = map(lambda x: x.getObject(), result)
          #self.topic.sort(self.post_date_storter)
          
          assert self.topic
          assert self.topic.append
          assert len(self.topic) > 0

      def update(self):
          result = view.process_form( self.context, self.request )
          if result:
              self.retval.update(result.items())
          result = view.process_post( self.context, self.request )
          if result:
              self.retval.update(result.items())

          if not self.messageQuery:
              self.init_topic_old()
              self.init_topic_old()
              self.init_threads()

      def init_threads(self):
          """Find out the threads that are temporally related to this
          topic, so we can show the previous and next links to the user.
          Painfully intensive."""
          
          assert self.topic
          assert self.archive
          
          self.threads  = self.archive.get_all_threads({}, 'mailDate', 'asc')
          self.threadNames = map(lambda thread: thread[1][0]['mailSubject'], 
                                 self.threads)
          currThreadName = self.get_topic_name()
          assert currThreadName in self.threadNames
          self.currThreadIndex = self.threadNames.index(currThreadName)         

      def get_topic(self):
          assert self.topic
          assert self.topic.append
          return self.topic
      
      def get_topic_name(self):
          assert self.email
          
          retval = self.email['mailSubject']
          
          return retval

          
      def get_next_topic(self):
          if self.messageQuery:
              r = self.messageQuery.next_topic(self.topicId)
              retval = (r['last_post_id'], r['subject'])
          else:
              retval = self.get_next_topic_old()
          return retval

      def get_next_topic_old(self):
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
          if self.messageQuery:
              r = self.messageQuery.previous_topic(self.topicId)
              retval = (r['last_post_id'], r['subject'])
          else:
              retval = self.get_previous_topic_old()
          return retval

      def get_previous_topic_old(self):
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
          
      def get_sticky_topics(self):
          assert self.threads
          
          retval = []
          
          stickyTopicsIds = self.groupInfo.get_property('sticky_topics')
          if stickyTopicsIds:
              for stickyTopicId in stickyTopicsIds:
                  query = {'id': stickyTopicId}
                  result = self.archive.find_email(query)[0]
                  threadInfo = {'id':     result.id,
                                'name':   result.mailSubject,
                                'date':   result.mailDate,
                                'length': ''}
                  retval.append(threadInfo)
          return retval
