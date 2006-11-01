import zope.interface, zope.component, zope.publisher.interfaces
import zope.viewlet.interfaces, zope.contentprovider.interfaces 

class IGSMessagesFolder(zope.interface.Interface):
    pass

# <zope-3 weirdness="high">

class IGSPostContentProvider(zope.interface.Interface):
      """The Groupserver Post Content Provider Interface
      
      This interface defines the fields that must be set up, normally using
      TAL, before creating a "GSPostContentProvider" instance. See the
      latter for an example."""
      post = zope.schema.Field(title=u"Email Message Instance",
                               description=u"The email instance to display",
                               required=True, 
                               readonly=False)
      position = zope.schema.Int(title=u"Position of the Post",
                                 description=u"""The position of the post
                                 in the topic. This is mostly used for
                                 determining the background colour of the
                                 post.""",
                                 required=False,
                                 min=1, default=1)
                                 
#zope.interface.directlyProvides(IGSPostContentProvider, 
#                                zope.contentprovider.interfaces.ITALNamespaceData)

class IGSTopicIndexContentProvider(zope.interface.Interface):
    """A content provider for the index of posts in a topic"""
    topic = zope.schema.Field(title=u"Topic",
                               description=u"The topic to display",
                               required=True, 
                               readonly=False)

# </zope-3>