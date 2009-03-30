'''GroupServer-Content View Class
'''
import sys, re, datetime, time, types, string
import Products.Five, Globals
import zope.schema
import zope.pagetemplate.pagetemplatefile
import zope.interface, zope.component, zope.publisher.interfaces
import zope.viewlet.interfaces, zope.contentprovider.interfaces 
import Products.PythonScripts.standard
import transaction

from sqlalchemy.exceptions import SQLError
from zope.component import createObject, getMultiAdapter

import DocumentTemplate
import Products.XWFMailingListManager.stickyTopicToggleContentProvider
import queries

from Products.GSGroupMember.interfaces import IGSPostingUser
from Products.XWFCore.XWFUtils import munge_date
import addapost

import logging
log = logging.getLogger('XWFMailingListManager.view')

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
            
            try:
                result = addapost.add_a_post(groupId, siteId, replyToId,
                                             topic, message, tags, email,
                                             uploadedFile, 
                                             context, request)
            except SQLError, e:
                log.error(e.message)
                result['error'] = True
                # --=mpj17=-- Let us hope the following is the case.
                result['message'] = 'The topic already contains the post'
                
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

class GSNewTopicView(Products.Five.BrowserView):
    def __init__(self, context, request):
        self.context = context
        self.request = request
          
        self.siteInfo = createObject('groupserver.SiteInfo', context)
        self.groupInfo = createObject('groupserver.GroupInfo', context)
          
        self.retval = {}
          
    def update(self):
        result = process_post( self.context, self.request )
        if result:
            self.retval.update(result.items())

        userInfo = createObject('groupserver.LoggedInUser', self.context)
        g = self.groupInfo.groupObj
        self.userPostingInfo = getMultiAdapter((g, userInfo), 
                                               IGSPostingUser)

