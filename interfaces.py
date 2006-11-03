import zope.interface, zope.component, zope.publisher.interfaces
import zope.viewlet.interfaces, zope.contentprovider.interfaces 
from zope.schema import *

class IGSMessagesFolder(zope.interface.Interface):
    pass

# <zope-3 weirdness="high">

class IGSPostContentProvider(zope.interface.Interface):
      """The Groupserver Post Content Provider Interface
      
      This interface defines the fields that must be set up, normally using
      TAL, before creating a "GSPostContentProvider" instance. See the
      latter for an example."""
      post = Field(title=u"Email Message Instance",
                   description=u"The email instance to display",
                   required=True, 
                   readonly=False)
      position = Int(title=u"Position of the Post",
                     description=u"""The position of the post in the topic.
                     This is mostly used for determining the background 
                     colour of the post.""",
                     required=False,
                     min=1, default=1)
      topicName = Text(title=u"Title of the Topic",
                       description=u"""The title of the topic.""",
                       required=False,
                       default=u'')
      pageTemplateFileName = Text(title=u"Page Template File Name",
                                  description=u"""The name of the ZPT file
                                  that is used to render the post.""",
                                  required=False,
                                  default=u"browser/templates/email.pt")
                                 
#zope.interface.directlyProvides(IGSPostContentProvider, 
#                                zope.contentprovider.interfaces.ITALNamespaceData)

class IGSTopicIndexContentProvider(zope.interface.Interface):
    """A content provider for the index of posts in a topic"""
    topic = Field(title=u"Topic",
                  description=u"The topic to display",
                  required=True, 
                  readonly=False)

# </zope-3>