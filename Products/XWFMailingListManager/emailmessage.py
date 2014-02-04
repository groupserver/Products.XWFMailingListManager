# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright © 2014 OnlineGroups.net and Contributors.
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
from __future__ import absolute_import, unicode_literals
import codecs
import datetime
from email import Parser, Header
try:
    from hashlib import md5
except:
    from md5 import md5  # lint:ok
import re
from rfc822 import AddressList
import string
import time
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from zope.cachedescriptors.property import Lazy
from zope.datetime import parseDatetimetz
from zope.sqlalchemy import mark_changed
from zope.interface import Interface, Attribute, implements
from gs.database import getSession, getTable
from .html2txt import convert_to_txt

import logging
log = logging.getLogger('Products.XWFMailingListManager.emailmessage')


def convert_int2b(num, alphabet, converted=[]):
    mod = num % len(alphabet)
    rem = num / len(alphabet)
    converted.append(alphabet[mod])
    if rem:
        return convert_int2b(rem, alphabet, converted)
    converted.reverse()
    return ''.join(converted)


def convert_int2b62(num):
    alphabet = string.printable[:62]
    return convert_int2b(num, alphabet, [])


def parse_disposition(s):
    matchObj = re.search('(?i)filename="*(?P<filename>[^"]*)"*', s)
    name = ''
    if matchObj:
        name = matchObj.group('filename')
    return name

reRegexp = re.compile('re:', re.IGNORECASE)
fwRegexp = re.compile('fw:', re.IGNORECASE)
fwdRegexp = re.compile('fwd:', re.IGNORECASE)
# See <http://www.w3.org/TR/unicode-xml/#Suitable>
uParaRegexep = re.compile(u'[\u2028\u2029]+')
annoyingChars = string.whitespace + u'\uFFF9\uFFFA\uFFFB\uFFFC\uFEFF'
annoyingCharsL = annoyingChars + u'\u202A\u202D'
annoyingCharsR = annoyingChars + u'\u202B\u202E'


def strip_subject(subject, list_title, remove_re=True):
    """ A helper function for tidying the subject line.

    """
    # remove the list title from the subject, if it isn't just an empty string
    if list_title:
        subject = re.sub('\[%s\]' % re.escape(list_title), '', subject).strip()

    subject = uParaRegexep.sub(' ', subject)
    # compress up the whitespace into a single space
    subject = re.sub('\s+', ' ', subject).strip()
    if remove_re:
        # remove the "re:" from the subject line. There are probably other
        # variants we don't yet handle.
        subject = reRegexp.sub('', subject)
        subject = fwRegexp.sub('', subject)
        subject = fwdRegexp.sub('', subject)
        subject = subject.lstrip(annoyingCharsL + '[')
        subject = subject.rstrip(annoyingCharsR + ']')
    else:
        subject = subject.lstrip(annoyingCharsL)
        subject = subject.rstrip(annoyingCharsR)
    if len(subject) == 0:
        subject = 'No Subject'
    return subject


def normalise_subject(subject):
    """Compress whitespace and lower-case subject"""
    return re.sub('\s+', '', subject).lower()


def calculate_file_id(file_body, mime_type):
    #
    # Two files will have the same ID if
    # - They have the same MD5 Sum, and
    # - They have the same length, and
    # - They have the same MIME-type.
    #
    length = len(file_body)
    md5_sum = md5()
    for c in file_body:
        md5_sum.update(c)
    file_md5 = md5_sum.hexdigest()
    md5_sum.update(':' + str(length) + ':' + mime_type)
    return (unicode(convert_int2b62(long(md5_sum.hexdigest(), 16))),
            length, file_md5)


class IRDBStorageForEmailMessage(Interface):
    pass


class DuplicateMessageError(Exception):
    pass


class RDBFileMetadataStorage(object):
    def __init__(self, context, email_message, file_ids):
        self.context = context
        self.email_message = email_message
        self.file_ids = file_ids
        self.fileTable = getTable('file')
        self.postTable = getTable('post')

    def insert(self):
        # FIXME: references like this should *NOT* be hardcoded!
        storage = self.context.FileLibrary2.get_fileStorage()
        session = getSession()
        for fid in self.file_ids:
            # for each file, get the metadata and insert it into our RDB table
            attachedFile = storage.get_file(fid)
            i = self.fileTable.insert()
            d = {'file_id': fid,
                  'mime_type': attachedFile.getProperty('content_type', ''),
                  'file_name': attachedFile.getProperty('title', ''),
                  'file_size': getattr(attachedFile, 'size', 0),
                  'date': self.email_message.date,
                  'post_id': self.email_message.post_id,
                  'topic_id': self.email_message.topic_id}
            session.execute(i, params=d)

        # set the flag on the post table to avoid lookups
        if self.file_ids:
            u = self.postTable.update(
                 self.postTable.c.post_id == self.email_message.post_id)
            session.execute(u, params={'has_attachments': True})
            mark_changed(session)


