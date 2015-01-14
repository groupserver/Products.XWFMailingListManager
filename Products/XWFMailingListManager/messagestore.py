# -*- coding: utf-8 -*-
############################################################################
#
# Copyright © 2015 OnlineGroups.net and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
############################################################################
from __future__ import absolute_import, unicode_literals
from datetime import datetime
try:  # Python 2
    from hashlib import md5
    INT = long
except:  # Python 3
    from md5 import md5  # lint:ok
    INT = int
import re
from zope.cachedescriptors.property import Lazy
from zope.datetime import parseDatetimetz
from gs.core import to_unicode_or_bust, convert_int2b62
from gs.group.list.base import EmailMessage


class EmailMessageStore(EmailMessage):

    def __init__(self, message, list_title='', group_id='', site_id='',
                 sender_id_cb=None, replace_mail_date=True):
        super(EmailMessageStore, self).__init__(
            message, list_title, group_id, site_id, sender_id_cb)
        self._list_title = list_title
        self.replace_mail_date = replace_mail_date

    @classmethod
    def from_email_message(cls, emailMessage, replaceMailDate=True):
        retval = cls(emailMessage.message, emailMessage.list_title,
                     emailMessage.group_id, emailMessage.site_id,
                     emailMessage.sender_id_cb, replaceMailDate)
        return retval

    @staticmethod
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
        vNum = convert_int2b62(INT(md5_sum.hexdigest(), 16))
        retval = (to_unicode_or_bust(vNum), length, file_md5)
        return retval

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
                pd = self.parse_disposition(msg.get('content-disposition',
                                                    ''))
                filename = to_unicode_or_bust(pd, encoding) if pd else ''
                fileid, length, md5_sum = self.calculate_file_id(
                    actual_payload, msg.get_content_type())
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
            pd = self.parse_disposition(cd)
            filename = to_unicode_or_bust(pd, self.encoding) if pd else ''

            fileid, length, md5_sum = self.calculate_file_id(
                payload, self.message.get_content_type())
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

    @Lazy
    def attachment_count(self):
        count = 0
        for item in self.attachments:
            if item['filename']:
                count += 1
        return count

    @Lazy
    def html_body(self):
        for item in self.attachments:
            if item['filename'] == '' and item['subtype'] == 'html':
                return to_unicode_or_bust(item['payload'], self.encoding)
        return ''

    @Lazy
    def date(self):
        retval = datetime.now()
        d = self.get('date', '').strip()
        if d and not self.replace_mail_date:
            # if we have the format Sat, 10 Mar 2007 22:47:20 +1300 (NZDT)
            # strip the (NZDT) bit before parsing, otherwise we break the
            # parser
            d = re.sub(' \(.*?\)', '', d)
            retval = parseDatetimetz(d)
        assert retval
        return retval


def store_from_message(message):
    'For the ZCML, which really does not like class methods.'
    return EmailMessageStore.from_email_message(message)
