# coding=utf-8
from Products.Five import BrowserView
from zope.component import getMultiAdapter, createObject
import Products.GSContent
from Products.GSSearch import queries
from Products.GSGroupMember.interfaces import IGSPostingUser
# from view import GSPostingInfo # FIX

class GSTopicsView(BrowserView):
      """List of latest topics in the group."""
      def __init__(self, context, request):
          self.context = context
          self.request = request

          self.__author_cache = {}

          self.siteInfo = createObject('groupserver.SiteInfo', 
            context)
          self.groupInfo = createObject('groupserver.GroupInfo', context)

          da = context.zsqlalchemy 
          assert da
          self.messageQuery = queries.MessageQuery(context, da)
          
          try:
              self.start = int(self.request.form.get('start', 0))
          except ValueError, e:
              self.start = 0
          try:
              self.end = int(self.request.form.get('end', 20))
          except ValueError, e:
              self.end = 0
              
          # Swap the start and end, if necessary
          if self.start > self.end:
              tmp = self.end
              self.end = self.start
              self.start = tmp

          messages = self.context.messages
          lists = messages.getProperty('xwf_mailing_list_ids')

          limit = self.get_summary_length()

          self.numTopics = self.messageQuery.topic_count(self.siteInfo.get_id(), lists)
          if self.start > self.numTopics:
              self.start = self.numTopics - limit

          searchTokens = createObject('groupserver.SearchTextTokens', '')
          self.topics = self.messageQuery.topic_search_keyword(
            searchTokens, self.siteInfo.get_id(), 
            [self.groupInfo.get_id()], limit=limit, offset=self.start)

          tIds = [t['topic_id'] for t in self.topics]
          self.topicFiles = self.messageQuery.files_metadata_topic(tIds)
          self.__userPostingInfo = None
          
      @property
      def userPostingInfo(self):
          '''Get the User Posting Info
          
          The reason that I do not assign to a self.userPostingInfo 
          variable is that self.context is a bit weird until *after* 
          "__init__" has run. Ask me not questions I tell you no lies.
          '''
          if self.__userPostingInfo == None:
              g = self.groupInfo.groupObj
              ui = createObject('groupserver.LoggedInUser', self.context)
              upi = getMultiAdapter((g, ui), IGSPostingUser)
              self.__userPostingInfo = upi
          retval = self.__userPostingInfo
          assert IGSPostingUser.providedBy(retval)
          return retval

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
          assert hasattr(self, 'messageQuery'), 'No message query'
          assert hasattr(self, 'groupInfo'), 'No group info'
          if not hasattr(self, 'stickyTopics'):
              stickyTopicsIds = self.groupInfo.get_property('sticky_topics', [])
              topics = filter(lambda t: t!=None, [self.messageQuery.topic(topicId) 
                                                  for topicId in stickyTopicsIds])
              self.stickyTopics = topics
              
          retval =  self.stickyTopics
          assert hasattr(self, 'stickyTopics'), 'Sticky topics not cached'
          return retval

      def get_author(self, userId):
          authorInfo = self.__author_cache.get(userId, None)
          if not authorInfo:
              authorInfo = createObject('groupserver.UserFromId',
                self.context, userId)
              self.__author_cache[authorInfo] = authorInfo
          return authorInfo

      def get_non_sticky_topics(self):
          stickyTopics = self.get_sticky_topics()
          stickyTopicIds = map(lambda t: t['topic_id'], stickyTopics)
          allTopics = self.get_topics()

          r = lambda r: r.replace('/','-').replace('.','-')
          retval = []
          for topic in self.topics:
              t = topic
              authorInfo = self.get_author(t['last_post_user_id'])
              authorD = {
                'exists': authorInfo.url != '#',
                'id': authorInfo.id,
                'name': authorInfo.name,
                'url': authorInfo.url,
              }
              t['last_author'] = authorD

              files = [{'name': f['file_name'],
                        'url': '/r/topic/%s#post-%s' % (f['post_id'], f['post_id']),
                        'icon': r(f['mime_type']),
                       } for f in self.topicFiles 
                       if f['topic_id'] == t['topic_id']]
                       
              t['files'] = files
              if t['topic_id'] not in stickyTopicIds:
                  retval.append(t)
          return retval

      def process_form(self, *args):
          pass

