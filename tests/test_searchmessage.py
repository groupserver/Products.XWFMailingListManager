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
      >>> from Products.XWFMailingListManager import queries
      >>> from Products.Five import zcml
      >>> from Products.ZSQLAlchemy.ZSQLAlchemy import manage_addZSQLAlchemy

      >>> zcml.load_config('meta.zcml', Products.Five)
      >>> zcml.load_config('permissions.zcml', Products.Five)
      >>> zcml.load_config('configure.zcml', Products.XWFMailingListManager)
      
      >>> alchemy_adaptor = manage_addZSQLAlchemy(app, 'zalchemy')
      >>> alchemy_adaptor.manage_changeProperties( hostname='localhost',
      ...                                             port=5433,
      ...                                             username='onlinegroups',
      ...                                             password='',
      ...                                             dbtype='postgres',
      ...                                             database='onlinegroups.net')
      
      >>> mq = queries.MessageQuery( {}, alchemy_adaptor )
      >>> len(mq.latest_topics( 'ogs', ['team','test'], limit=20, offset=0))
      20
      >>> mq.latest_topics( 'ogs', ['NOTAGROUP'], limit=20, offset=0) == []
      True
      >>> mq.previous_post( '6nwvvUew8YUOIpnHxinZN7' )['post_id']
      '2U7eZNz0BzI29ts9Cq8iXU'
      >>> mq.next_post( '6nwvvUew8YUOIpnHxinZN7' )['post_id']
      '2IpSfPclqNJeSk2TtXlmNo'
      >>> mq.earlier_topic( '6uTwCLOKJ8zQbaevQe0ySr' )['subject']
      u'testing rdb backend'
      >>> mq.later_topic( '6uTwCLOKJ8zQbaevQe0ySr' )['date'].isoformat()
      '2007-03-15T16:28:09+13:00'
      >>> mq.topic_post_navigation( '6KFmjSgWfzGmy1XeGkjhTW' )
      {'previous_post_id': None, 'next_post_id': None, 'last_post_id': None, 'first_post_id': None}
      >>> len(mq.topic_posts( '5GNlPkUv85Koyz5fS2NNxp' )) == 40
      False
      >>> mq.post( '6KFmjSgWfzGmy1XeGkjhTW' )['subject']
      u'testing'
      >>> mq.post_count( 'ogs', ['team','test'] )
      1632L
      >>> mq.topic_search( 'blarg foo hello', 'ogs', ['team','test'] )[0]['topic_id']
      '4zW2Q4zdor20oGqWhxJuTF'
      >>> mq.post_id_from_legacy_id('139137')
      >>> mq.active_groups()
      []
 
    Clean up:
      >>> tearDown()
      
    """

def test_suite():
    from Testing.ZopeTestCase import ZopeDocTestSuite
    return ZopeDocTestSuite()

if __name__ == '__main__':
    framework()
