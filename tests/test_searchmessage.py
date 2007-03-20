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
      >>> import time
      >>> import Products.XWFMailingListManager
      >>> from Products.XWFMailingListManager import queries
      >>> from Products.Five import zcml
      >>> from Products.ZSQLAlchemy.ZSQLAlchemy import manage_addZSQLAlchemy

      >>> zcml.load_config('meta.zcml', Products.Five)
      >>> zcml.load_config('permissions.zcml', Products.Five)
      >>> zcml.load_config('configure.zcml', Products.XWFMailingListManager)
      
      >>> alchemy_adaptor = manage_addZSQLAlchemy(app, 'zalchemy')
      >>> alchemy_adaptor.manage_changeProperties( hostname='localhost',
      ...                                             port=5432,
      ...                                             username='richard',
      ...                                             password='',
      ...                                             dbtype='postgres',
      ...                                             database='onlinegroups.net')
      
      >>> mq = queries.MessageQuery( {}, alchemy_adaptor )
      >>> a = time.time()
      >>> len(mq.latest_topics( 'ogs', ['team','test'], limit=20, offset=0))
      20
      >>> mq.latest_topics( 'ogs', ['NOTAGROUP'], limit=20, offset=0) == None
      True
      >>> b = time.time()
      >>> mq.previous_post( '6nwvvUew8YUOIpnHxinZN7' )['post_id']
      '2U7eZNz0BzI29ts9Cq8iXU'
      >>> c = time.time()
      >>> mq.next_post( '6nwvvUew8YUOIpnHxinZN7' )['post_id']
      '2IpSfPclqNJeSk2TtXlmNo'
      >>> mq.previous_topic( '6uTwCLOKJ8zQbaevQe0ySr' )['date'].isoformat()
      '2007-03-15T16:28:09+13:00'
      >>> d = time.time()
      >>> mq.next_topic( '6uTwCLOKJ8zQbaevQe0ySr' )['subject']
      u'testing rdb backend'
      >>> e = time.time()
      >>> mq.topic_post_navigation( '6KFmjSgWfzGmy1XeGkjhTW' )
      {'previous_post_id': '4OXxPDZDbKp3Zvrtv02J1D', 'next_post_id': '7kN69yiitMRuYwusXyQict', 'last_post_id': '6C40G5mK29eRz66ufGfTGN', 'first_post_id': '7aLFkgbUVe4qx7m04OzNdI'}
      >>> f = time.time()
      >>> len(mq.topic_posts( '5GNlPkUv85Koyz5fS2NNxp' )) == 40
      True
      >>> g = time.time()
      >>> mq.post( '6KFmjSgWfzGmy1XeGkjhTW' )['subject']
      u'testing'
      >>> h = time.time()
      >>> print b-a, c-b, d-c, f-e, e-d, g-f, h-g
      >>> print h-a
      
    Clean up:
      >>> tearDown()
      
    """

def test_suite():
    from Testing.ZopeTestCase import ZopeDocTestSuite
    return ZopeDocTestSuite()

if __name__ == '__main__':
    framework()
