# CHANGE THESE
DBHOSTNAME='localhost'
DBPORT=5432
DBUSERNAME='gstest'
DBPASSWORD=''
DBNAME='gstestdb'

IMPORT_DIR='/home/richard/Workspace/groupserver-1.0beta/src/Products.XWFMailingListManager/Products/XWFMailingListManager/migrate/archives/'
LOG_FILE='/home/richard/foo.out'

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
import gzip
import re

from mailbox import PortableUnixMailbox

app = base.app()

zcml.load_config('meta.zcml', Products.Five)
zcml.load_config('permissions.zcml', Products.Five)
zcml.load_config('configure.zcml', Products.XWFMailingListManager)

startPos = os.environ.get('START_POS', '')
try:
    dryRun = int(os.environ.get('DRY_RUN', '')) and True or False
except:
    dryRun = False

print "importing from: '%s'" % IMPORT_DIR
print "logging to: '%s'" % LOG_FILE

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

log = file(LOG_FILE, 'a+')

def import_mbox(mbox):
    frommask = ' at '

    for message in mbox:
        header = ''
        i = 0
        for h in message.headers:
            if h[:5].lower() == 'from:':
                h = h.replace(frommask, '@')
                message.headers[i] = h
                break
            i += 1
    
        email = str(message)
        email += '\n'
        email += message.fp.read()
    
        msg = emailmessage.EmailMessage( email, replace_mail_date=False )
        
        msg = emailmessage.EmailMessage( email, msg.get('x-gsgroup-title',''),
                                         msg.get('x-gsgroup-id',''),
                                         msg.get('x-gssite-id', ''),
                                         lambda x: msg.get('x-gsuser-id', ''),
                                         replace_mail_date=False)
        
        msgstorage = IRDBStorageForEmailMessage( msg )
        if not dryRun:
            msgstorage.set_zalchemy_adaptor( alchemy_adaptor )
            
        try:
            if not dryRun:
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
        except Exception, x:
            print 'e',
            log.write("---------START---------\n")
            log.write(str(x).decode('utf-8')+u'\n')
            log.write("---------END--------\n")
            

for mfile in os.listdir(IMPORT_DIR):
    mbox = PortableUnixMailbox(gzip.open(os.path.join(IMPORT_DIR, mfile)))
    import_mbox(mbox)

