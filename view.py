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
import addapost

def process_post( context, request ):
    form = request.form
    result = {}
    if form.has_key('submitted'):
        if ((form['model'] == 'post') 
            and (form['instance'] == 'addPost_pragmatic')):
            assert form.has_key('groupId')
            assert form.has_key('siteId')
            assert form.has_key('replyToId')
            assert form.has_key('topic')
            assert form.has_key('message')
            assert form.has_key('tags')
            assert form.has_key('email')
            assert form.has_key('file')

            # --=mpj17=-- Do not, under *A*N*Y* circumstances, 
            #  strip the file.
            fields = ['replyToId', 'topic', 'message', 'tags', 'email']
            for field in fields:
                # No really: do not strip the file.
                try:
                    form[field] = form[field].strip()
                except AttributeError:
                    pass
                    
            groupId = form.get('groupId')
            siteId = form.get('siteId')
            replyToId = form.get('replyToId', '')
            topic = form.get('topic', '')
            message = form.get('message', '')
            tags = form.get('tags', '')
            email = form.get('email', '')
            uploadedFile = form.get('file', '')
            result = addapost.add_a_post(groupId, siteId, replyToId,
                                         topic, message, tags, email,
                                         uploadedFile, 
                                         context, request)
        else:
            result['error'] = False
            result['message'] = ''

        assert result.has_key('error')
        assert result.has_key('message')
        assert result['message'].split
            
        result['form'] = form

        return result

def process_form( context, request ):
    form = request.form
    result = {}
    if form.has_key('submitted'):
        model = form['model']
        instance = form['instance']
        
        oldScripts = context.Scripts.forms
        if hasattr(oldScripts, model):
            modelDir = getattr(oldScripts, model)
            if hasattr(modelDir, instance):
                script = getattr(modelDir, instance)
                return script()
            else:
                m = """<p>Could not find the instance
                       <code>%s</code></p>.""" % instance
                result['error'] = True
                result['message'] = m
        else:
            m = """<p>Could not find the model 
                   <code>%s</code></p>.""" % model
            result['error'] = True
            result['message'] = m
        assert result.has_key('error')
        assert result.has_key('message')
        assert result['message'].split
    
    result['form'] = form
    return result

class GSGroupInfo:
    def __init__(self, context):
        assert context
        self.context = context
        self.groupObj = self.__get_group_object()
        self.siteInfo = Products.GSContent.view.GSSiteInfo( context )

    def __get_group_object(self):
        assert self.context
        retval = self.context
        markerAttr = 'is_group'
        while retval:
            try:
                if getattr(retval.aq_inner.aq_explicit, markerAttr, False):
                    break
                else:
                    retval = retval.aq_parent
            except:
                break
        retval = retval.aq_inner.aq_explicit
        assert retval 
        assert hasattr(retval, markerAttr)
        assert getattr(retval, markerAttr)
        return retval

    def get_name(self):
        assert self.groupObj
        retval = self.groupObj.title_or_id()
        return retval
        
    def get_id(self):
        assert self.groupObj
        retval = self.groupObj.getId()
        return retval
        
    def get_url(self):
        assert self.groupObj
        assert self.siteInfo
        siteURL = self.siteInfo.get_url()
        retval = '%s/groups/%s' % (siteURL, self.get_id())
        return retval
        
    def get_property(self, propertyId, default=None):
        assert self.groupObj
        retval = self.groupObj.getProperty(propertyId, default)
        return retval

class GSPostingInfo:
      def get_user_can_post(self, reasonNeeded=False):
        # Assume the user can post
        retval = (('', 1), True)

        user = self.request.AUTHENTICATED_USER
        groupList = getattr(self.context.ListManager.aq_explicit, 
                            self.groupInfo.get_id())
        assert user
        userRoles = user.getRolesInContext(self.groupInfo.groupObj)
        if user.getId() == None:
            m = '''Only members who are logged in can post, and you
            are not logged in.'''
            retval = ((m, 2), False)
        elif 'GroupMember' not in userRoles:
            # Not a group member
            m = '''Only members of this group can post, and you are not 
            a member.'''
            retval = ((m, 3), False)
        elif groupList.is_senderBlocked(user.getId())[0]:
            senderLimit = groupList.getValueFor('senderlimit')
            senderInterval = groupList.getValueFor('senderinterval')

            secInDay = 86400
            secInHour = 3600
            day = not(senderInterval % secInDay)
            duration = senderInterval/(day and secInDay or secInHour)
            plural = duration > 1
            dayOrHour = day and 'day' or 'hour'
            dayOrHour = dayOrHour + ((plural and 's') or '')
            interval = '%d %s' % (duration, dayOrHour)
            
            timezone = self.context.Scripts.get.option('timezone')
            t = DateTime.DateTime(int(groupList.is_senderBlocked(user.getId())[1]))
            postingDate = t.toZone(timezone).strftime('%F %H:%M')
            m = """Members may only send %d messages every %s, and 
            you have exceeded this limit; you may post again 
            at %s."""  % (senderLimit, interval, postingDate)
            retval = ((m, 4), False)
        else:            
            # ...there is a local reason that allows the user to post
            retval = self.get_user_can_post_local(True)

        if not reasonNeeded:
            retval = retval[1]
        return retval

      def get_user_can_post_local(self, reasonNeeded=False):
        assert self.context

        # Assume the user can post
        retval = (('', 1), True)
        
        try:
            localScripts = self.context.LocalScripts
        except:
            localScripts = None
            
        if (localScripts
            and hasattr(localScripts, 'get')
            and hasattr(localScripts.get, 'userCanPostToGroup')):
            retval = localScripts.get.userCanPostToGroup(True)

        if not reasonNeeded:
            retval = retval[1]
        return retval
        
