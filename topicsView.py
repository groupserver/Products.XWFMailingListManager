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

          # HACK because I stuffed up my local box.
          if self.siteInfo.get_id() == 'example_division':
              print self.groupInfo.get_id()
              self.topics = self.messageQuery.latest_topics('ogs', 
                                                            self.groupInfo.get_id())
              print self.topics
          else:
              self.topics = self.messageQuery.latest_topics(self.siteInfo.get_id(), 
                                                            self.groupInfo.get_id())
          assert self.topics
                
      def get_previous_summary_url(self):
          return ''
      
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
          return ''
          
          newStart = self.end
          newEnd = newStart + self.get_summary_length()
          if newStart < len(self.threads):
              retval = 'topics.html?start=%d&end=%d' % (newStart, newEnd)
          else:
              retval = ''
          return retval
      
      def get_last_summary_url(self):
          return ''
          newStart = len(self.threads) - self.get_summary_length()
          newEnd = len(self.threads)
          return 'topics.html?start=%d&end=%d' % (newStart, newEnd)
          
      def get_topics(self):
          assert self.topics
          return self.topics

      def get_sticky_topics(self):
          #assert self.threads
          
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
          
      def get_summary_length(self):
          return 20
                    
      def process_form(self, *args):
          pass
