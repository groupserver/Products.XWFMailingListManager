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
         
          self.archive = context.messages
          self.emailId = request.form.get('id', None)

          da = context.zsqlalchemy 
          assert da, 'No data-adaptor found'
          
          self.messageQuery = queries.MessageQuery(context, da)
          self.topicId = self.messageQuery.topic_id_from_post_id(self.emailId)
          
      def update(self):
          print '\nStart update'
          result = view.process_form( self.context, self.request )
          if result:
              self.retval.update(result.items())
          result = view.process_post( self.context, self.request )
          if result:
              self.retval.update(result.items())
          self.topic = self.messageQuery.topic_posts(self.topicId)
          self.lastPostId = self.topic[-1]['post_id']
          print 'End update\n'
          
      def get_topic(self):
          assert self.topic
          return self.topic
      
      def get_topic_name(self):
          assert self.topic
          retval = self.topic[0]['subject']
          return retval
          
      def get_next_topic(self):
          assert self.messageQuery
          r = self.messageQuery.next_topic(self.topicId)
          if r:
              retval = (r['last_post_id'], r['subject'])
          else:
              retval = (None,None)
          return retval
          
      def get_previous_topic(self):
          assert self.messageQuery
          r = self.messageQuery.previous_topic(self.topicId)
          if r:
              retval = (r['last_post_id'], r['subject'])
          else:
              retval = (None,None)
          return retval
          
      def get_sticky_topics(self):
          retval = []


          return retval
          
          
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
