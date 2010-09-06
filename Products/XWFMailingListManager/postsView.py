# coding=utf-8
import Products.Five, Products.GSContent, Globals
import zope.schema
import zope.pagetemplate.pagetemplatefile
import zope.interface, zope.component, zope.publisher.interfaces
from zope.component import createObject
import zope.viewlet.interfaces, zope.contentprovider.interfaces 
import DocumentTemplate, Products.XWFMailingListManager
import Products.GSContent, Products.XWFCore.XWFUtils,  queries
from Products.GSGroup.utils import is_public

import logging
log = logging.getLogger('Products.XWFMailingList.postsView')

class GSPostsView(Products.Five.BrowserView):
      topNPosts = 64
      def __init__(self, context, request):
          self.context = context
          self.request = request
          
          self.siteInfo = Products.GSContent.view.GSSiteInfo( context )
          self.groupInfo = createObject('groupserver.GroupInfo', context)
           
          self.isPublic = is_public(self.groupInfo.groupObj)
          
          self.start = int(self.request.form.get('start', 0))
          self.end = int(self.request.form.get('end', 20))
          # Swap the start and end, if necessary
          if self.start > self.end:
              tmp = self.end
              self.end = self.start
              self.start = tmp
          nPosts = (self.end - self.start)
          if (nPosts >  self.topNPosts):
              m = u'Request for %d posts (%d--%d) from %s (%s) on ' \
                u'%s (%s) is too high; returning %d.' % \
                (nPosts, self.start, self.end, self.groupInfo.name,
                self.groupInfo.id, self.siteInfo.name, 
                self.siteInfo.id, self.topNPosts)
              log.warn(m)
              self.end = self.start + self.topNPosts
          
          da = context.zsqlalchemy 
          assert da
          self.messageQuery = queries.MessageQuery(context, da)
          
          messages = self.context.messages
          lists = messages.getProperty('xwf_mailing_list_ids')

          limit = self.get_chunk_length()
          self.numPosts = self.messageQuery.post_count(self.siteInfo.get_id(),
                                                      lists)
          self.posts = self.messageQuery.latest_posts(self.siteInfo.get_id(), 
                                                      lists, limit=limit,
                                                      offset=self.start)

      def get_posts(self):
          assert hasattr(self, 'posts')
          return self.posts

      def get_chunk_length(self):
          assert hasattr(self, 'start')
          assert hasattr(self, 'end')
          assert self.start <= self.end
          
          retval = self.end - self.start
          
          assert retval >= 0
          return retval;
          
      def get_later_url(self):
          assert hasattr(self, 'start')

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

      def get_earlier_url(self):
          assert hasattr(self, 'end')

          newStart = self.end
          newEnd = newStart + self.get_chunk_length()
          if newStart < self.numPosts:
              retval = 'posts.html?start=%d&end=%d' % (newStart, newEnd)
          else:
              retval = ''
          return retval

      def get_last_url(self):
          newStart = self.numPosts - self.get_chunk_length()
          newEnd = self.numPosts
          return 'posts.html?start=%d&end=%d' % (newStart, newEnd)

      def get_most_recent_post_date(self):
          retval = ''
          
          if self.posts:
              mostRecentPost = self.posts[0]
              d = mostRecentPost['date']
              date = d - d.utcoffset()
              retval = date.strftime('%Y-%m-%dT%H:%M:%SZ')
              
          return retval
          
      def process_form(self):
          pass

      @property
      def web_feed_uri(self):
          retval = '/s/search.atom?g=%s&p=1&t=0&l=%d' %\
            (self.groupInfo.id, self.get_chunk_length())
          assert type(retval) == str
          return retval

class GSPostsViewWebFeed(GSPostsView):
      def __init__(self, context, request):
          GSPostsView.__init__(self, context, request)

      def __call__(self):
          self.request.response.redirect(self.web_feed_uri)

