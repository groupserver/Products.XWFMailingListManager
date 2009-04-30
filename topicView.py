from time import time
from StringIO import StringIO
from zope.component import getMultiAdapter, createObject
from zope.interface import implements
from zope.traversing.interfaces import TraversalError
from interfaces import IGSTopicView, IGSAddToTopicFields
from Products.GSGroupMember.interfaces import IGSPostingUser
from zope.publisher.interfaces import IPublishTraverse
from Products.Five import BrowserView
import Products.GSContent, queries, view, stickyTopicToggleContentProvider
from Products.Five.browser.pagetemplatefile import ZopeTwoPageTemplateFile
from zope.formlib import form
from Products.Five.formlib.formbase import PageForm
from addapost import add_a_post
from Products.GSGroupMember.groupmembership import user_admin_of_group


import logging
log = logging.getLogger('topicView')

class GSTopicTraversal(BrowserView):
    implements(IPublishTraverse)
    def __init__(self, context, request):
        self.context = context
        self.request = request

        self.postId = None
        self.post = None
        
    def publishTraverse(self, request, name):
        #
        # TODO: this would probably be a good spot to check if the
        # postId is valid, and if not redirect to a helpful message
        #
        if not self.postId:
            self.postId = name
        else:
            raise TraversalError, "Post ID was already specified"
        
        return self
          
    def __call__(self):
      return getMultiAdapter((self.context, self.request), name="gstopic")()

