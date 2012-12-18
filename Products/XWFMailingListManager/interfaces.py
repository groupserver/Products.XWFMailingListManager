# coding=utf-8
from zope.interface import Interface
from zope.schema import Bool, Bytes, Choice, Field, Int, Text, TextLine 

class IGSMessagesFolder(Interface):
    pass

class IGSTopicView(Interface):
    pass

class IGSPostView(Interface):
    pass
                              
class IGSPostMessageContentProvider(Interface):
    """A content provider for the "Add to Topic" and "Start Topic" forms"""
    startNew = Bool(title=u'Start a New Topic',
                    description=u'Set to "True" if a new topic is started',
                    required=False,
                    default=True)
    topic = Text(title=u"Topic",
                 description=u"The topic that the new post is added to",
                 required=False, 
                 default=u'Enter your new topic here')
    groupInfo = Field(title=u"Group Information",
                     description=u"Information about the group",
                     required=True,
                     default=None)
    siteInfo = Field(title=u"Site Information",
                     description=u"Information about the site",
                     required=True, 
                     default=None)
    replyToId = Text(title=u'Reply-To Post Identifier',
                     description=u'Used when adding to a topic',
                     required=False,
                     default=u'')
    pageTemplateFileName = Text(title=u"Page Template File Name",
                                description=u"""The name of the ZPT file
                                that is used to render the post.""",
                                required=False,
                                default=u"browser/templates/postMessage.pt")
