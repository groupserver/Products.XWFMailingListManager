# Copyright IOPEN Technologies Ltd., 2003
# richard@iopen.net
#
# For details of the license, please see LICENSE.
#
# You MUST follow the rules in README_STYLE before checking in code
# to the head. Code which does not follow the rules will be rejected.
#
from __future__ import absolute_import, unicode_literals
from . import XWFMailingListManager
from . import XWFMailingList
from . import XWFVirtualMailingListArchive2

from AccessControl import ModuleSecurityInfo
from AccessControl import allow_class, allow_type

from .queries import MessageQuery

q_security = ModuleSecurityInfo(b'Products.XWFMailingListManager.queries')
q_security.declarePublic(b'MessageQuery')
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
