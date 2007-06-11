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

from zope.component import createObject

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
        else: # Not posting
            model = form['model']
            instance = form['instance']

            localScripts = context.LocalScripts.forms  
            oldScripts = context.Scripts.forms
            
            modelDir = getattr(localScripts, model, 
                                getattr(oldScripts, model, None))
            if modelDir:
                assert hasattr(modelDir, model)
                if hasattr(modelDir, instance):
                    script = getattr(modelDir, instance)
                    assert script
                    retval = script()
                    return retval
                else:
                    m = """<p>Could not find the instance
                            <code>%s</code> in the model
                            <code>%s</code>.</p>""" % (instance, model)
                    result['error'] = True
                    result['message'] = m
            else:
                m = """<p>Could not find the model 
                        <code>%s</code>.</p>""" % model
                result['error'] = True
                result['message'] = m

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
            m = """You have reached the posting limit of %d messages 
            every %s; you may post again  at %s."""  % (senderLimit, 
              interval, postingDate)
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
          self.groupInfo = createObject('groupserver.GroupInfo', context)
          
          self.retval = {}
          
      def update(self):
          result = process_post( self.context, self.request )
          if result:
              self.retval.update(result.items())

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
          
#Globals.InitializeClass( GSPostView )
