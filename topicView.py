'''GroupServer-Content View Class
'''
from zope.app.traversing.interfaces import TraversalError
from interfaces import IGSTopicView
from zope.interface import implements
from Products.Five.traversable import Traversable
from zope.app.traversing.interfaces import ITraversable
import Products.GSContent, Products.XWFCore.XWFUtils
import Products.XWFMailingListManager.stickyTopicToggleContentProvider
import queries
import view

class GSTopicView(view.GSPostingInfo, Traversable):
      """View of a single GroupServer Topic"""
      implements(IGSTopicView, ITraversable)
      def __init__(self, context, request):
          self.retval = {}
          self.context = context
          self.request = request
          
          self.siteInfo = Products.GSContent.view.GSSiteInfo( context )
          self.groupInfo = view.GSGroupInfo( context )
          
          self.archive = context.messages
          self.postId = None
          
          self.da = self.context.zsqlalchemy 
          assert self.da, 'No data-adaptor found'
          
      def traverse(self, name, furtherPath):
          #
          # TODO: this would probably be a good spot to check if the
          # postId is valid, and if not redirect to a helpful message
          #
          if not self.postId:
              self.postId = name
          else:
              raise TraversalError, "Post ID was already specified"
          
          return self
          
      def update(self):
          assert hasattr(self, 'postId')
          assert self.postId
          
          result = view.process_form( self.context, self.request )
          if result:
              self.retval.update(result.items())
          result = view.process_post( self.context, self.request )
          if result:
              self.retval.update(result.items())
          
          self.messageQuery = queries.MessageQuery(self.context, self.da)
          self.topicId = self.messageQuery.topic_id_from_post_id(self.postId)
          
          # see if it's a legacy postId, and if so get the correct one
          if not self.topicId:
              self.postId = self.messageQuery.post_id_from_legacy_id(self.postId)
              self.topicId = self.messageQuery.topic_id_from_post_id(self.postId)
              
          self.topic = self.messageQuery.topic_posts(self.topicId)
          assert len(self.topic) >= 1, "No posts in the topic %s" % self.topicId
          self.lastPostId = self.topic[-1]['post_id']
          
      def get_topic(self):
          assert self.topic
          return self.topic
      
      def get_topic_name(self):
          assert self.topic
          retval = self.topic[0]['subject']
          return retval
          
      def get_next_topic(self):
          assert self.messageQuery
          r = self.messageQuery.later_topic(self.topicId)
          if r:
              retval = (r['last_post_id'], r['subject'])
          else:
              retval = (None,None)
          return retval
          
      def get_previous_topic(self):
          assert self.messageQuery
          r = self.messageQuery.earlier_topic(self.topicId)
          if r:
              retval = (r['last_post_id'], r['subject'])
          else:
              retval = (None,None)
          return retval
          
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
