# coding=utf-8
"""The audit-trails component for the handling of email bounces

CONSTANTS
    SUBSYSTEM: 'groupserver.BounceHandling'
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
from Products.GSAuditTrail import IAuditEvent, BasicAuditEvent, \
  AuditQuery, event_id_from_data
from Products.XWFCore.XWFUtils import munge_date
from Products.GSGroup.groupInfo import groupInfo_to_anchor

# Create a logger for this audit-trail component
SUBSYSTEM = 'groupserver.BounceHandling'
import logging
log = logging.getLogger(SUBSYSTEM)

UNKNOWN        = '0'  # Unknown is always "0"
BOUNCE         = '1'
DISABLE        = '2'

class BounceHandlingAuditEventFactory(object):
    """A Factory for bounce-handling events
    
    DESCRIPTION
        This factory creates events relating to email bounces
    """
    implements(IFactory)

    title=u'GroupServer Bounce Handling Audit Event Factory'
    description=u'Creates a GroupServer audit event for email bounce handling'

    def __call__(self, context, event_id, code, date,
        userInfo, instanceUserInfo, siteInfo, groupInfo,
        instanceDatum='', supplementaryDatum='', subsystem=''):
        
        assert subsystem == SUBSYSTEM, 'Subsystems do not match'
        
        if (code == BOUNCE):
            event = BounceEvent(context, event_id, date, 
              instanceUserInfo, siteInfo, groupInfo, instanceDatum)
        elif (code == DISABLE):
            event = DisableEvent(context, event_id, date, 
              instanceUserInfo, siteInfo, groupInfo, instanceDatum, 
              supplementaryDatum)
        else:
            # The catch-all
            event = BasicAuditEvent(context, event_id, UNKNOWN, date, 
              userInfo, None, siteInfo, groupInfo, 
              instanceDatum, supplementaryDatum, SUBSYSTEM)
        assert event
        return event
    
    def getInterfaces(self):
        return implementedBy(BasicAuditEvent)

class BounceEvent(BasicAuditEvent):
    ''' An audit-trail event representing an email-bounce.
    '''
    implements(IAuditEvent)

    def __init__(self, context, id, d, userInfo, siteInfo, 
                 groupInfo, instanceDatum):
        BasicAuditEvent.__init__(self, context, id, BOUNCE, d, 
          None, userInfo, siteInfo, groupInfo, instanceDatum, 
          None, SUBSYSTEM)
        
    def __str__(self):
        """Display the event as a string, in such a way that it
        will be useful for the standard Python log.
        """
        retval = u'Bounce detected for %s (%s) in group %s (%s) '\
          u'on site %s (%s) for email address <%s>' %\
          (self.instanceUserInfo.name, self.instanceUserInfo.id, 
           self.groupInfo.name, self.groupInfo.id,
           self.siteInfo.name, self.siteInfo.id,
           self.instanceDatum, )
        return retval.encode('ascii', 'ignore')
    
    @property
    def xhtml(self):
        """Display the event as string, with XHTML markup, in such
        a way that it will be useful for the Web view of audit trails.
        """
        cssClass = u'audit-event groupserver-bounce-event-%s' % \
          self.code
        retval = u'<span class="%s">Email delivery from %s to '\
          u'<code class="email">%s</code> failed' %\
          (cssClass, groupInfo_to_anchor(self.groupInfo), 
           self.instanceDatum)
        retval = u'%s (%s)' % \
          (retval, munge_date(self.context, self.date))
        return retval

class DisableEvent(BasicAuditEvent):
    ''' An audit-trail event representing the system disabling
        an email address.
    '''
    implements(IAuditEvent)

    def __init__(self, context, id, d, userInfo, siteInfo, groupInfo,
                 instanceDatum, supplementaryDatum):
        BasicAuditEvent.__init__(self, context, id, DISABLE, d, 
          None, userInfo, siteInfo, groupInfo, instanceDatum, 
          supplementaryDatum, SUBSYSTEM)
        self.__numBounceDays = self.__numDaysChecked = None
    
    @property
    def numBounceDays(self):
        if self.__numBounceDays == None:
            self.__numBounceDays = \
              int(self.supplementaryDatum.split(';')[0])
        return self.__numBounceDays
    
    @property
    def numDaysChecked(self):
        if self.__numDaysChecked == None:
            self.__numDaysChecked = \
              int(self.supplementaryDatum.split(';')[1])
        return self.__numDaysChecked
        
    def __str__(self):
        """ Display the event as a string, in such a way that it
            will be useful for the standard Python log.
        """
        retval = u'Disabled address <%s> for %s (%s). (Detected '\
          u'%d bounces on unique days in the last %d days.)' %\
          (self.instanceDatum, self.instanceUserInfo.name, 
           self.instanceUserInfo.id, self.numBounceDays, self.numDaysChecked)
        return retval.encode('ascii', 'ignore')
    
    @property
    def xhtml(self):
        """ Display the event as string, with XHTML markup, in such
            a way that it will be useful for the Web view of audit trails.
        """
        cssClass = u'audit-event groupserver-bounce-event-%s' % \
          self.code
        retval = u'<span class="%s">Email address <code class="email">%s</code> '\
          u'disabled after deliveries failed on %d different days in the last %d days.' %\
          (cssClass, self.instanceDatum, self.numBounceDays, self.numDaysChecked)
        retval = u'%s (%s)' % \
          (retval, munge_date(self.context, self.date))
        return retval

class BounceHandlingAuditor(object):
    """An Auditor for GroupServer 
    
    DESCRIPTION
        This auditor creates an audit trail for the handling of
        email bounces. The work of creating the actual events is 
        then carried out by "BounceHandlingAuditEventFactory".
    """
    def __init__(self, context, userInfo, groupInfo, siteInfo):
        """Create a bounce-handling auditor (after the act).
        """
        self.context = context
        self.userInfo = userInfo
        self.groupInfo = groupInfo
        self.siteInfo = siteInfo
        
        self.queries = AuditQuery()

        self.factory = BounceHandlingAuditEventFactory()
        
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
          None, self.userInfo, self.siteInfo, self.groupInfo,
          instanceDatum, supplementaryDatum, SUBSYSTEM)
          
        self.queries.store(e)
        log.info(e)
        
