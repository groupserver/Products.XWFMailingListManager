# coding=utf-8
"""The audit-trails component for the storage of ABEL financial docs

CONSTANTS
    SUBSYSTEM: 'groupserver.WebPost'
    UNKNOWN:   '0' (*String*)
    POST:      '1' (*String*)
"""
from pytz import UTC
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape
from base64 import b64decode
from zope.component import createObject
from zope.component.interfaces import IFactory
from zope.interface import implements, implementedBy
from Products.CustomUserFolder.interfaces import IGSUserInfo
from Products.CustomUserFolder.userinfo import userInfo_to_anchor
from Products.GSAuditTrail import IAuditEvent, BasicAuditEvent, \
  AuditQuery, event_id_from_data
from Products.XWFCore.XWFUtils import munge_date

# Create a logger for this audit-trail component
SUBSYSTEM = 'groupserver.WebPost'
import logging
log = logging.getLogger(SUBSYSTEM)

UNKNOWN        = '0'  # Unknown is always "0"
POST           = '1'

class WebPostAuditEventFactory(object):
    """A Factory for web-posting events
    
    DESCRIPTION
        This factory creates events relating to posting to a 
        GroupServer group from the Web
    """
    implements(IFactory)

    title=u'GroupServer Web Post Audit Event Factory'
    description=u'Creates a GroupServer audit event for web posting'

    def __call__(self, context, event_id, code, date,
        userInfo, instanceUserInfo, siteInfo, groupInfo,
        instanceDatum='', supplementaryDatum='', subsystem=''):
        """Create an event
        
        DESCRIPTION
            The factory is called to create user-creation event instances.
            
        ARGUMENTS
            context
                The context in which the user was created.
                
            event_id
                The identifier for the user-creation event.
                
            code
                The code used to determine the type of
                user-creation event that is instantiated.
                
            date
                The date the user was created.
                
            userInfo
                The person who created the user (the staff member).
                
            instanceUserInfo
                The user who was created.
                
            siteInfo
                The site on which the staff member created the user.
                
            groupInfo
                The group where the user was created. Can be None.
                
            instanceDatum
                Data about the event. Can be ''.
                
            supplementaryDatum
                More data about the event. Can be ''.
                
            subsystem
                The subsystem (should be this one).
        RETURNS
            An event, that conforms to the IAuditEvent interface.
            
        SIDE EFFECTS
            None
        """
        assert subsystem == SUBSYSTEM, 'Subsystems do not match'
        
        if (code == POST):
            event = PostEvent(context, event_id, date, 
              userInfo, siteInfo, groupInfo, instanceDatum)
        else:
            # The catch-all
            event = BasicAuditEvent(context, event_id, UNKNOWN, date, 
              userInfo, None, siteInfo, groupInfo, 
              instanceDatum, supplementaryDatum, SUBSYSTEM)
        assert event
        return event
    
    def getInterfaces(self):
        return implementedBy(BasicAuditEvent)

class PostEvent(BasicAuditEvent):
    '''An audit-trail event representing posting a message from the 
      Web.
    '''
    implements(IAuditEvent)

    def __init__(self, context, id, d, userInfo, siteInfo, groupInfo,
      instanceDatum):
        """Create a post event
        
        ARGUMENTS
            Most of the arguments are the same as for the factory,
            except some are skipped. The instanceDatum is the
            identifier of the post.
        """
        BasicAuditEvent.__init__(self, context, id, POST, d, 
          userInfo, None,  siteInfo, groupInfo, instanceDatum, 
          None, SUBSYSTEM)
        
    def __str__(self):
        """Display the event as a string, in such a way that it
        will be useful for the standard Python log.
        """
        retval = u' %s (%s) making a post from the web to the '\
          u'topic "%s" in %s (%s) on %s (%s)' %\
          (self.userInfo.name, self.userInfo.id, 
           self.instanceDatum, 
           self.groupInfo.name, self.groupInfo.id,
           self.siteInfo.name, self.siteInfo.id)
        return retval
    
    @property
    def xhtml(self):
        """Display the event as string, with XHTML markup, in such
        a way that it will be useful for the Web view of audit trails.
        """
        cssClass = u'audit-event groupserver-webpost-event-%s' % \
          self.code
        retval = u'<span class="%s">Made a post from the web to '\
          u'topic %s in <a href="%s/%s">%s</a>' %\
          (self.instanceDatum, 
           self.groupInfo.url, self.groupInfo.name)
        retval = u'%s (%s)' % \
          (retval, munge_date(self.context, self.date))
          
        return retval

class WebPostAuditor(object):
    """An Auditor for ABEL findoc storage
    
    DESCRIPTION
        This auditor creates an audit trail for the ABEL findoc storage
        subsystem. The work of creating the actual events is then
        carried out by "FindocStorageAuditEventFactory".
    """
    def __init__(self, context):
        """Create a user-creation auditor (after the act).
        """
        self.context = context
        self.userInfo = createObject('groupserver.LoggedInUser',context)
        self.siteInfo = createObject('groupserver.SiteInfo', context)
        self.groupInfo = createObject('groupserver.GroupInfo', context)
        
        da = context.zsqlalchemy
        self.queries = AuditQuery(da)

        self.factory = WebPostAuditEventFactory()
        
    def info(self, code, instanceDatum='', supplementaryDatum=''):
        """Log an info event to the audit trail.

        DESCRIPTION
            This method logs an event to the audit trail.
                
        ARGUMENTS
            "code"    The code that identifies the event.
                      
            "instanceDatum"
                      Data about the event.
        
        SIDE EFFECTS
            * Creates an ID for the new event,
            * Writes the instantiated event to the audit-table, and
            * Writes the event to the standard Python log.
        
        RETURNS
            None
        """
        d = datetime.now(UTC)
        eventId = event_id_from_data(self.userInfo, 
          self.userInfo, self.siteInfo, code, instanceDatum,
          supplementaryDatum)
          
        e = self.factory(self.context, eventId, code, d,
          self.userInfo, None, self.siteInfo, self.groupInfo,
          instanceDatum, supplementaryDatum, SUBSYSTEM)
          
        self.queries.store(e)
        log.info(e)

