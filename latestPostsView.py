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
         
class GSLatestPostsView(Products.Five.BrowserView, 
                        Products.XWFMailingListManager.view.GSGroupObject):
      def __init__(self, context, request):
          # Preconditions
          assert context
          assert request
           
          Products.Five.BrowserView.__init__(self, context, request)
          Products.XWFMailingListManager.view.GSGroupObject.__init__(self, 
                                                                     context)
          self.set_archive(self.context.messages)
          self.init_start_and_end()
          self.init_posts()
                
      def set_archive(self, archive):
          """Set the email message archive to "archive"."""
          assert archive
          self.archive = archive
          assert self.archive
      
      def get_archive(self):
          """Get the email message archive."""
          assert self.archive
          return self.archive
          
      def init_start_and_end(self):
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

      def init_posts(self):
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
          self.posts.sort(self.post_date_sorter)
          #self.posts.reverse()

      def post_date_storter(self, a, b):
          if a['mailDate'] > b['mailDate']:
              retval = 1
          elif a['mailDate'] == b['mailDate']:
              retval = 0
          else:
              retval = -1
          assert retval in (1, 0, -1)
          return retval

          
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
