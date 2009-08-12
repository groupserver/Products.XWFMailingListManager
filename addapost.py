# coding=utf-8
from email.Encoders import encode_base64
from email.MIMENonMultipart import MIMENonMultipart
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText 
from mimetypes import MimeTypes

from zope.component import createObject, getMultiAdapter
from zExceptions import BadRequest
from sqlalchemy.exceptions import SQLError

from queries import MessageQuery
from MailBoxerTools import lowerList
from Products.GSGroupMember.interfaces import IGSPostingUser

from logging import getLogger
log = getLogger('addapost')
from webpostaudit import WebPostAuditor, POST

from Products.XWFCore.XWFUtils import getOption, \
  removePathsFromFilenames
def tagProcess(tagsString):
    # --=mpj17=-- Not the most elegant function, but I did not want to
    #   use the regular-expression library.
    retval = []

    if len(tagsString) == 0:
        return retval

    if ',' in tagsString:
        retval = tagsString.split(',')
    else:
        tags = tagsString
        if (('"' in tags) and (tags.count('"') % 2 == 0)):
            newTags = ''
            inQuote = False
            for c in tags:
                if (c == '"') and (not inQuote):
                    inQuote = True
                elif (c == '"') and (inQuote):
                    inQuote = False
                elif (c == ' ') and inQuote:
                    newTags += '_'
                else:
                    newTags += c
                    tags = newTags

        tagsList = tags.split(' ')
        for tag in tagsList:
            retval.append(tag.replace('_', ' '))
    
    return map(lambda t: t.strip(), filter(lambda t: t!='', retval))

def add_a_post(groupId, siteId, replyToId, topic, message,
               tags, email, uploadedFiles, context, request):
    
    result = {
      'error': False,
      'message': u"Message posted.",
      'id': u''}

    site_root = context.site_root()
    assert site_root
    userInfo = createObject('groupserver.LoggedInUser', context)

    siteObj = getattr(site_root.Content, siteId)
    groupObj = getattr(siteObj.groups, groupId)
    
    messages = getattr(groupObj, 'messages')
    assert messages
    listManager = messages.get_xwfMailingListManager()
    assert listManager
    groupList = getattr(listManager, groupObj.getId())
    assert groupList

    audit = WebPostAuditor(groupObj)
    audit.info(POST, topic)

    # Step 1, check if the user can post
    userPostingInfo = getMultiAdapter((groupObj, userInfo), 
                                       IGSPostingUser)
    if not userPostingInfo.canPost:
        raise 'Forbidden', userPostingInfo.status

    # --=mpj17-- Bless WebKit. It adds a file, even when no file has
    #   been specified; if the files are empty, do not add the files.
    uploadedFiles = [f for f in uploadedFiles if f]
    # Step 2, Create the message
    # Step 2.1 Body
    message = message.encode('utf-8')
    if uploadedFiles:
        msg = MIMEMultipart()
        msgBody = MIMEText(message, 'plain', 'utf-8') # As God intended.
        msg.attach(msgBody)
    else:
        msg = MIMEText(message, 'plain', 'utf-8')
    # Step 2.2 Headers
    # msg['To'] set below
    # TODO: Add the user's name. The Header class will be needed
    #   to ensure it is escaped properly.
    msg['From'] = email
    msg['Subject'] = topic
    tagsList = tagProcess(tags)
    tagsString = ', '.join(tagsList)
    if tagsString:
        msg['Keywords'] = tagsString
    if replyToId:
        msg['In-Reply-To'] = replyToId
    # msg['Reply-To'] set by the list
            
    # Step 2.3 Attachments
    for f in uploadedFiles:
        # --=mpj17=-- zope.formlib has already read the data, so we
        #   seek to the beginning to read it all again :)
        f.seek(0)
        data = f.read()
        if data:
            t = f.headers.getheader('Content-Type', 
                                    'application/octet-stream')
            mimePart = MIMENonMultipart(*t.split('/'))
            mimePart.set_payload(data)
            mimePart['Content-Disposition'] = 'attachment'
            filename = removePathsFromFilenames(f.filename)
            mimePart.set_param('filename', filename, 
                               'Content-Disposition')              
            encode_base64(mimePart) # Solves a lot of problems.
            msg.attach(mimePart)
            
    # Step 3, check the moderation. 
    # --=mpj17=-- This changes *how* we send the message to the 
    #   mailing list. No, really.
    via_mailserver = False
    moderatedlist = groupList.get_moderatedUserObjects(ids_only=True)
    moderated = groupList.getValueFor('moderated')
    # --=rrw=--if we are moderated _and_ we have a moderatedlist, only
    # users in the moderated list are moderated
    if moderated and moderatedlist and (userInfo.id in moderatedlist):
        log.warn('User "%s" posted from web while moderated' % 
              userInfo.id)
        via_mailserver = True
    # --=rrw=-- otherwise if we are moderated, everyone is moderated
    elif moderated and not(moderatedlist):
        log.warn('User "%s" posted from web while moderated' % userInfo.id)
        via_mailserver = True
    
    errorM = u'The post was not added to the topic '\
      u'<code class="topic">%s</code> because a post with the same '\
      u'body already exists in the topic.' % topic
    
    # Step 4, send the message.
    for list_id in messages.getProperty('xwf_mailing_list_ids', []):
        curr_list = listManager.get_list(list_id)
        msg['To'] = curr_list.getValueFor('mailto')
        
        if via_mailserver:
            # If the message is being moderated, we have to emulate
            #   a post via email so it can go through the moderation
            #   subsystem.
            mailto = curr_list.getValueFor('mailto')
            try:
                listManager.MailHost._send(mfrom=email,
                                           mto=mailto,
                                           messageText=msg.as_string())
            except BadRequest, e:
                result['error'] = True
                result['message'] = errorM
                log.error(e)
                break
            except SQLError, e:
                result['error'] = True
                result['message'] = errorM
                log.error(e)
                break
            result['error'] = True
            result['message'] = u'Your message has been sent to '\
              'the moderators for approval.'
            break
        else:
            # Send the message directly to the mailing list because
            #   it is not moderated
            try:
                request = {'Mail': msg.as_string()}
                r = groupList.manage_listboxer(request)
                result['message'] = \
                  u'<a href="/r/topic/%s#post-%s">Message '\
                  u'posted.</a>' % (r, r)
                # --=mpj17=-- The reason that I rewrite the result,
                # rather than doing a redirect, is the database may
                # not contain the post yet, so we have nowhere to
                # redirect to. The few seconds it will take the user
                # to click on the link should be fine: a race 
                # condition :)
            except BadRequest, e:
                result['error'] = True
                result['message'] = errorM
                log.error(e)
                break
            if (not r):
                # --=mpj17=-- This could be lies.
                result['error'] = True
                result['message'] = errorM
                break
    return result

