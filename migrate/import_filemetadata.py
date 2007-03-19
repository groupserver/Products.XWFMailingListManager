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
import sqlalchemy
import csv
     
filemetadata_csv = file(sys.argv[1])
filegroup_csv = file(sys.argv[2])

fmetadata = {}
for fid, mtype, title, size, date in csv.reader(filemetadata_csv):
    fmetadata[fid] = (mtype, title, size, date)

fmetadata_out = []
for items in csv.reader(filegroup_csv):
    topic_id = items[0]
    post_id = items[1]
    fileids = items[2:]
    if isinstance(fileids, str):
        fileids = [fileids]
    for fid in fileids:
        try:
            mdata = fmetadata[fid]
            fmetadata_out.append((fid, topic_id, post_id, mdata[0], mdata[1], mdata[2], mdata[3]))
        except:
            print 'no such file %s' % fid

session = alchemy_adaptor.getSession()
metadata = session.getMetaData()
and_ = sqlalchemy.and_; or_ = sqlalchemy.or_
fileTable = sqlalchemy.Table('file', metadata, autoload=True)
postTable = sqlalchemy.Table('post', metadata, autoload=True)

for fid, topic_id, post_id, mtype, title, size, date in fmetadata_out:
    i = fileTable.insert()
    i.execute(file_id=fid,
              mime_type=mtype,
              file_name=title,
              file_size=size,
              date=date,
              post_id=post_id,
              topic_id=topic_id)
    
    postTable.update(postTable.c.post_id == post_id).execute(has_attachments=True)
            
print fmetadata_out
