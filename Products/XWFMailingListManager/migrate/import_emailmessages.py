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
DBPORT=5432
DBUSERNAME='testbed'
DBPASSWORD=''
DBNAME='testbed'

# You shouldn't need to change below here
import os, sys

if __name__ == '__main__':
    execfile('framework.py')

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

importDir = os.environ.get('IMPORT_DIR', '')
fileName = os.environ.get('LOG_FILE', '')
startPos = os.environ.get('START_POS', '')
try:
    dryRun = int(os.environ.get('DRY_RUN', '')) and True or False
except:
    dryRun = False

sys.stdout.write("importing from: '%s'\n" % importDir)
sys.stdout.write("logging to: '%s'\n" % fileName)

if not dryRun:
    alchemy_adaptor = manage_addZSQLAlchemy(app, 'zalchemy')
    alchemy_adaptor.manage_changeProperties( hostname=DBHOSTNAME,
                                         port=DBPORT,
                                         username=DBUSERNAME,
                                         password=DBPASSWORD,
                                         dbtype='postgres',
                                         database=DBNAME)

count = 0
top = time.time()

if not dryRun:
    session = alchemy_adaptor.getSession()
    metadata = session.getMetaData()
    and_ = sqlalchemy.and_; or_ = sqlalchemy.or_
    postTable = sqlalchemy.Table('post', metadata, autoload=True)

log = file(fileName, 'a+')

if startPos:
    position = int(startPos)
else:
    position = 0

sys.stdout.write("starting at position: %s\n" % startPos)

for fname in os.listdir( importDir )[position:]:
     email = file( os.path.join( importDir, fname ) ).read()
     msg = emailmessage.EmailMessage( email, replace_mail_date=False )
     msg = emailmessage.EmailMessage( email, msg.get('x-gsgroup-title',''), msg.get('x-gsgroup-id',''), msg.get('x-gssite-id', ''), lambda x: msg.get('x-gsuser-id', ''), replace_mail_date=False)
     msgstorage = IRDBStorageForEmailMessage( msg )
     if not dryRun:
         msgstorage.set_zalchemy_adaptor( alchemy_adaptor )
     try:
         if not dryRun:
             msgstorage.insert()
             msgstorage.insert_keyword_count()
             msgstorage.insert_legacy_id()
         sys.stdout.write('.')
     except SQLError, x:
         sys.stdout.write('e')
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
         sys.stdout.write('\niters: %s, %s per iter\n' % (count, (time.time()-top)/float(count)))

sys.stdout.write('\ntook %s\n' % (time.time()-top))         

