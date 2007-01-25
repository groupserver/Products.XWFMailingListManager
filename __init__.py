# Copyright IOPEN Technologies Ltd., 2003
# richard@iopen.net
#
# For details of the license, please see LICENSE.
#
# You MUST follow the rules in README_STYLE before checking in code
# to the head. Code which does not follow the rules will be rejected.  
#
import XWFMailingListManager, XWFMailingList
import XWFVirtualMailingListArchive, XWFVirtualMailingListArchive2

import postContentProvider, postMessageContentProvider, topicIndexContentProvider, stickyTopicToggleContentProvider

def initialize(context):
    # import lazily and defer initialization to the module
    XWFMailingListManager.initialize(context)
    XWFMailingList.initialize(context)
    XWFVirtualMailingListArchive.initialize(context)
    XWFVirtualMailingListArchive2.initialize(context)