class GSNewTopicView(Products.Five.BrowserView, GSPostingInfo):
      def __init__(self, context, request):
          self.context = context
          self.request = request
          
          self.siteInfo = Products.GSContent.view.GSSiteInfo( context )
          self.groupInfo = GSGroupInfo( context )

          self.retval = {}
          
      def update(self):
          result = process_post( self.context, self.request )
          if result:
              self.retval.update(result.items())


class GSBaseMessageView(Products.Five.BrowserView):
      def __init__(self, context, request, dummy=False):
          self.siteInfo = Products.GSContent.view.GSSiteInfo( context )
          self.groupInfo = GSGroupInfo( context )
          
          self.context = context
          self.request = request

          self.set_archive(context.messages)
          self.set_emailId(request.form.get('id', None))
          self.init_email()
          if not dummy:
              self.init_topic()
      
      def set_archive(self, archive):
          """Set the email message archive to "archive"."""
          assert archive
          self.archive = archive
          assert self.archive
      
      def get_archive(self):
          """Get the email message archive."""
          assert self.archive
          return self.archive
      
      # emailId
      def set_emailId(self, emailId):
          assert emailId
          self.emailId = emailId
          assert self.emailId
      
      def get_emailId(self):
          return self.emailId
      
      # email
      def init_email(self):
          # Missing error-handling
          assert self.emailId
          self.email = None
          self.email = self.archive.get_email(self.emailId)
          assert self.email
      
      def get_email(self):
          retval = self.email
          assert retval
          return retval

      # topic
      def init_topic(self):
          assert self.emailId
          assert self.archive
          assert self.email
          
          # Mostly taken from XWFVirtualMailingListArchive.view_email
          
          query = {'compressedTopic': '%s' % self.email.compressedSubject}
          result = self.archive.find_email(query)
          
          query = {}
          resultSet = self.archive.find_email(query)
          sortFields = (('mailSubject', 'nocase'),
                        ('mailDate', 'cmp','desc'))
          result = DocumentTemplate.sequence.sort(resultSet,
                                                   sortFields)
          assert result
          r = [p.getObject() for p in result]
          cs = self.email.compressedSubject.lower()
          self.topic = [p for p in r 
                        if p['compressedSubject'].lower() == cs]
          self.topic.reverse()
          #self.topic = map(lambda x: x.getObject(), result)
          #self.topic.sort(self.post_date_storter)
          
          assert self.topic
          assert self.topic.append
          assert len(self.topic) > 0
          
      def get_topic(self):
          assert self.topic
          assert self.topic.append
          return self.topic
      
      def get_topic_name(self):
          assert self.email
          
          retval = self.email['mailSubject']
          
          return retval
          
          
        
class GSPostView(GSBaseMessageView):
      """A view of a single post in a topic.
      
      A view of a single post shares much in common with a view of an 
      entire topic, which is why it inherits from "GSTopicView". The main
      semantic difference is the ID specifies post to display, rather than
      the first post in the topic.   
      """
      # Next and previous email messages
      def get_previous_email(self):
          assert self.topic
          assert self.email in self.topic
          
          retval = None
          
          emailPos = self.topic.index(self.email)
          previousPos = emailPos - 1
          
          if previousPos >= 0:
              retval = self.topic[previousPos]
          return retval
          
      def get_next_email(self):
          assert self.topic
          assert self.email in self.topic
          
          retval = None
          
          emailPos = self.topic.index(self.email)
          nextPos = emailPos + 1
          
          if nextPos < len(self.topic):
              retval = self.topic[nextPos]
          return retval

      def get_first_email(self):
          assert self.topic
          retval = self.topic[0]
          return retval
          
      def get_last_email(self):
          assert self.topic
          retval = self.topic[-1]
          return retval

class GSCurrentUserInfo:
    """Information about the current user"""
    zope.interface.implements( IGSUserInfo )
    
    def __init__(self):
        pass
    
    def exists(self):
        return True
    def get_id(self):
        pass
    def get_image(self):
        pass
    def get_real_names(self, preferredNameOnly=True):
        pass
          
Globals.InitializeClass( GSPostView )
