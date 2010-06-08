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


# --=mpj17=-- TODO: Go through here with the view of throwing stuff
#   out. Who knows what is still required.

def process_post( context, request ):
    form = request.form
    result = {}
    if form.has_key('submitted'):
        if ((form['model'] == 'post') 
            and (form['instance'] == 'addPost_pragmatic')):
            # --=mpj17=-- multiple files.
            keys = ('groupId', 'siteId', 'replyToId', 'topic', \
              'message', 'tags', 'email', 'files')
            for key in keys:
                assert form.has_key(key), '%s not in form' % key

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
            # --=mpj17=-- multiple files.
            uploadedFiles = form.get('files', [])
            if type(uploadedFiles) != list:
                uploadedFiles = [uploadedFiles]
            try:
                result = addapost.add_a_post(groupId, siteId, replyToId,
                                             topic, message, tags, email,
                                             uploadedFiles, 
                                             context, request)
            except SQLError, e:
                log.error(e)
                result['error'] = True
                # --=mpj17=-- Let us hope the following is the case.
                result['message'] = 'The topic already contains the post'
                
        else:
            m = "<p>Could not find the model <code>%s</code>.</p>" % form['model']
            result['error'] = True
            result['message'] = m

        assert result.has_key('error')
        assert result.has_key('message')
        assert type(result['message']) in (unicode, str)
            
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

