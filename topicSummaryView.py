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

class GSTopicSummaryView(Products.Five.BrowserView, 
                         Products.XWFMailingListManager.view.GSGroupObject):
      __groupInfo = None
      def __init__(self, context, request):
          # Preconditions
          assert context
          assert request
           
          Products.Five.BrowserView.__init__(self, context, request)
          Products.XWFMailingListManager.view.GSGroupObject.__init__(self, 
                                                                     context)
          
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
          #assert self.threads
      
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
          #assert self.threads
          
          if len(self.threads) > self.start:
              topics = self.threads[self.start:self.end]
              if self.start == 0:
                  stickyTopics = self.get_sticky_topics()
                  stickyTopicNames = map(lambda t: t['name'].lower(),
                                         stickyTopics)
                  for topic in topics:
                      if topic['name'].lower() in stickyTopicNames:
                          topics.remove(topic)
              retval = topics
          else:
              retval = []
          assert retval.append
          assert len(retval) <= self.get_summary_length()
          return retval

      def get_sticky_topics(self):
          #assert self.threads
          
          retval = []
          
          groupInfo = self.get_group_info()
          stickyTopicsIds = groupInfo.get_property('sticky_topics')
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
          
      def __thread_sorter(self, a, b):
          assert a
          assert (a['date'], a)
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