class RDBEmailMessageStorage(object):
    implements(IRDBStorageForEmailMessage)

    def __init__(self, email_message):
        self.email_message = email_message
        self.postTable = getTable('post')
        self.topicTable = getTable('topic')
        self.post_tagTable = getTable('post_tag')
        self.post_id_mapTable = getTable('post_id_map')

    def _get_topic(self):
        and_ = sa.and_

        s = self.topicTable.select(
           and_(self.topicTable.c.topic_id == self.email_message.topic_id,
                self.topicTable.c.group_id == self.email_message.group_id,
                self.topicTable.c.site_id == self.email_message.site_id))
        session = getSession()
        r = session.execute(s)

        return r.fetchone()

    def insert(self):
        and_ = sa.and_
        session = getSession()

        #
        # add the post itself
        #
        i = self.postTable.insert()
        try:
            session.execute(i, params={
                 'post_id': self.email_message.post_id,
                 'topic_id': self.email_message.topic_id,
                 'group_id': self.email_message.group_id,
                 'site_id': self.email_message.site_id,
                 'user_id': self.email_message.sender_id,
                 'in_reply_to': self.email_message.inreplyto,
                 'subject': self.email_message.subject,
                 'date': self.email_message.date,
                 'body': self.email_message.body,
                 'htmlbody': self.email_message.html_body,
                 'header': self.email_message.headers,
                 'has_attachments': bool(self.email_message.attachment_count)})
        except SQLAlchemyError as se:
            log.warn(se)
            log.warn("Post id %s already existed in database. This should be "
                     "changed to raise a specific error to the UI."
                    % self.email_message.post_id)
            session.rollback()

            raise DuplicateMessageError("Post %s already existed in database."
                    % self.email_message.post_id)

        #
        # add/update the topic
        #
        topic = self._get_topic()
        if not topic:
            i = self.topicTable.insert()
            session.execute(i, params={
                 'topic_id': self.email_message.topic_id,
                 'group_id': self.email_message.group_id,
                 'site_id': self.email_message.site_id,
                 'original_subject': self.email_message.subject,
                 'first_post_id': self.email_message.post_id,
                 'last_post_id': self.email_message.post_id,
                 'last_post_date': self.email_message.date,
                 'num_posts': 1})
        else:
            num_posts = topic['num_posts']
            # --=mpj17=-- Hypothesis: the following condition is
            # screwing up, and causing the Last Author to be bung.
            # Test: check the Last Post in topics where the last
            # author is bung.
            if (time.mktime(topic['last_post_date'].timetuple()) >
                time.mktime(self.email_message.date.timetuple())):
                last_post_date = topic['last_post_date']
                last_post_id = topic['last_post_id']
            else:
                last_post_date = self.email_message.date
                last_post_id = self.email_message.post_id

            u = self.topicTable.update(and_(
                 self.topicTable.c.topic_id == self.email_message.topic_id,
                 self.topicTable.c.group_id == self.email_message.group_id,
                 self.topicTable.c.site_id == self.email_message.site_id)
                )
            session.execute(u, params={'num_posts': num_posts + 1,
                                       'last_post_id': last_post_id,
                                       'last_post_date': last_post_date})
        #
        # add any tags we have for the post
        #
        i = self.post_tagTable.insert()
        for tag in self.email_message.tags:
            session.execute(i,
                    params={'post_id': self.email_message.post_id,
                            'tag': tag})
        mark_changed(session)

    def remove(self):
        session = getSession()
        topic = self._get_topic()
        if topic['num_posts'] == 1:
            d = self.topicTable.delete(
                  self.topicTable.c.topic_id == self.email_message.topic_id)
            session.execute(d)

        d = self.postTable.delete(
             self.postTable.c.post_id == self.email_message.post_id)
        session.execute(d)
        mark_changed(session)


