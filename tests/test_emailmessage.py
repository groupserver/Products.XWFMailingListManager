##############################################################################
#
# Copyright (c) 2004, 2005 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Size adapters for testing

$Id: test_size.py 61072 2005-10-31 17:43:51Z philikon $
"""
import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from zope.interface import implements
from zope.app.size.interfaces import ISized

def test_emailmessage():
    """
    Test emailmessage and adapters

    Set up:
      >>> from zope.app.testing.placelesssetup import setUp, tearDown
      >>> setUp()
      >>> import Products.Five
      >>> import Products.XWFMailingListManager
      >>> from Products.XWFMailingListManager import emailmessage
      >>> from Products.Five import zcml
      >>> zcml.load_config('meta.zcml', Products.Five)
      >>> zcml.load_config('permissions.zcml', Products.Five)
      >>> zcml.load_config('configure.zcml', Products.XWFMailingListManager)

      >>> email_attachments = file('emails/withattachments.eml').read()
      >>> email_b64attachments = file('emails/base64attachments.eml').read()
      >>> email_simple = file('emails/simple.eml').read()

      >>> msg = emailmessage.EmailMessage(email_attachments) 
      >>> msg.sender
      u'richard@iopen.net'
      >>> msg.subject
      u'testing attachments'
      >>> msg.title
      u'testing attachments / richard@iopen.net'
      >>> getattr(msg, 'title')
      u'testing attachments / richard@iopen.net'
      >>> msg.date.isoformat()
      '2007-02-26T16:53:19+13:00'

      >>> b64msg = emailmessage.EmailMessage(email_b64attachments) 
      >>> b64msg.attachments[1]['filename']
      u'Delivery report.txt'

      >>> simplemsg = emailmessage.EmailMessage(email_simple)
      >>> simplemsg.title
      u'testing 7 / richard@iopen.net'
      >>> simplemsg.sender
      u'richard@iopen.net'
      >>> simplemsg.message.get('from')
      '"" <richard@iopen.net>'

    Adapt:
      >>> from Products.XWFMailingListManager.emailmessage import IRDBStorageForEmailMessage
      >>> msgstorage = IRDBStorageForEmailMessage( msg )
      >>> msgstorage.hello_world()
      'hello'

    Clean up:
      >>> tearDown()
      
    """

def test_suite():
    from Testing.ZopeTestCase import ZopeDocTestSuite
    return ZopeDocTestSuite()

if __name__ == '__main__':
    framework()
