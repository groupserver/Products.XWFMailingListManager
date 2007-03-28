import sys, re, datetime, time, types, string
import Products.Five, Products.GSContent, DateTime, Globals
import zope.schema
import zope.app.pagetemplate.viewpagetemplatefile
import zope.pagetemplate.pagetemplatefile
import zope.interface, zope.component, zope.publisher.interfaces
import zope.viewlet.interfaces, zope.contentprovider.interfaces 

import DocumentTemplate, Products.XWFMailingListManager

import Products.GSContent, Products.XWFCore.XWFUtils

from view import GSGroupInfo, GSPostingInfo
import queries

class GSTopicsView( Products.Five.BrowserView, GSPostingInfo ):
      """List of latest topics in the group."""
      __groupInfo = None
      def __init__(self, context, request):
          self.context = context
          self.request = request

          self.siteInfo = Products.GSContent.view.GSSiteInfo( context )
          self.groupInfo = GSGroupInfo( context )
          
          da = context.zsqlalchemy 
          assert da
          self.messageQuery = queries.MessageQuery(context, da)
  
          self.start = int(self.request.form.get('start', 0))
          self.end = int(self.request.form.get('end', 20))
          # Swap the start and end, if necessary
          if self.start > self.end:
              tmp = self.end
              self.end = self.start
              self.start = tmp
          
          messages = self.context.messages
          lists = messages.getProperty('xwf_mailing_list_ids')

          limit = self.get_summary_length()

          self.numTopics = self.messageQuery.topic_count(self.siteInfo.get_id(), lists)
          self.topics = self.messageQuery.latest_topics(self.siteInfo.get_id(),
                                                        lists,
                                                        limit=limit,
                                                        offset=self.start)

      def get_later_url(self):
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
      
      def get_earlier_url(self):
          newStart = self.end
          newEnd = newStart + self.get_summary_length()
          if newStart < self.numTopics:
              retval = 'topics.html?start=%d&end=%d' % (newStart, newEnd)
          else:
              retval = ''
          return retval
      
      def get_last_url(self):
          newStart = self.numTopics - self.get_summary_length()
          newEnd = self.numTopics
          return 'topics.html?start=%d&end=%d' % (newStart, newEnd)

      def get_summary_length(self):
          assert hasattr(self, 'start')
          assert hasattr(self, 'end')
          assert self.start <= self.end
          
          retval = self.end - self.start
          
          assert retval >= 0
          return retval;
          
      def get_topics(self):
          assert hasattr(self, 'topics')
          return self.topics

      def get_sticky_topics(self):
          retval = []
          return retval
                    
          stickyTopicsIds = self.groupInfo.get_property('sticky_topics')
          if stickyTopicsIds and (self.start == 0):
              for stickyTopicId in stickyTopicsIds:
                  query = {'id': stickyTopicId}
                  result = self.archive.find_email(query)[0]
                  threadInfo = {'id':     result.id,
                                'name':   result.mailSubject,
                                'date':   result.mailDate,
                                'length': ''}
                  retval.append(threadInfo)
          return retval
                              
      def process_form(self, *args):
          pass
