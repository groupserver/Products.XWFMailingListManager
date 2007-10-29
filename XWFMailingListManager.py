# Copyright IOPEN Technologies Ltd., 2003
# richard@iopen.net
#
# For details of the license, please see LICENSE.
#
# You MUST follow the rules in README_STYLE before checking in code
# to the head. Code which does not follow the rules will be rejected.  
#
from AccessControl import ClassSecurityInfo

from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Globals import InitializeClass
from OFS.Folder import Folder

# TODO: once catalog is completely removed, we can remove XWFMetadataProvider too
from Products.XWFCore.XWFMetadataProvider import XWFMetadataProvider
import DateTime

import os, time

MAILDROP_SPOOL = '/tmp/mailboxer_spool2'

class Record:
    pass

class XWFMailingListManager(Folder, XWFMetadataProvider):
    """ A searchable, self indexing mailing list manager.

    """
    security = ClassSecurityInfo()
    security.setPermissionDefault('View', ('Manager',))
    
    meta_type = 'XWF Mailing List Manager'
    version = 0.99
    
    manage_options = Folder.manage_options + \
                     ({'label': 'Configure',
                       'action': 'manage_configure'},)
    
    manage_configure = PageTemplateFile('management/main.zpt',
                                        globals(),
                                        __name__='manage_main')
    
    archive_options = ['not archived', 'plain text', 'with attachments']
    
    id_namespace = 'http://xwft.org/ns/mailinglistmanager'
    _properties = (
        {'id':'title', 'type':'string', 'mode':'w'},
        {'id':'maillist', 'type':'lines', 'mode':'wd'},
        {'id':'disabled', 'type':'lines', 'mode':'wd'},
        {'id':'moderator', 'type':'lines', 'mode':'wd'},
        {'id':'moderatedlist', 'type':'lines', 'mode':'wd'},
        {'id':'mailoptions', 'type':'lines', 'mode':'wd'},
        {'id':'returnpath','type':'string', 'mode':'wd'},
        {'id':'moderated', 'type':'boolean', 'mode':'wd'},
        {'id':'unclosed','type':'boolean','mode':'wd'},
        {'id':'plainmail', 'type':'boolean', 'mode':'wd'},
        {'id':'keepdate', 'type':'boolean', 'mode':'wd'},
        {'id':'storage', 'type':'string', 'mode':'wd'},
        {'id':'archived', 'type':'selection','mode':'wd',
                      'select_variable':'archive_options'},
        {'id':'subscribe', 'type':'string', 'mode':'wd'},
        {'id':'unsubscribe','type':'string', 'mode':'wd'},
        {'id':'mtahosts', 'type':'tokens', 'mode':'wd'},
        {'id':'spamlist', 'type':'lines', 'mode':'wd'},
        {'id':'atmask', 'type':'string', 'mode':'wd'},
        {'id':'sniplist', 'type':'lines', 'mode':'wd'},
        {'id':'catalog', 'type':'string', 'mode':'wd'},
        {'id':'xmailer', 'type':'string', 'mode':'wd'},
        {'id':'headers', 'type':'string', 'mode':'wd'},
        {'id':'batchsize','type':'int','mode':'wd'},
        {'id':'senderlimit','type':'int','mode':'wd'},
        {'id':'senderinterval','type':'int','mode':'wd'},
        {'id':'mailqueue','type':'string','mode':'wd'},
        {'id':'getter','type':'string','mode':'wd'},
        {'id':'setter','type':'string','mode':'wd'},
       )
    
    # initial properties, very handy when upgrading
    maillist = []
    disabled = []
    moderator = []
    moderatedlist = []
    mailoptions = []
    returnpath = ''
    moderated = 0
    unclosed = 0
    plainmail = 0
    keepdate = 0
    storage = 'archive'
    archived = archive_options[0]
    subscribe = 'subscribe'
    unsubscribe = 'unsubscribe'
    mtahosts = []
    spamlist = []
    atmask = '(at)'
    sniplist = [r'(\n>[^>].*)+|(\n>>[^>].*)+',
                r'(?s)\n-- .*',
                r'(?s)\n_+\n.*']
    catalog = 'Catalog'
    xmailer = 'GroupServer'
    headers = ''
    batchsize = 0
    senderlimit = 10                # default: no more than 10 mails
    senderinterval = 600            # in 10 minutes (= 600 seconds) allowed
    mailqueue = 'mqueue'
    getter = ''
    setter = ''
        
    def __init__(self, id, title=''):
        """ Initialise a new instance of XWFMailingListManager.
        
        """
        self.__name__ = id
        self.id = id
        self.title = title
        self._setupMetadata()
        self.__initialised = 0
        
       
    security.declareProtected('Add Mail Boxers','manage_afterAdd') 
    def manage_afterAdd(self, item, container):
        """ For configuring the object post-instantiation.
                        
        """
        if getattr(self, '__initialised', 1):
            return 1
        
        item.manage_addProduct['MailHost'].manage_addMailHost('MailHost', 
                                                              smtp_host='127.0.0.1')
        
        return True

    security.declareProtected('View','get_catalog')
    def get_catalog(self):
        """ Get the catalog associated with this file library.
        
        """
        return self.Catalog

    security.declareProtected('View','find_email')
    def find_email(self, query):
        """ Return the catalog 'brains' objects representing the results of
        our query.
        
        """
        catalog = self.get_catalog()
        
        return catalog.searchResults(query)

    security.declareProtected('Manage properties', 'unrestricted_find_email')
    def unrestricted_find_email(self, query):
        """ Similar to find email, but using the unrestricted version of
        searchResults.
        
        """
        catalog = self.get_catalog()
        
        return catalog.unrestrictedSearchResults(query)

    security.declareProtected('View','get_list')
    def get_list(self, list_id):
        """ Get a contained list, given the list ID.
        
        """
        return getattr(self.aq_explicit, list_id)

    security.declareProtected('View','get_listPropertiesFromMailto')
    def get_listPropertiesFromMailto(self, mailto):
        """ Get a contained list, given the list mailto.
        
        """
        list_props = {}
        for listobj in self.objectValues('XWF Mailing List'):
            if getattr(listobj, 'mailto', '').lower() == mailto.lower():
                for prop in self._properties:
                    pid = prop['id']
                    list_props[pid] = getattr(listobj, pid, None)
                list_props['id'] = listobj.getId()
                return list_props
        return {}

    security.declareProtected('View','get_listProperty')
    def get_listProperty(self, list_id, property, default=None):
        """ Get the given property of the given list_id.
        
        """
        list = self.get_list(list_id)
                
        return list.getProperty(property, default)

    def processSpool(self):
        """ Process the deferred spool files.

        """
        objdir = os.path.join(*self.getPhysicalPath())
        spooldir = os.path.join(MAILDROP_SPOOL, objdir)
        if not os.path.exists(spooldir): # no spool to process yet
            return
        for spoolfilepath in os.listdir(spooldir):
            if os.path.exists(os.path.join(spooldir, '%s.lck' % spoolfilepath)):
                continue # we're locked
            spoolfilepath = os.path.join(spooldir, spoolfilepath)
            spoolfile = file(spoolfilepath)
            line = spoolfile.readline().strip()
            if len(line) < 5 or line[:2] != ';;' or line[-2:] != ';;':
                #logger.error('No group was specified (line was "%s")' % line)
                continue

            groupname = line[2:-2]
            group = self.get_list(groupname)
            if not group:
                #logger.error('No such group "%s"' % groupname)
                continue

            mailString = spoolfile.read()

            try:
                group.sendMail(mailString)
                spoolfile.close()
                os.remove(spoolfilepath)
                # sleep a little
                time.sleep(0.5)
            except:
                pass

    def processBounce(self, group_id, email):
        """ Process a bounce for a particular list.
        
        """
        from Products.XWFCore.XWFUtils import get_site_by_id, getOption, get_support_email
        action = 'bounce_detection %s' % email
        
        user = self.acl_users.get_userByEmail(email)
        if not user:
            return 'no user with email %s' % email
        
        Bounces = getattr(self, 'Bounces', False)
        
        if not Bounces:
            self.manage_addFolder('Bounces')
            Bounces = getattr(self, 'Bounces')
        
        group_obj = getattr(Bounces.aq_explicit, group_id, False)
        if not group_obj:
            Bounces.manage_addFolder(group_id)
            group_obj = getattr(Bounces.aq_explicit, group_id)
        
        obj = getattr(group_obj.aq_explicit, user.getId(), False)
        if not obj:
            group_obj.manage_addProduct['CustomProperties'].manage_addCustomProperties(user.getId())
            obj = getattr(group_obj.aq_explicit, user.getId())
        
        bounce_addresses = obj.getProperty('bounce_addresses', [email])
        if not obj.hasProperty('bounce_addresses'):
            obj.manage_addProperty('bounce_addresses', bounce_addresses, 'lines')
        else:
            if email not in bounce_addresses:
                bounce_addresses.append(email)
            obj.manage_changeProperties(bounce_addresses=bounce_addresses)
        
        # Perform a little heuristic analysis ... figure out if we've had any successful emails since the last bounce
        now = DateTime.DateTime()
        
        last_action = obj.getProperty('last_bounce_time', 0)
        bounce_count = obj.getProperty('bounce_count', 1)
        had_success = False
        list_object = getattr(self.aq_explicit, group_id, None)
        if last_action:
            last_failure_diff = now-last_action       
            # we look for the second-to-last email, since the last one is
            # probably the one that bounced!
            if list_object:
                archives = getattr(list_object, 'archive', None)
                last_success_object = None
                if archives:
                    items = archives.objectValues()
                    if len(items) > 2:
                        last_success_object = items[-2]
                
                last_success_diff = 0
                if last_success_object:                         
                    last_success_diff = now - last_success_object.getProperty('mailDate')
                    
                if last_failure_diff > last_success_diff:
                    # if we haven't detected a bounce in the last 24 hours, give a bonus 'point'
                    if last_failure_diff > 1.0:
                        bounce_count -= 2
                    else:
                        bounce_count -= 1
                    
                    had_success = True
        
        if not obj.hasProperty('bounce_count'):
            obj.manage_addProperty('bounce_count', 1, 'int')
        else:
            # only increment the bounce count if we haven't detected
            # a failure in the last 24 hours. This is to give temporary
            # failures a chance to recover
            if last_action and last_failure_diff > 1.0:
                bounce_count += 1
            else:
                action = '24_hours_allowance %s' % email
            bounce_count = bounce_count > 1 and bounce_count or 1
            obj.manage_changeProperties(bounce_count=bounce_count)
        
        if not obj.hasProperty('last_bounce_time'):
            obj.manage_addProperty('last_bounce_time', now, 'date')
        else:
            obj.manage_changeProperties(last_bounce_time=now)
        
        do_notification = False
        lnt = filter(None, map(lambda x: x.strip(), obj.getProperty('notification_times', [])))
        
        if len(lnt) >= 1:
            lnt_elapsed = now - DateTime.DateTime(lnt[-1])
        else:
            lnt_elapsed = 0
        
        if (not lnt) or (lnt_elapsed > 1.0):
            do_notification = True
        
        notification_type = 'bounce_detection'
        # disable delivery
        if bounce_count >= 3:
            user.remove_defaultDeliveryEmailAddress(email)
            # reset the bounce counter, but penalize them a single point for having
            # been disabled before
            obj.manage_changeProperties(bounce_count=1)
            do_notification = True
            bounce_addresses = obj.getProperty('bounce_addresses')
            try:
                bounce_addresses.remove(email)
            except:
                pass
            obj.manage_changeProperties(bounce_addresses=bounce_addresses)
            action = 'disabled_email %s' % email
            notification_type = 'disabled_email'
        elif had_success:
            action = 'reprieve %s' % email
        
        if do_notification:
            addresses = user.get_emailAddresses()
            try:
                addresses.remove(email)
            except:
                pass
                
            if addresses:
                n_dict = {}
                if list_object:
                    site_id = list_object.getProperty('siteId', '')
                    site_obj = get_site_by_id(list_object, siteId)
                    support_email = get_support_email(group_obj, siteId)
                    
                    n_dict =  {
                                  'bounced_email' : email,
                                  'memberId'      : user.getId(),
                                  'groupId'       : group_id,
                                  'groupName'     : group_obj.title_or_id(),
                                  'siteId'        : site_id,
                                  'siteName'      : site_obj.title_or_id(),
                                  'canonical'     : getOption(group_obj, 'canonicalHost'),
                                  'supportEmail'  : support_email
                              }
                try:
                    user.send_notification(notification_type, group_id, n_dict=n_dict, email_only=addresses)
                except:
                    pass
                
                if not obj.hasProperty('notification_times'):
                    obj.manage_addProperty('notification_times', [str(now)], 'lines')
                else:
                    lnt.append(str(now))
                    obj.manage_changeProperties(notification_times=lnt)
                    
                nt = obj.getProperty('notification_types', [])        
                if not obj.hasProperty('notification_types'):
                    obj.manage_addProperty('notification_types', [notification_type], 'lines')
                else:
                    nt.append(notification_type)
                    obj.manage_changeProperties(notification_types=nt)
        
        if not obj.hasProperty('action_taken_times'):
            obj.manage_addProperty('action_taken_times', [str(now)], 'lines')
        else:
            att = obj.getProperty('action_taken_times')
            att.append(str(now))
            obj.manage_changeProperties(action_taken_times=att)
        
        if not obj.hasProperty('action_taken'):
            obj.manage_addProperty('action_taken', [action], 'lines')
        else:
            at = obj.getProperty('action_taken')
            at.append(action)
            obj.manage_changeProperties(action_taken=at)    
        
        return True
                
    security.declareProtected('Upgrade objects', 'upgrade')
    security.setPermissionDefault('Upgrade objects', ('Manager', 'Owner'))
    def upgrade(self):
        """ Upgrade to the latest version.
            
        """
        currversion = getattr(self, '_version', 0)
        if currversion == self.version:
            return 'already running latest version (%s)' % currversion

        self.__initialised = 1
        self._setupMetadata()
        self._version = self.version

        return 'upgraded %s to version %s from version %s' % (self.getId(),
                                                              self._version,
                                                              currversion)

manage_addXWFMailingListManagerForm = PageTemplateFile(
    'management/manage_addXWFMailingListManagerForm.zpt',
    globals(),
    __name__='manage_addXWFMailingListManagerForm')

def manage_addXWFMailingListManager(self, id, title='Mailing List Manager',
                                     REQUEST=None):
    """ Add an XWFMailingListManager to a container.

    """
    ob = XWFMailingListManager(id, title)
    self._setObject(id, ob)
    if REQUEST is not None:
        return self.manage_main(self,REQUEST)

InitializeClass(XWFMailingListManager)

def initialize(context):
    context.registerClass(
        XWFMailingListManager,
        permission="Add XWF MailingListManager",
        constructors=(manage_addXWFMailingListManagerForm,
                      manage_addXWFMailingListManager),
        icon='icons/ic-mailinglistmanager.png'
        )
