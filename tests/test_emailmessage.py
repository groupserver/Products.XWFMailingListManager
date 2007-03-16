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
      >>> from Products.ZSQLAlchemy.ZSQLAlchemy import manage_addZSQLAlchemy

      >>> zcml.load_config('meta.zcml', Products.Five)
      >>> zcml.load_config('permissions.zcml', Products.Five)
      >>> zcml.load_config('configure.zcml', Products.XWFMailingListManager)

      >>> email_attachments = file('emails/withattachments.eml').read()
      >>> email_b64attachments = file('emails/base64attachments.eml').read()
      >>> email_b64 = file('emails/base64.eml').read()
      >>> email_simple = file('emails/simple.eml').read()
      >>> email_simple2 = file('emails/simple2.eml').read()
      >>> email_test1 = file('emails/testemail1.eml').read()
      >>> email_attachments2 = file('emails/7479421AFD9.eml').read()
      >>> email_internationalization = file('emails/internationalization.eml').read()
      
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
      >>> msg.post_id
      u'J28Au0rZjjB20Hoax7uUT'
      >>> msg.topic_id
      u'6Ok4eFuiUzhn2xoPVohcz2'
      >>> msg.inreplyto
      u''

   A second attachments example:
      >>> msg2 = emailmessage.EmailMessage(email_attachments2) 
      >>> [ a['filename'] for a in msg2.attachments ]
      [u'', u'', u'', u'', u'image003.jpg', u'image001.jpg', u'Christchurch City Flyer 2007-2008.doc']
      
   An email that has a base 64 attachment:
      >>> b64msg = emailmessage.EmailMessage(email_b64attachments) 
      >>> b64msg.attachments[1]['filename']
      u'Delivery report.txt'

   An email that has the entire body encoded as base64
      >>> b64msg = emailmessage.EmailMessage(email_b64)
      >>> b64msg.attachments[0]['md5']
      '3c56c82af9e6604d31afba86b083444a'

      >>> simplemsg = emailmessage.EmailMessage(email_simple, 'Example Group', sender_id_cb=lambda x: 'richard')
      >>> simplemsg.title
      u'testing 7 / richard@iopen.net'
      >>> simplemsg.sender
      u'richard@iopen.net'
      >>> simplemsg.message.get('from')
      '"" <richard@iopen.net>'
      >>> simplemsg.sender_id
      'richard'
      >>> simplemsg.tags
      [u'one', u'two', u'three']

      >>> simplemsg2 = emailmessage.EmailMessage(email_simple2, 'Example Group')
      >>> simplemsg2.post_id == simplemsg.post_id
      False
      >>> simplemsg2.topic_id == simplemsg.topic_id
      True
      >>> simplemsg2.language
      'en'
     
      >>> test1msg = emailmessage.EmailMessage(email_test1)
      >>> test1msg.title
      u'Email bounced / privacy@obscured.co.nz'
      >>> test1msg.sender
      u'privacy@obscured.co.nz'
      >>> test1msg.message.get('from')
      'privacy@obscured.co.nz'
      >>> len(test1msg.headers)
      2281
      >>> test1msg.inreplyto
      u'<20070227111232.C25DDFFF1@orange.iopen.net>'
      >>> test1msg.language
      'en'
      >>> test1msg.word_count['message']
      4
      
      >>> imsg = emailmessage.EmailMessage(email_internationalization, 'test')
      >>> imsg.subject
      u'unicode testing: I\xf1t\xebrn\xe2ti\xf4n\xe0liz\xe6ti\xf8n'
      
    Setup ZSQLAlchemy
      >>> alchemy_adaptor = manage_addZSQLAlchemy(app, 'zalchemy')
      >>> alchemy_adaptor.manage_changeProperties( hostname='localhost',
      ...                                             port=5432,
      ...                                             username='richard',
      ...                                             password='',
      ...                                             dbtype='postgres',
      ...                                             database='onlinegroups.net')

    Adapt:
      >>> from Products.XWFMailingListManager.emailmessage import IRDBStorageForEmailMessage
      >>> msgstorage = IRDBStorageForEmailMessage( simplemsg )
      >>> msgstorage.set_zalchemy_adaptor( alchemy_adaptor )
      >>> msgstorage.insert()

      #>>> msgstorage.remove()

      >>> msgstorage2 = IRDBStorageForEmailMessage( b64msg )
      >>> msgstorage2.set_zalchemy_adaptor( alchemy_adaptor )
      >>> msgstorage2.insert()

      >>> msgstorage3 = IRDBStorageForEmailMessage( msg2 )
      >>> msgstorage3.set_zalchemy_adaptor( alchemy_adaptor )
      >>> msgstorage3.insert()

      #>>> msgstorage2.remove()

    Clean up:
      >>> tearDown()
      
    """

def test_suite():
    from Testing.ZopeTestCase import ZopeDocTestSuite
    return ZopeDocTestSuite()

if __name__ == '__main__':
    framework()
