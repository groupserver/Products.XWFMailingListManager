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
    execfile('framework.py')

from Products.XWFMailingListManager import emailmessage 

importDir = os.environ.get('IMPORT_DIR', '')

try:
    onlyIds = bool(int(os.environ.get('ONLY_IDS', '0')))
except:
    onlyIds = False

for fname in os.listdir( importDir ):
    email = file( os.path.join( importDir, fname ) ).read()
    msg = emailmessage.EmailMessage( email )
    msg = emailmessage.EmailMessage( email, msg.get('x-gsgroup-title',''), msg.get('x-gsgroup-id',''), msg.get('x-gssite-id', ''), lambda x: msg.get('x-gsuser-id', ''))
    if msg.get('x-xwfnotification-file-id',''):
        if onlyIds:
            for fid in msg.get('x-xwfnotification-file-id', '').split():
                sys.stdout.write('%s\n'%fid)
        else:
            sys.stdout.write(('%s,%s,%s\n' % (msg.topic_id, msg.post_id, ','.join(msg.get('x-xwfnotification-file-id','').split()))))
