# coding=utf-8
from gs.group.base.page import GroupPage

class GSMessagesRedirect(GroupPage):
    def __init__(self, context, request):
        GroupPage.__init__(self, context, request)

    def __call__(self):
        t = self.groupInfo.get_property('group_template', 'standard')
        if t == 'announcement':
            uri = '%s/messages/posts.html' % self.groupInfo.url
        else:
            uri = '%s/messages/topics.html' % self.groupInfo.url
        retval = self.request.RESPONSE.redirect(uri)
        return retval