class IEmailMessage(Interface):
    """ A representation of an email message.

    """
    post_id = Attribute("The unique ID for the post, based on attributes of "
                        "the message")
    topic_id = Attribute("The unique ID for the topic, based on attributes "
                        "of the message")

    encoding = Attribute("The encoding of the email and headers.")
    attachments = Attribute("A list of attachment payloads, each structured "
                            "as a dictionary, from the email (both body and "
                            "attachments).")
    body = Attribute("The plain text body of the email message.")
    html_body = Attribute("The html body of the email message, if one exists")
    subject = Attribute("Get the subject of the email message, stripped of "
                        "additional details (such as re:, and list title)")
    compressed_subject = Attribute("Get the compressed subject of the email "
                                  "message, with all whitespace removed.")

    sender_id = Attribute("The user ID of the message sender")
    headers = Attribute("A flattened version of the email headers")
    language = Attribute("The language in which the email has been composed")
    inreplyto = Attribute("The value of the inreplyto header if it exists")
    date = Attribute("The date on which the email was sent")
    md5_body = Attribute("An md5 checksum of the plain text body of the email")

    to = Attribute("The email address the message was sent to")
    sender = Attribute("The email address the message was sent from")
    name = Attribute("The name of the sender, from the header. This is not "
                     "related to their name as set in GroupServer")
    title = Attribute("An attempt at a title for the email")
    tags = Attribute("A list of tags that describe the email")

    attachment_count = Attribute("A count of attachments which have a"
                                    "filename")

    def get(name, default):
        """ Get the value of a header, changed to unicode using the
            encoding of the email.

        @param name: identifier of header, eg. 'subject'
        @param default: default value, if header does not exist. Defaults to
            '' if left unspecified
        """


def check_encoding(encoding):
    # a slightly wierd encoding that isn't in the standard encoding table
    if encoding.lower() == 'macintosh':
        encoding = 'mac_roman'
    try:
        codecs.lookup(encoding)
    except:
        # play it pretty safe ... we're going to be ignoring errors in
        # the encoding anyway, and UTF-8 is going to be right more of the time
        # in the very, very rare case that we have to force this!
        encoding = 'utf-8'
    return encoding