class GSTopicView(PageForm):
    """View of a single GroupServer Topic"""
    label = u'Topic View'
    pageTemplateFileName = 'browser/templates/topic.pt'
    template = ZopeTwoPageTemplateFile(pageTemplateFileName)
    form_fields = form.Fields(IGSAddToTopicFields, render_context=False)
    
    implements(IGSTopicView)
    
    def __init__(self, context, request):
        PageForm.__init__(self, context, request)
        assert hasattr(self.context, 'postId')
        self.postId = self.context.postId
        assert self.postId, 'self.postID set to %s' % self.postId
        
        self.siteInfo = createObject('groupserver.SiteInfo', context )
        self.groupInfo = createObject('groupserver.GroupInfo', context)
        self.__userInfo = None
        self.__userPostingInfo = None
        self.__messageQuery = None
        self.__topicId = None
        self.__topic = None
        self.__lastPostId = None
        self.__topicName = None
        self.__nextTopic = None
        self.__previousTopic = None
        self.__stickyTopics = None

        self.__message = None

    def setUpWidgets(self, ignore_request=False):
        self.adapters = {}
        fromAddr = self.userInfo.user.get_verifiedEmailAddresses()[0]
        data = {
          'fromAddress': fromAddr,
          'message':     u'',
          'sticky':      self.topicSticky,
        }
        self.widgets = form.setUpWidgets(
            self.form_fields, self.prefix, self.context,
            self.request, form=self, data=data,
            ignore_request=ignore_request)
        assert self.widgets
        
    @form.action(label=u'Add', failure='handle_action_failure')
    def handle_add(self, action, data):
      if self.__message != data['message']:
          # --=mpj17=-- Formlib sometimes submits twice submits twice
          self.__message = data['message']
          uploadedFiles = [self.request['form.uploadeFile']]
          r = add_a_post(
            groupId=self.groupInfo.id, 
            siteId=self.siteInfo.id, 
            replyToId=self.topic[-1]['post_id'], 
            topic=self.topicName, 
            message=data['message'],
            tags=[], 
            email=data['fromAddress'], 
            uploadedFiles=uploadedFiles,
            context=self.context, 
            request=self.request)
          if r['error']:
              # TODO make a seperate validator for messages that the
              #   web and email subsystems can use to verifiy the
              #   messages before posting them.
              self.status = r['message']
          else:
              self.status = u'<a href="%(id)s#(id)s">%(message)s</a>' % r
      assert self.status
      assert type(self.status) == unicode

    @form.action(label=u'Change', failure='handle_action_failure')
    def handle_add_to_sticky(self,action, data):
        if data['sticky']:
            self.add_topic_to_sticky()
            self.status = u'<cite>%s</cite> has been '\
              u'<strong>added</strong> to the list of sticky '\
              u'topics in %s' % (self.topicName, self.groupInfo.name)
        else:
            self.remove_topic_from_sticky()
            self.status = u'<cite>%s</cite> has been '\
              u'<strong>removed</strong> from the list of sticky '\
              u'topics in %s' % (self.topicName, self.groupInfo.name)
        assert self.status
        assert type(self.status) == unicode
       
    def handle_action_failure(self, action, data, errors):
      if len(errors) == 1:
          self.status = u'<p>There is an error:</p>'
      else:
          self.status = u'<p>There are errors:</p>'

    def add_topic_to_sticky(self):
        group = self.groupInfo.groupObj
        if group.hasProperty('sticky_topics'):
            topics = self.get_sticky_topics()
            if self.topicId not in topics:
                topics.append(self.topicId)
            group.manage_changeProperties(sticky_topics=topics)
        else:
            group.manage_addProperty('sticky_topics', [self.topicId],
                'lines')
        assert group.hasProperty('sticky_topics')

    def remove_topic_from_sticky(self):
        group = self.groupInfo.groupObj
        if group.hasProperty('sticky_topics'):
            topics = list(group.getProperty('sticky_topics'))
            if self.topicId in topics:
                topics.remove(self.topicId)
            group.manage_changeProperties(sticky_topics=topics)
        else:
            group.manage_addProperty('sticky_topics', [], 'lines')
        assert group.hasProperty('sticky_topics')

    @property
    def userInfo(self):
        if self.__userInfo == None:
            self.__userInfo = createObject('groupserver.LoggedInUser', 
              self.context)
        return self.__userInfo
        
    @property
    def userPostingInfo(self):
        if self.__userPostingInfo == None:
            g = self.groupInfo.groupObj
            assert g
            # --=mpj17=-- A Pixie Caramel to anyone who can tell me
            #    why the following line does not work in Zope 2.10.
            #   "Zope Five is screwed" is not sufficient.
            #self.userPostingInfo = IGSPostingUser((g, userInfo))
            self.__userPostingInfo = getMultiAdapter((g, self.userInfo), 
                                                      IGSPostingUser)
        assert self.__userPostingInfo
        return self.__userPostingInfo
        
    @property
    def messageQuery(self):
        if self.__messageQuery == None:
            da = self.context.zsqlalchemy 
            assert da, 'No data-adaptor found'
            self.__messageQuery = \
              queries.MessageQuery(self.context, da)
        assert self.__messageQuery
        return self.__messageQuery

    @property
    def topicId(self):
        if self.__topicId == None:
            self.__topicId = \
              self.messageQuery.topic_id_from_post_id(self.postId)
            if not self.__topicId:
                self.__topicId = \
                  self.topic_id_from_legacy_post_id(self.postId)
        assert self.__topicId != None
        return self.__topicId
        
    def topic_id_from_legacy_post_id(self, legacyPostId):
        p = self.messageQuery.post_id_from_legacy_id(legacyPostId)
        retval = self.messageQuery.topic_id_from_post_id(p)
        assert retval
        return retval
        
    @property
    def topic(self):
        if self.__topic == None:
            self.__topic = self.messageQuery.topic_posts(self.topicId)
        assert type(self.__topic) == list
        assert len(self.__topic) >= 1, \
          "No posts in the topic %s" % self.topicId
        return self.__topic
        
    @property
    def lastPostId(self):
        if self.__lastPostId == None:
            self.__lastPostId = self.topic[-1]['post_id']
        assert self.__lastPostId
        return self.__lastPostId

    @property
    def topicName(self):
        if self.__topicName == None:
            self.__topicName = self.topic[0]['subject']
        assert self.__topicName != None
        return self.__topicName
    
    @property
    def nextTopic(self):
        if self.__nextTopic == None:
            r = self.messageQuery.later_topic(self.topicId)
            if r:
                self.__nextTopic = TopicInfo(r['last_post_id'], r['subject'])
            else:
                self.__nextTopic = TopicInfo(None,None)
        assert self.__nextTopic != None
        return self.__nextTopic
        
    @property
    def previousTopic(self):
        if self.__previousTopic == None:
            r = self.messageQuery.earlier_topic(self.topicId)
            if r:
                self.__previousTopic = TopicInfo(r['last_post_id'], r['subject'])
            else:
                self.__previousTopic = TopicInfo(None,None)
        assert self.__previousTopic
        return self.__previousTopic

    @property
    def topicSticky(self):
        retval = self.topicId in self.groupInfo.get_property('sticky_topics', [])
        assert type(retval) == bool
        return retval

    def get_sticky_topics(self):
        if self.__stickyTopics == None:
            stickyTopicsIds = self.groupInfo.get_property('sticky_topics', [])
            if type(stickyTopicsIds) != list:
                stickyTopicIdIds = [stickyTopicsIds]
            topics = [t for t in [self.messageQuery.topic(topicId) 
                                  for topicId in stickyTopicsIds] if t]
            assert type(topics) == list
            for t in topics:
                assert type(t) == dict
            self.__stickyTopics = topics
        assert self.__stickyTopics != None
        return self.__stickyTopics

    @property
    def userIsAdmin(self):
        return user_admin_of_group(self.userInfo, self.groupInfo)

class TopicInfo(object):
    def __init__(self, topicId, subject):
        self.topicId = topicId
        self.subject = subject

