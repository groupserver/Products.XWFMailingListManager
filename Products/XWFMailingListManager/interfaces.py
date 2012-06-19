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
    
class IGSPostPrivacyContentProvider(Interface):
    pageTemplateFileName = Text(title=u"Page Template File Name",
        description=u"""The name of the ZPT file
        that is used to render the post.""",
        required=False,
        default=u"browser/templates/postprivacy.pt")

