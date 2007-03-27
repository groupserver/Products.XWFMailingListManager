'''GroupServer-Content View of a Single Post
'''
from zope.app.traversing.interfaces import TraversalError
from interfaces import IGSPostView
from zope.interface import implements
from Products.Five.traversable import Traversable
from zope.app.traversing.interfaces import ITraversable
import Products.GSContent, Products.XWFCore.XWFUtils
import Products.XWFMailingListManager.stickyTopicToggleContentProvider
import queries
import view

class GSPostView(Traversable):
      """A view of a single post.
      
      A view of a single post shares much in common with a view of an 
      entire topic, which is why it inherits from "GSTopicView". The main
      semantic difference is the ID specifies post to display, rather than
      the first post in the topic.   
      """
      implements(IGSPostView, ITraversable)
      def __init__(self, context, request):
          self.context = context
          self.request = request

          self.siteInfo = Products.GSContent.view.GSSiteInfo( context )
          self.groupInfo = view.GSGroupInfo( context )
          
          self.archive = context.messages
          
          self.postId = None

          da = self.context.zsqlalchemy 
          assert da, 'No data-adaptor found'
          self.messageQuery = queries.MessageQuery(self.context, da)

          
      def traverse(self, name, furtherPath):
          uri = ''
          print
          print 'Wibble'
          if not self.postId:
              self.postId = name
              if not self.messageQuery.post(self.postId):
                  uri = '/r/post-not-found?id=%s' % self.postId
              else: # No post found
                  self.update()
          else: # No ID set
              uri = '/r/post-no-id'
          if uri:
              print uri
              return self.request.RESPONSE.redirect(uri)
          else:            
              return self
      
      def update(self):
          if (self.postId):
              self.post = self.messageQuery.post(self.postId)
              assert self.post, 'No post found'
              self.relatedPosts = self.messageQuery.topic_post_navigation(self.postId)
              
      def get_topic_title(self):
          assert hasattr(self, 'post')
          retval = self.post and self.post['subject'] or ''
          return retval
          
      def get_previous_post(self):
          assert hasattr(self, 'relatedPosts')
          assert self.relatedPosts.has_key('previous_post_id')
          return self.relatedPosts['previous_post_id']
                    
      def get_next_post(self):
          assert hasattr(self, 'relatedPosts')
          assert self.relatedPosts.has_key('next_post_id')
          return self.relatedPosts['next_post_id']
          
      def get_first_post(self):
          assert hasattr(self, 'relatedPosts')
          assert self.relatedPosts.has_key('first_post_id')
          return self.relatedPosts['first_post_id']
          
      def get_last_post(self):
          assert hasattr(self, 'relatedPosts')
          assert self.relatedPosts.has_key('last_post_id')
          return self.relatedPosts['last_post_id']
          
      def get_post(self):
          assert hasattr(self, 'post')
          return self.post
          
