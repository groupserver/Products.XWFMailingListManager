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
from App.class_init import InitializeClass
from OFS.Folder import Folder
from gs.cache import cache

import logging
log = logging.getLogger('XWFMailingListManager.XWFMailingListManager')


class XWFMailingListManager(Folder):
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

    id_namespace = 'http://xwft.org/ns/mailinglistmanager'
    _properties = (
        {'id': 'title', 'type': 'string', 'mode': 'w'},
        {'id': 'maillist', 'type': 'lines', 'mode': 'wd'},
        {'id': 'disabled', 'type': 'lines', 'mode': 'wd'},
        {'id': 'moderator', 'type': 'lines', 'mode': 'wd'},
        {'id': 'moderatedlist', 'type': 'lines', 'mode': 'wd'},
        {'id': 'mailoptions', 'type': 'lines', 'mode': 'wd'},
        {'id': 'returnpath', 'type': 'string', 'mode': 'wd'},
        {'id': 'moderated', 'type': 'boolean', 'mode': 'wd'},
        {'id': 'unclosed', 'type': 'boolean', 'mode': 'wd'},
        {'id': 'plainmail', 'type': 'boolean', 'mode': 'wd'},
        {'id': 'keepdate', 'type': 'boolean', 'mode': 'wd'},
        {'id': 'subscribe', 'type': 'string', 'mode': 'wd'},
        {'id': 'unsubscribe', 'type': 'string', 'mode': 'wd'},
        {'id': 'mtahosts', 'type': 'tokens', 'mode': 'wd'},
        {'id': 'spamlist', 'type': 'lines', 'mode': 'wd'},
        {'id': 'atmask', 'type': 'string', 'mode': 'wd'},
        {'id': 'sniplist', 'type': 'lines', 'mode': 'wd'},
        {'id': 'xmailer', 'type': 'string', 'mode': 'wd'},
        {'id': 'headers', 'type': 'string', 'mode': 'wd'},
        {'id': 'senderlimit', 'type': 'int', 'mode': 'wd'},
        {'id': 'senderinterval', 'type': 'int', 'mode': 'wd'},
        {'id': 'mailqueue', 'type': 'string', 'mode': 'wd'},
        {'id': 'getter', 'type': 'string', 'mode': 'wd'},
        {'id': 'setter', 'type': 'string', 'mode': 'wd'},
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
    subscribe = 'subscribe'
    unsubscribe = 'unsubscribe'
    mtahosts = []
    spamlist = []
    atmask = '(at)'
    sniplist = [r'(\n>[^>].*)+|(\n>>[^>].*)+',
                r'(?s)\n-- .*',
                r'(?s)\n_+\n.*']
    xmailer = 'GroupServer'
    headers = ''
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

    security.declareProtected('Add Mail Boxers', 'manage_afterAdd')
    def manage_afterAdd(self, item, container):
        """ For configuring the object post-instantiation.

        """
        if getattr(self, '__initialised', 1):
            return 1
        return True

    security.declareProtected('View', 'get_list')
    def get_list(self, list_id):
        """ Get a contained list, given the list ID.

        """
        try:
            return getattr(self.aq_explicit, list_id)
        except AttributeError:
            raise AttributeError("No such list %s" % list_id)

    @cache('Products.XWFMailingListManager', lambda x, y: y, 3600)
    def get_listIdFromMailto(self, mailto):
        """ Get a contained list, given the list mailto.

        """
        mailto = mailto.lower()
        # then try to find it fast, using the LHS of the email address
        listIds = self.objectIds('XWF Mailing List')

        assert mailto.find('@'), "No LHS/RHS with @ in mailto"

        possibleId = mailto.split('@')[0]
        possListIds = filter(None,
                      [x.find(possibleId) >= 0 and x for x in listIds])
        found = False  # Typical pessimism
        for listId in possListIds:
            listObj = getattr(self, listId)
            list_mailto = getattr(listObj, 'mailto', '').lower()
            if list_mailto:
                if list_mailto == mailto:
                    found = True
                    break

        # if we still haven't found it, wade through everything
        if not found:
            for listobj in self.objectValues('XWF Mailing List'):
                list_mailto = getattr(listobj, 'mailto', '').lower()
                listId = listobj.getId()
                if list_mailto:
                    if list_mailto == mailto:
                        log.debug("found list (%s) from mailto (%s) by slow lookup" % (listId, mailto))
                        found = True
                        break
        if not found:
            listId = ''
            log.warn("did not find list from mailto (%s)" % mailto)

        return listId

    def get_listFromMailto(self, mailto):
        listId = self.get_listIdFromMailto(mailto)
        retval = self.get_list(listId)
        return retval

    security.declareProtected('View', 'get_listPropertiesFromMailto')
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

    security.declareProtected('View', 'get_listProperty')
    def get_listProperty(self, list_id, property, default=None):
        """ Get the given property of the given list_id.

        """
        mlist = self.get_list(list_id)
        return mlist.getProperty(property, default)


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
        return self.manage_main(self, REQUEST)


InitializeClass(XWFMailingListManager)


def initialize(context):
    context.registerClass(
        XWFMailingListManager,
        permission="Add XWF MailingListManager",
        constructors=(manage_addXWFMailingListManagerForm,
                      manage_addXWFMailingListManager),
        icon='icons/ic-mailinglistmanager.png'
        )
