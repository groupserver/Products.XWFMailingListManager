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

# CHANGE THESE
DBHOSTNAME='localhost'
DBPORT=5433
DBUSERNAME='onlinegroups'
DBPASSWORD=''
DBNAME='onlinegroups.net'

# You shouldn't need to change below here
import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Products.Five import zcml
from Products.XWFMailingListManager import emailmessage
from Products.XWFMailingListManager.emailmessage import IRDBStorageForEmailMessage
from Products.ZSQLAlchemy.ZSQLAlchemy import manage_addZSQLAlchemy
from Testing.ZopeTestCase import base
from sqlalchemy.exceptions import SQLError

import Products.Five
import Products.XWFMailingListManager

import difflib
import sqlalchemy
import time

app = base.app()


zcml.load_config('meta.zcml', Products.Five)
zcml.load_config('permissions.zcml', Products.Five)
zcml.load_config('configure.zcml', Products.XWFMailingListManager)

alchemy_adaptor = manage_addZSQLAlchemy(app, 'zalchemy')
alchemy_adaptor.manage_changeProperties( hostname=DBHOSTNAME,
                                         port=DBPORT,
                                         username=DBUSERNAME,
                                         password=DBPASSWORD,
                                         dbtype='postgres',
                                         database=DBNAME)


importDir = sys.argv[1]
count = 0
top = time.time()
session = alchemy_adaptor.getSession()
metadata = session.getMetaData()
and_ = sqlalchemy.and_; or_ = sqlalchemy.or_
postTable = sqlalchemy.Table('post', metadata, autoload=True)
log = file(sys.argv[2], 'a+')
try:
    position = int(sys.argv[3])
except:
    position = 0
print position
for fname in os.listdir( importDir )[position:]:
     email = file( os.path.join( importDir, fname ) ).read()
     msg = emailmessage.EmailMessage( email )
     msg = emailmessage.EmailMessage( email, msg.get('x-gsgroup-title',''), msg.get('x-gsgroup-id',''), msg.get('x-gssite-id', ''), lambda x: msg.get('x-gsuser-id', ''))
     msgstorage = IRDBStorageForEmailMessage( msg )
     msgstorage.set_zalchemy_adaptor( alchemy_adaptor )
     try:
         msgstorage.insert()
         msgstorage.insert_keyword_count()
         print '.',
     except SQLError, x:
         print 'e',
         log.write("---------START---------\n")
         log.write('%s: %s\n' % (msg.get('x-gsoriginal-id'), str(x.orig)))
         r = postTable.select( postTable.c.post_id==msg.post_id ).execute()
         row = r.fetchone()
         if row:
             log.write("===POSSIBLE DUPLICATE DETAILS===\n\n")
             hdiff = '\n'.join(difflib.unified_diff(msg.headers.encode('utf-8').split('\n'), row.header.encode('utf-8').split('\n')))
             if hdiff:
                 log.write("===HEADER DIFF FOLLOWS===\n")
                 log.write(hdiff+'\n')
             bdiff = '\n'.join(difflib.unified_diff(msg.body.encode('utf-8').split('\n'), row.body.encode('utf-8').split('\n')))
             if bdiff:
                 log.write("===BODY DIFF FOLLOWS===\n\n")
                 log.write(bdiff+'\n')
             log.write("---------END--------\n")
         else:
             log.write("===UNKNOWN ERROR===\nn")
             log.write("%s\n\n" % msg.headers.encode('utf-8'))
             log.write("%s\n" % msg.body.encode('utf-8'))
             log.write("---------END--------\n")
         log.flush()
         
     count += 1
     if not count % 500:
         print
         print 'iters: %s, %s per iter' % (count, (time.time()-top)/float(count))

print
print 'took %s' % (time.time()-top)
         
     
