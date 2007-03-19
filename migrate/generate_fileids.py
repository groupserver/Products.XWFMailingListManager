# coding=utf-8
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

from Testing.ZopeTestCase import base
app = base.app()

import md5, os, sys
import Products.Five
import Products.XWFMailingListManager
from Products.XWFMailingListManager import emailmessage
from Products.Five import zcml
from Products.ZSQLAlchemy.ZSQLAlchemy import manage_addZSQLAlchemy

zcml.load_config('meta.zcml', Products.Five)
zcml.load_config('permissions.zcml', Products.Five)
zcml.load_config('configure.zcml', Products.XWFMailingListManager)

alchemy_adaptor = manage_addZSQLAlchemy(app, 'zalchemy')
alchemy_adaptor.manage_changeProperties( hostname='localhost',
                                         port=5432,
                                         username='richard',
                                         password='',
                                         dbtype='postgres',
                                         database='onlinegroups.net')

from Products.XWFMailingListManager.emailmessage import IRDBStorageForEmailMessage
from sqlalchemy.exceptions import SQLError
     
importDir = sys.argv[1]
for fname in os.listdir( importDir ):
    email = file( os.path.join( importDir, fname ) ).read()
    msg = emailmessage.EmailMessage( email )
    msg = emailmessage.EmailMessage( email, msg.get('x-gsgroup-title',''), msg.get('x-gsgroup-id',''), msg.get('x-gssite-id', ''), lambda x: msg.get('x-gsuser-id', ''))
    if msg.get('x-xwfnotification-file-id',''):
        print('%s,%s,%s' % (msg.topic_id, msg.post_id, ','.join(msg.get('x-xwfnotification-file-id','').split())))
