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
from AccessControl.class_init import InitializeClass
from OFS.Folder import Folder

from Products.XWFCore.XWFUtils import getOption, get_support_email
from Products.XWFCore.XWFUtils import get_site_by_id, get_group_by_siteId_and_groupId
from Products.XWFCore.cache import SimpleCache

# TODO: once catalog is completely removed, we can remove XWFMetadataProvider too
from Products.XWFCore.XWFMetadataProvider import XWFMetadataProvider

from Products.XWFMailingListManager.queries import MessageQuery, DigestQuery

import os, time, logging, StringIO, traceback
from Products.CustomUserFolder.queries import UserQuery
import sqlalchemy as sa
import datetime

log = logging.getLogger('XWFMailingListManager.XWFMailingListManager') #@UndefinedVariable

MAILDROP_SPOOL = '/tmp/mailboxer_spool2'

class Record:
    pass

class XWFMailingListManager(Folder, XWFMetadataProvider):
    """ A searchable, self indexing mailing list manager.

    """
    security = ClassSecurityInfo()
    security.setPermissionDefault('View', ('Manager',))

    ListMailtoCache = SimpleCache("ListMailtoCache")
    
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
        try:
            return getattr(self.aq_explicit, list_id)
        except AttributeError:
            raise AttributeError("No such list %s" % list_id)

    security.declareProtected('View','get_listFromMailto')
    def get_listFromMailto(self, mailto):
        """ Get a contained list, given the list mailto.
        
        """
        mailto = mailto.lower()

        site = self.site_root()
        siteId = site.getId()

        thisCacheKey = '%s:%s' % (siteId, mailto)

        found = False
        
        # first, look in the cache
        if self.ListMailtoCache.has_key(thisCacheKey):
            listId = self.ListMailtoCache.get(thisCacheKey)
            found = True
            log.info("found list from mailto using cache")

        # then try to find it fast, using the LHS of the email address
        else:
            listIds = self.objectIds('XWF Mailing List')
            
            assert mailto.find('@'), "No LHS/RHS with @ in mailto"

            possibleId = mailto.split('@')[0]
            possListIds = filter(None,
                          [x.find(possibleId) >= 0 and x for x in listIds])
            for listId in possListIds:
                listObj = getattr(self, listId)
                list_mailto = getattr(listObj, 'mailto', '').lower()
                if list_mailto:
                    cacheKey = '%s:%s' % (siteId, list_mailto)
                    self.ListMailtoCache.add(cacheKey, listId)
                    if list_mailto == mailto:
                        log.info("found list from mailto by fast lookup")
                        found = True
                        break
        
        # if we still haven't found it, wade through everything, might as
        # well cache as we go
        if not found:
            for listobj in self.objectValues('XWF Mailing List'):
                list_mailto = getattr(listobj, 'mailto', '').lower()
                listId = listobj.getId()
                cacheKey = '%s:%s' % (siteId, list_mailto)
                
                if list_mailto:
                    self.ListMailtoCache.add(cacheKey, listId)
                    if list_mailto == mailto:
                        log.info("found list from mailto by slow lookup")
                        found = True
                        break
        
        if not found:
            listId = ''
            log.warn("did not find list from mailto")
                        
        return self.get_list(listId)

    security.declareProtected('View','get_listPropertiesFromMailto')
    def get_listPropertiesFromMailto(self, mailto):
        """ Get a contained list's properties, given the list mailto.
        
        """
        list_props = {}
        try:
            listobj = self.get_listFromMailto(mailto)
        except AttributeError:
            log.info("Could not find list for mailto (%s)" % mailto)
            listobj = None
        if listobj:
            for prop in self._properties:
                pid = prop['id']
                list_props[pid] = getattr(listobj, pid, None)
            list_props['id'] = listobj.getId()
            
        return list_props

    security.declareProtected('View','get_listProperty')
    def get_listProperty(self, list_id, property, default=None):
        """ Get the given property of the given list_id.
        
        """
        list = self.get_list(list_id)
            
        return list.getProperty(property, default)

    def processDigests(self, REQUEST):
        """ Process the digests for all lists.

        """
        da = self.zsqlalchemy 
        assert da
        messageQuery = MessageQuery(self, da)
        digestQuery = DigestQuery(self, da)

        # get the groups which have been active in the last 24-ish hours
        active_groups = messageQuery.active_groups() 
        
        # collect a dict of groups we want to digest
        digest_dict = {}
        for g in active_groups:
            digest_dict[(g['site_id'],g['group_id'])] = 1

        # get the groups which have *not* had a digest in the last 7-ish days,
        # but have been active in last 3 months
        no_recent_digest = digestQuery.no_digest_but_active()
        no_recent_digest_dict = {}        
        for g in no_recent_digest:
            key = (g['site_id'],g['group_id'])
            digest_dict[key] = 1
        
        digests_required = digest_dict.keys()

        for site_id,group_id in digests_required:
            log.info("Requesting digest for: %s, %s" % (site_id,group_id))
            group = self.get_list(group_id)
            if not group:
                log.warn("Could not find list: %s" % group_id)
                continue
            try:
                group.manage_digestBoxer(REQUEST)
            except Exception,x:
                fp = StringIO.StringIO()
                traceback.print_exc(file=fp)
                message = fp.getvalue()

                log.warn("Problems processing digest for list %s: %s" % (group_id, message))
                continue
            

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
                continue

            groupname = line[2:-2]
            group = self.get_list(groupname)
            if not group:
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
        da = self.site_root().zsqlalchemy
        bounceTable = da.createTable('bounce')
        bt_insert = bounceTable.insert()
        bt_select = bounceTable.select()
        
        now = datetime.datetime.now()        

        bt_select.append_whereclause(bounceTable.c.email==email)
        bt_select.append_whereclause(bounceTable.c.date > (now-datetime.timedelta(60)))
        bt_select.order_by(sa.desc(bounceTable.c.date))
        
        r = bt_select.execute()
        previous_bounces = []
        if r.rowcount:
            for row in r:
                bounce_date = row['date'].strftime("%Y%m%d")
                if bounce_date not in previous_bounces:
                    previous_bounces.append(bounce_date)
        
        user = self.acl_users.get_userByEmail(email)
        if not user:
            m = 'Bounce detection failure: no user with email %s' % email
            log.info(m)
            return m

        user_id = user.getId()
        log.info('Bounce detected for %s (%s) in group %s' % (user_id, email, group_id))
        
        # insert into the bounce table
        bt_insert.execute(date=now, group_id=group_id,
                          site_id='', email=email, user_id=user_id)

        do_notification = False
        bounce_date = now.strftime("%Y%m%d")
        if bounce_date not in previous_bounces:
            previous_bounces.append(bounce_date)
            do_notification=True

        log.info("Detected %s bounces on unique days in last 60 days" % len(previous_bounces))

        addresses = map(lambda e: e.lower(), user.get_verifiedEmailAddresses())
        try:
            addresses.remove(email.lower())
        except ValueError:
            log.info('%s (%s) was already unverified' % (user_id, email))
            do_notification = False
        
        notification_type = 'bounce_detection'
        # disable address by unverifying after 5 bounces
        if len(previous_bounces) >= 5:
            # TODO: might want to clear the bounce table at this point perhaps
            uq = UserQuery(user, da)
            uq.unverify_userEmail(email)
            log.info('Unverifying %s (%s)' % (user_id, email))
            notification_type = 'disabled_email'            
        
        if do_notification:
            if addresses:
                n_dict = {}
                try:
                    list_object = self.get_list(group_id)
                except AttributeError:
                    list_object = None

                if list_object:
                    site_id = list_object.getProperty('siteId', '')
                    site = get_site_by_id(list_object, site_id)
                    group = get_group_by_siteId_and_groupId(list_object, site_id, group_id)
                    support_email = get_support_email(group, site_id)
                    
                    n_dict =  {
                                  'bounced_email' : email,
                                  'memberId'      : user.getId(),
                                  'groupId'       : group_id,
                                  'groupName'     : group.title_or_id(),
                                  'siteId'        : site_id,
                                  'siteName'      : site.title_or_id(),
                                  'canonical'     : getOption(group, 'canonicalHost'),
                                  'supportEmail'  : support_email
                              }
                try:
                    user.send_notification(notification_type, group_id, n_dict=n_dict, email_only=addresses)
                except:
                    pass
                
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
