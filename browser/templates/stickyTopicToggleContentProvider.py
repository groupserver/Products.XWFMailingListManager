from zope.pagetemplate.pagetemplatefile import PageTemplateFile
from zope.interface import Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from zope.contentprovider.interfaces import UpdateNotCalled, IContentProvider
from zope.component import adapts, provideAdapter
from zope.interface import implements

from interfaces import IGSStickyTopicToggleContentProvider

class GSStickyTopicToggleContentProvider(object):
    """GroupServer Post Message Content Provider
    """

    implements( IGSStickyTopicToggleContentProvider )
    adapts(Interface, IDefaultBrowserLayer, Interface)
      
    def __init__(self, context, request, view):
        self.__parent = view
        self.__updated = False
        self.context = context
        self.request = request
        self.view = view
          
    def update(self):
        self.__updated = True
          
        stickyTopics = self.view.get_sticky_topics()
        stickyTopicIds = [topic['topic_id'] for topic in stickyTopics]
        # Add or remove the topic.
        self.add = self.topicId not in stickyTopicIds
          
    def render(self):
        if not self.__updated:
            raise UpdateNotCalled
        VPTF = PageTemplateFile
        self.pageTemplate = VPTF(self.pageTemplateFileName)

        addOrRemove = self.add and 'add' or 'remove'
        return self.pageTemplate(instance=addOrRemove,
                                   add=self.add,
                                   groupId=self.groupInfo.get_id(),
                                   siteId=self.siteInfo.get_id(),
                                   topicId=self.view.topicId)
          
    #########################################
    # Non standard methods below this point #
    #########################################

provideAdapter(GSStickyTopicToggleContentProvider, 
               provides=IContentProvider,
               name="groupserver.StickyTopicToggle")
