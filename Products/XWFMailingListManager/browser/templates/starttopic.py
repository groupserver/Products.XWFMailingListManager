# coding=utf-8
from zope.component import getMultiAdapter, createObject
from zope.traversing.interfaces import TraversalError
from zope.publisher.interfaces import IPublishTraverse
from zope.formlib import form
from zope.app.form import CustomWidgetFactory
from zope.app.form.browser import ListSequenceWidget, FileWidget
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ZopeTwoPageTemplateFile
from Products.Five.formlib.formbase import PageForm
from Products.GSGroupMember.interfaces import IGSPostingUser
from Products.GSGroupMember.groupmembership import user_admin_of_group
from queries import MessageQuery
from interfaces import IGSPostMessageNewTopic
from addapost import add_a_post


class MyFileWidget(FileWidget):
    def _toFieldValue(self, input):
        #--=mpj17=-- Lookie! A hack!
        return self.context.missing_value

class GSStartANewTopicView(PageForm):
    """View of a single GroupServer Topic"""
    label = u'Start a New Topic'
    pageTemplateFileName = 'browser/templates/newTopic.pt'
    template = ZopeTwoPageTemplateFile(pageTemplateFileName)
    form_fields = form.Fields(IGSPostMessageNewTopic, render_context=False)
    
    def __init__(self, context, request):
        PageForm.__init__(self, context, request)

        self.siteInfo = createObject('groupserver.SiteInfo', context )
        self.groupInfo = createObject('groupserver.GroupInfo', context)
        self.__userInfo = self.__userPostingInfo = self.__message = None
        cw = CustomWidgetFactory(MyFileWidget)
        self.form_fields['uploadedFile'].custom_widget = cw

    def setUpWidgets(self, ignore_request=True):
        self.adapters = {}
        if self.userInfo.anonymous:
            fromAddr = ''
        else:
            fromAddr = self.userInfo.user.get_defaultDeliveryEmailAddresses()[0]
        data = {
          'fromAddress': fromAddr,
          'message':     u'',
          'sticky':      False, # New topics cannot be sticky
        }
        self.widgets = form.setUpWidgets(
            self.form_fields, self.prefix, self.context,
            self.request, form=self, data=data,
            ignore_request=ignore_request)
        assert self.widgets
        
    @form.action(label=u'Start', failure='handle_action_failure')
    def handle_add(self, action, data):
      if self.__message != data['message']:
          # --=mpj17=-- Formlib sometimes submits twice submits twice
          self.__message = data['message']
          uploadedFiles = [self.request[k] 
                           for k in self.request.form 
                           if (('form.uploadedFile' in k) and 
                                self.request[k])]
          r = add_a_post(
            groupId=self.groupInfo.id, 
            siteId=self.siteInfo.id, 
            replyToId='', 
            topic=data['topic'], 
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

    def handle_action_failure(self, action, data, errors):
      if len(errors) == 1:
          self.status = u'<p>There is an error:</p>'
      else:
          self.status = u'<p>There are errors:</p>'
      assert type(self.status) == unicode

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

