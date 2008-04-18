from Products.PythonScripts.standard import html_quote
from zLOG import LOG, WARNING, PROBLEM, INFO
from zExceptions import BadRequest
from sqlalchemy.exceptions import SQLError
import queries

import logging
log = logging.getLogger('addapost')

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
               tags, email, uploadedFile, context, request):
    
    result = {'error': False, 'message': 'No errror'}

    tagsList = tagProcess(tags)
    tagsString = ', '.join(tagsList)

    site_root = context.site_root()
    assert site_root

    user = request.AUTHENTICATED_USER
    assert user

    siteObj = getattr(site_root.Content, siteId)
    groupObj = getattr(siteObj.groups, groupId)
    ptnCoachId = groupObj.getProperty('ptn_coach_id', '')
    canonicalHost = context.Scripts.get.option('canonicalHost',
                                                 'onlinegroups.net')

    host = context.Scripts.get.option('canonicalHost', 'onlinegroups.net')
    messages = getattr(groupObj, 'messages')
    assert messages
    
    da = context.zsqlalchemy 
    assert da, 'No data-adaptor found'
    messageQuery = queries.MessageQuery(context, da)
    
    files = getattr(groupObj, 'files')
    assert files
    listManager = messages.get_xwfMailingListManager()
    assert listManager
    groupList = getattr(listManager, groupObj.getId())
    assert groupList

    if replyToId:
        origEmail = messageQuery.post(replyToId)
        topic = origEmail['subject']
        subject = 'Re: %s'  % topic
        emailMessageReplyToId = replyToId
        # --=mpj17=-- I should really handle the References header here.
    else:
        subject = topic
        emailMessageReplyToId = ''

    m = 'Adding post from %s (%s) via the Web, to the topic "%s" in %s '\
      '(%s) on %s (%s)'%\
      (user.getProperty('fn', ''), user.getId(), 
       topic, groupObj.title_or_id(), groupObj.getId(),
       siteObj.title_or_id(), siteObj.getId())
    log.info(m)

    # Step 1, check if the user is blocked
    blocked_members = groupList.getProperty('blocked_members')
    if blocked_members and user.getId() in blocked_members:
        message = 'Blocked user: %s from posting via web' % user.getId()
        LOG('XWFVirtualMailingListArchive', PROBLEM, message)
        m = '''You are currently blocked from posting. Please contact 
        the group administrator'''
        raise 'Forbidden', m

    # Step 2, check the moderation
    moderatedlist = groupList.getValueFor('moderatedlist')
    moderated = groupList.getValueFor('moderated')
    via_mailserver = False
    # --=rrw=--if we are moderated _and_ we have a moderatedlist, only
    # users in the moderated list are moderated
    if moderated and moderatedlist:
        for address in user.get_emailAddresses():
            if address in moderatedlist:
                LOG('XWFVirtualMailingListArchive', INFO,
                    'User "%s" posted from web while moderated' % 
                     user.getId())
                via_mailserver = True
                break
    # --=rrw=-- otherwise if we are moderated, everyone is moderated
    elif moderated:
        LOG('XWFVirtualMailingListArchive', INFO,
            'User "%s" posted from web while moderated' % user.getId())
        via_mailserver = True

    # Step 3, Create the file object, if necessary
    fileObj = None
    if uploadedFile:
        fileProperties = {'topic': topic,
                          'tags': tagsString,
                          'dc_creator': user.getId(),
                          'description': message[:200]}
        fileObj = files.add_file(uploadedFile, fileProperties)

    # Step 3, Get the templates
    templateDir = site_root.Templates.email.notifications.new_file
    assert templateDir, 'No template folder %s' % templateDir
    assert templateDir.message
    messageTemplate = templateDir.message

    result = {}
    result['error'] = False
    result['message'] = "Message posted."
    errorM = u'The post was not added to the topic '\
      u'<code class="topic">%s</code> because a post already exists in '\
      u'the topic with the same body.' % subject
    for list_id in messages.getProperty('xwf_mailing_list_ids', []):
        curr_list = listManager.get_list(list_id)
        m = messageTemplate(request, list_object=curr_list,
                            user=user, from_addr=email,
                            subject=subject, tags=tagsString,
                            canonicalHost=canonicalHost,
                            group=groupObj, ptn_coach_id=ptnCoachId,
                            message=message,
                            reply_to_id=emailMessageReplyToId,
                            n_type='new_file', n_id=groupObj.getId(),
                            file=fileObj)

        if via_mailserver:
            # If the message is being moderated, we have to emulate
            #   a post via email so it can go through the moderation
            #   subsystem.
            mailto = curr_list.getValueFor('mailto')
            try:
                listManager.MailHost._send(mfrom=email,
                                           mto=mailto,
                                           messageText=m)
            except BadRequest, e:
                result['error'] = True
                result['message'] = errorM
                break
            except SQLError, e:
                result['error'] = True
                result['message'] = errorM
                break
        else:
            try:
                # TODO: Complelely rewrite message handling so we actually
                #       have a vague idea what is going on.
                r = (groupList.manage_listboxer({'Mail': m}) != 'FALSE')
                # --=mpj17=-- I kid you not, the above code is legit.
                #   Too legit. Too legit to quit.
            except BadRequest, e:
                result['error'] = True
                result['message'] = errorM
                break
            if (not r):
                # This could be lies.
                result['error'] = True
                result['message'] = errorM
                break
    return result

