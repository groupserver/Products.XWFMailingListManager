# Copyright IOPEN Technologies Ltd., 2003
# richard@iopen.net
#
# For details of the license, please see LICENSE.
#
# You MUST follow the rules in README_STYLE before checking in code
# to the head. Code which does not follow the rules will be rejected.  
#
try:
    from zope.browserpage import metaconfigure
except ImportError:
    from zope.app.pagetemplate import metaconfigure
from zope.contentprovider import tales
from zope.tales.tales import RegistrationError
try:
    metaconfigure.registerType('provider',
                               tales.TALESProviderExpression)
except RegistrationError:
    # almost certainly been registered somewhere else already.
    pass

import XWFMailingListManager, XWFMailingList
import XWFVirtualMailingListArchive2

import postMessageContentProvider
import postprivacy

from AccessControl import ModuleSecurityInfo
from AccessControl import allow_class, allow_module, allow_type

from queries import MessageQuery

q_security = ModuleSecurityInfo('Products.XWFMailingListManager.queries')
q_security.declarePublic('MessageQuery')
allow_class(MessageQuery)

from datetime import datetime
allow_type(datetime)

import time
allow_class(time)

def initialize(context):
    # import lazily and defer initialization to the module
    XWFMailingListManager.initialize(context)
    XWFMailingList.initialize(context)
    XWFVirtualMailingListArchive2.initialize(context)
