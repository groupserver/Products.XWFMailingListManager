from zope.interface import Interface
from zope.schema import *

class IMarkupEmail(Interface):
    pass

class IWrapEmail(Interface):
    pass

class IGSMessagesFolder(Interface):
    pass

class IGSTopicView(Interface):
    pass

class IGSPostView(Interface):
    pass

class IGSPostContentProvider(Interface):
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
    # Should really be called "same author" or similar.
    showPhoto = Bool(title=u'Whether to show the photo',
                       description=u"""Determines if the author's photo
                       should be shown.""",
                       required=False,
                       default=True)
    pageTemplateFileName = Text(title=u"Page Template File Name",
                                  description=u"""The name of the ZPT file
                                  that is used to render the post.""",
                                  required=False,
                                  default=u"browser/templates/email.pt")
    groupInfo = Field(title=u"Group Information",
                        description=u"Information about the group",
                        required=True,
                        default=None)
    siteInfo = Field(title=u"Site Information",
                       description=u"Information about the site",
                       required=True, 
                       default=None)
                              
class IGSTopicSummaryContentProvider(Interface):
    """The Groupserver Topic Summary Content Provider Interface
      
      This interface defines the fields that must be set up, normally using
      TAL, before creating a "GSTopicSummaryContentProvider" instance. 
      See the latter for an example."""
    
    topic = Field(title=u"Topic",
                    description=u"The topic to display",
                    required=True, 
                    readonly=False)

    pageTemplateFileName = Text(title=u"Page Template File Name",
                                  description=u"""The name of the ZPT file
                                  that is used to render the post.""",
                                  required=False,
                                  default=u"browser/templates/topicSummary.pt")

    groupInfo = Field(title=u"Group Information",
                        description=u"Information about the group",
                        required=True,
                        default=None)

    siteInfo = Field(title=u"Site Information",
                       description=u"Information about the site",
                       required=True, 
                       default=None)


class IGSTopicIndexContentProvider(Interface):
    """A content provider for the index of posts in a topic"""
    topic = Field(title=u"Topic",
                  description=u"The topic to display",
                  required=True, 
                  readonly=False)
                  
    def get_user_can_post(): #@NoSelf
        """ """
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

class IGSStickyTopicToggleContentProvider(Interface):
    """A content provider for the sticky-topic toggle"""
    topic = Text(title=u"Topic",
                 description=u"The name of the topic to be toggled",
                 required=True)
    topicId = Text(title=u"Topic ID",
                   description=u"The ID of the topic to be toggled",
                   required=True)
    groupInfo = Field(title=u"Group Information",
                     description=u"Information about the group",
                     required=True,
                     default=None)
    siteInfo = Field(title=u"Site Information",
                     description=u"Information about the site",
                     required=True, 
                     default=None)
    pageTemplateFileName = Text(title=u"Page Template File Name",
                                description=u"""The name of the ZPT file
                                that is used to render the form.""",
                                required=False,
                                default=u"browser/templates/toggleStickyTopicForm.pt")

class IGSPostMessage(Interface):
    fromAddress = Choice(title=u'Email From',
      description=u'The email address that you want in the "From" '\
        u'line in the email you send.',
      vocabulary = 'EmailAddressesForLoggedInUser',
      required=True)

    message = Text(title=u'Message',
      description=u'The message you want to post to this topic.',
      required=True)
    
    uploadedFile = Bytes(title=u'Files',
                         description=u'A file you wish to add.',
                         required=False)
      
class IGSStickyTopic(Interface):
    sticky = Bool(title=u'Sticky',
      description=u'Display this topic before all other topics on '\
        u'the Latest Topics page.',
      required=False)

class IGSAddToTopicFields(IGSPostMessage, IGSStickyTopic):
    u'''Fields used on the topic page.'''
    inReplyTo = TextLine(title=u'In Reply To Identifier',
      description=u'The ID of the most recent post to the topic',
      required=True)

class IGSPostMessageNewTopic(IGSPostMessage):
    topic = TextLine(title=u'Topic',
        description=u'The title of the topic. This appears as the '\
          u'subject of the email messages that are sent out.',
        required=True)
    
class IGSPostPrivacyContentProvider(Interface):
    pageTemplateFileName = Text(title=u"Page Template File Name",
        description=u"""The name of the ZPT file
        that is used to render the post.""",
        required=False,
        default=u"browser/templates/postprivacy.pt")

