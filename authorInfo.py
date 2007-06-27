import zope.interface
import zope.interface 
from zope.interface import implements, implementedBy
from zope.component import adapts, createObject
from zope.app.folder.interfaces import IFolder
from zope.component.interfaces import IFactory
from interfaces import IGSAuthorInfo
from Products.XWFCore.XWFUtils import get_user, get_user_realnames

class GSAuthorInfoFactory(object):
    implements(IFactory)
    
    title = u'GroupServer Author Info Factory'
    descripton = u'Create a new GroupServer author information instance'
    
    def __call__(self, context, authorId):
        retval = None
        retval = GSAuthorInfo(context, authorId)
        return retval
        
    def getInterfaces(self):
        retval = implementedBy(GSAuthorInfo)
        assert retval
        return retval
        
    #########################################
    # Non-Standard methods below this point #
    #########################################

class GSAuthorInfo(object):
    implements( IGSAuthorInfo )
    adapts( IFolder )
    
    def __init__(self, context, authorId):
        self.context = context
        self.authorId = authorId
        self.author = get_user(self.context, authorId)

    def user_authored(self, userId):
        return userId == self.authorId

    def exists(self):
        assert hasattr(self, 'author')
        return self.author and True or False
    
    def get_id(self):
        return self.authorId

    def get_image(self):
        retval = None
        if self.exists():
            retval = self.author.get_image()
        return retval
          
    def get_realnames(self):
        retval = get_user_realnames( self.author, self.authorId )
        return retval

    def get_url(self):
        retval = '/contacts/%s' % self.authorId
        return retval