class EmailMessage(object):
    implements(IEmailMessage)

    def __init__(self, message, list_title='', group_id='', site_id='',
                sender_id_cb=None, replace_mail_date=True):
        self._list_title = list_title
        self.group_id = group_id
        self.site_id = site_id
        self.sender_id_cb = sender_id_cb
        self.replace_mail_date = replace_mail_date
        # --=mpj17=-- self.message is not @Lazy, because it is mutable.
        parser = Parser.Parser()
        self.message = parser.parsestr(message)

    @Lazy
    def _date(self):
        retval = datetime.datetime.now()
        return retval

    def get(self, name, default=''):
        value = self.message.get(name, default)
        header_parts = []
        for value, encoding in Header.decode_header(value):
            encoding = check_encoding(encoding) if encoding else self.encoding
            header_parts.append(unicode(value, encoding, 'ignore'))

        return ' '.join(header_parts)

    @Lazy
    def sender_id(self):
        retval = ''
        if self.sender_id_cb:
            retval = self.sender_id_cb(self.sender)

        return retval

    @Lazy
    def encoding(self):
        encoding = check_encoding(self.message.get_param('charset', 'utf-8'))
        return encoding

    @Lazy
    def attachments(self):
        def split_multipart(msg, pl):
            if msg.is_multipart():
                for b in msg.get_payload():
                    pl = split_multipart(b, pl)
            else:
                pl.append(msg)

            return pl

        retval = []
        payload = self.message.get_payload()
        if isinstance(payload, list):
            outmessages = []
            for i in payload:
                outmessages = split_multipart(i, outmessages)

            for msg in outmessages:
                actual_payload = msg.get_payload(decode=True)
                encoding = msg.get_param('charset', self.encoding)
                pd = parse_disposition(msg.get('content-disposition', ''))
                filename = unicode(pd, encoding, 'ignore') if pd else ''
                fileid, length, md5_sum = calculate_file_id(actual_payload,
                                                    msg.get_content_type())
                retval.append({
                      'payload': actual_payload,
                      'fileid': fileid,
                      'filename': filename,
                      'length': length,
                      'md5': md5_sum,
                      'charset': encoding,  # --=mpj17=-- Issues?
                      'maintype': msg.get_content_maintype(),
                      'subtype': msg.get_content_subtype(),
                      'mimetype': msg.get_content_type(),
                      'contentid': msg.get('content-id', '')})
        else:
            # Since we aren't a bunch of attachments, actually decode the
            #   body
            payload = self.message.get_payload(decode=True)
            cd = self.message.get('content-disposition', '')
            pd = parse_disposition(cd)
            filename = unicode(pd, self.encoding, 'ignore') if pd else ''

            fileid, length, md5_sum = calculate_file_id(payload,
                                        self.message.get_content_type())
            retval = [{
                      'payload': payload,
                      'md5': md5_sum,
                      'fileid': fileid,
                      'filename': filename,
                      'length': length,
                      'charset': self.message.get_charset(),
                      'maintype': self.message.get_content_maintype(),
                      'subtype': self.message.get_content_subtype(),
                      'mimetype': self.message.get_content_type(),
                      'contentid': self.message.get('content-id', '')}]
        assert retval is not None
        assert type(retval) == list
        return retval

    @property
    def headers(self):
        # --=mpj17=-- Not @Lazy because self.message. changes.
        # return a flattened version of the headers
        header_string = '\n'.join(map(lambda x: '%s: %s' % (x[0], x[1]),
                                        self.message._headers))

        if not isinstance(header_string, unicode):
            header_string = unicode(header_string, self.encoding, 'ignore')

        return header_string

    @Lazy
    def attachment_count(self):
        count = 0
        for item in self.attachments:
            if item['filename']:
                count += 1
        return count

    @Lazy
    def language(self):
        # one day we might want to detect languages, primarily this
        # will be used for stemming, stopwords and search
        return 'en'

    @Lazy
    def body(self):
        retval = ''
        for item in self.attachments:
            if item['filename'] == '' and item['subtype'] != 'html':
                retval = unicode(item['payload'], self.encoding,
                                        'ignore')
                break
        html_body = self.html_body
        if html_body and (not retval):
            h = html_body.encode(self.encoding, 'xmlcharrefreplace')
            retval = convert_to_txt(h)
        assert retval is not None
        assert type(retval) == unicode
        return retval

    @Lazy
    def html_body(self):
        for item in self.attachments:
            if item['filename'] == '' and item['subtype'] == 'html':
                return unicode(item['payload'], self.encoding, 'ignore')
        return ''

    @Lazy
    def subject(self):
        retval = strip_subject(self.get('subject'), self._list_title)
        return retval

    @Lazy
    def compressed_subject(self):
        return normalise_subject(self.subject)

    @Lazy
    def sender(self):
        sender = self.get('from')
        if sender:
            name, sender = AddressList(sender)[0]
            sender = sender.lower()
        return sender

    @Lazy
    def name(self):
        sender = self.get('from')
        retval = ''
        if sender:
            retval, sender = AddressList(sender)[0]
        return retval

    @Lazy
    def to(self):
        to = self.get('to')
        if to:
            name, to = AddressList(to)[0]
            to = to.lower()
        # --=mpj17=-- TODO: Add the group name.
        return to

    @Lazy
    def title(self):
        return '%s / %s' % (self.subject, self.sender)

    @Lazy
    def inreplyto(self):
        return self.get('in-reply-to')

    @Lazy
    def date(self):
        if self.replace_mail_date:
            return self._date
        d = self.get('date', '').strip()
        if d:
            # if we have the format Sat, 10 Mar 2007 22:47:20 +1300 (NZDT)
            # strip the (NZDT) bit before parsing, otherwise we break the
            # parser
            d = re.sub(' \(.*?\)', '', d)
            return parseDatetimetz(d)
        return self._date

    @Lazy
    def md5_body(self):
        retval = md5(self.body.encode('utf-8')).hexdigest()
        return retval

    @Lazy
    def topic_id(self):
        # this is calculated from what we have/know

        # A topic_id for two posts will clash if
        #   - The compressedsubject, group ID and site ID are all identical
        items = self.compressed_subject + ':' + self.group_id + ':' + \
                self.site_id
        tid = md5(items.encode('utf-8')).hexdigest()

        return unicode(convert_int2b62(long(tid, 16)))

    @Lazy
    def tags(self):
        # Deprecated
        return []

    @Lazy
    def post_id(self):
        # this is calculated from what we have/know
        len_payloads = sum([x['length'] for x in self.attachments])

        # A post_id for two posts will clash if
        #    - The topic IDs are the same, and
        #    - The subject is the same (this may not be the same as
        #      compressed subject used in topic id)
        #    - The body of the posts are the same, and
        #    - The posts are from the same author, and
        #    - The posts respond to the same message, and
        #    - The posts have the same length of attachments.
        items = (self.topic_id + ':' + self.subject + ':' +
                  self.md5_body + ':' + self.sender + ':' +
                  self.inreplyto + ':' + str(len_payloads))
        pid = md5(items.encode('utf-8')).hexdigest()
        retval = unicode(convert_int2b62(long(pid, 16)))
        return retval
