# CHANGE THESE
DBHOSTNAME='localhost'
DBPORT=5432
DBUSERNAME='gstest'
DBPASSWORD=''
DBNAME='gstestdb'

PATH_TO_INSTANCE='/example/'
GROUP_TITLE='mythtvnz'
GROUP_ID='mythtvnz'
SITE_ID='mythtvnz'

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
from Products.GSProfile.utils import create_user_from_email
import transaction

import difflib, sqlalchemy
import time, gzip, re, sys

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

gsInstance = app.unrestrictedTraverse(PATH_TO_INSTANCE)

sys.stdout.write("importing from: '%s'\n" % IMPORT_DIR)
sys.stdout.write("logging to: '%s'" % LOG_FILE)

if not dryRun:
    alchemy_adaptor = app.unrestrictedTraverse(os.path.join(PATH_TO_INSTANCE,
                                                            'zsqlalchemy'))
    
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
    
    createdUserEmails = {}
    count = 0
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
        
        sender = msg.sender.encode('utf-8')
        if sender not in createdUserEmails:
            try:
                user = create_user_from_email(gsInstance,
                                              sender)
                user_id = user.getId()
                sys.stdout.write('c')
                transaction.commit()
                createdUserEmails[sender] = user_id
            except AssertionError:
                user = gsInstance.acl_users.get_userByEmail(sender)
                try:
                    user_id = user.getId()
                except:
                    sys.stdout.write('%s' % sender)
                    raise
        else:
            user_id = createdUserEmails[sender]
            
        msg = emailmessage.EmailMessage( email,
                                         GROUP_TITLE,
                                         GROUP_ID,
                                         SITE_ID,
                                         lambda x: user_id,
                                         replace_mail_date=False)
        
        msgstorage = IRDBStorageForEmailMessage( msg )
        if not dryRun:
            msgstorage.set_zalchemy_adaptor( alchemy_adaptor )
            
        try:
            if not dryRun:
                msgstorage.insert()
                msgstorage.insert_keyword_count()
            sys.stdout.write('.')
        except SQLError, x:
            sys.stdout.write('e')
            log.write("---------START---------\n")
            log.write('%s: %s\n' % (msg.get('x-gsoriginal-id'), str(x.orig)))
            r = postTable.select( postTable.c.post_id==msg.post_id ).execute()
            row = r.fetchone()
            if row:
                log.write("===POSSIBLE DUPLICATE DETAILS, POST ID %s===\n\n" % msg.post_id)
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
                log.write("===UNKNOWN ERROR, POST ID %s===\nn" % msg.post_id)
                log.write("%s\n\n" % msg.headers.encode('utf-8'))
                log.write("%s\n" % msg.body.encode('utf-8'))
                log.write("---------END--------\n")
            log.flush()
        except Exception, x:
            sys.stdout.write('e')
            log.write("---------START---------\n")
            log.write(str(x).decode('utf-8')+u'\n')
            log.write("---------END--------\n")
        
        sys.stdout.flush()
        count += 1

    return count

mfiles = os.listdir(IMPORT_DIR)
mfiles.sort()
for mfile in mfiles:
    top = time.time()
    sys.stdout.write('processing %s\n' % mfile)
    mbox = PortableUnixMailbox(gzip.open(os.path.join(IMPORT_DIR, mfile)))
    count = import_mbox(mbox)
    bottom = time.time()
    sys.stdout.write('\ntook %.2fs to import %s messages, %.0fms per message\n\n' % ((bottom-top), count, (((bottom-top)/count)*1000.0)))

