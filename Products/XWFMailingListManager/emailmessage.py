# -*- coding: utf-8 -*-
############################################################################
#
# Copyright © 2013, 2014, 2015 OnlineGroups.net and Contributors.
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
try:
    from hashlib import md5
except:
    from md5 import md5  # lint:ok
import logging
log = logging.getLogger('Products.XWFMailingListManager.emailmessage')
import time
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from zope.sqlalchemy import mark_changed
from zope.interface import implements
from gs.database import getSession, getTable
from .interfaces import IRDBStorageForEmailMessage


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
            # for each file, get the metadata and insert it into our RDB
            # table
            attachedFile = storage.get_file(fid)
            i = self.fileTable.insert()
            d = {
                'file_id': fid,
                'mime_type': attachedFile.getProperty('content_type', ''),
                'file_name': attachedFile.getProperty('title', ''),
                'file_size': getattr(attachedFile, 'size', 0),
                'date': self.email_message.date,
                'post_id': self.email_message.post_id,
                'topic_id': self.email_message.topic_id, }
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
            hasAttachments = bool(self.email_message.attachment_count)
            p = {
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
                'has_attachments': hasAttachments, }
            session.execute(i, params=p)
        except SQLAlchemyError as se:
            log.warn(se)
            m = "Post id %s already existed in database. This should be"\
                "changed changed to raise a specific error to the UI."
            log.warn(m % self.email_message.post_id)
            session.rollback()
            m = "Post %s already existed in database."
            raise DuplicateMessageError(m % self.email_message.post_id)

        #
        # add/update the topic
        #
        topic = self._get_topic()
        if not topic:
            i = self.topicTable.insert()
            try:
                session.execute(i, params={
                    'topic_id': self.email_message.topic_id,
                    'group_id': self.email_message.group_id,
                    'site_id': self.email_message.site_id,
                    'original_subject': self.email_message.subject,
                    'first_post_id': self.email_message.post_id,
                    'last_post_id': self.email_message.post_id,
                    'last_post_date': self.email_message.date,
                    'num_posts': 1})
            except SQLAlchemyError as se:
                log.warn(se)
                m = 'Topic id "{0}" already existed in database. This '\
                    'should be changed to raise a specific error to the UI.'
                log.warn(m.format(self.email_message.topic_id))
                session.rollback()

                m = 'Topic "{0}" already existed in database.'
                msg = m.format(self.email_message.topic_id)
                raise DuplicateMessageError(msg)
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

            uselect = and_(
                self.topicTable.c.topic_id == self.email_message.topic_id,
                self.topicTable.c.group_id == self.email_message.group_id,
                self.topicTable.c.site_id == self.email_message.site_id)
            u = self.topicTable.update(uselect)
            session.execute(u, params={'num_posts': num_posts + 1,
                                       'last_post_id': last_post_id,
                                       'last_post_date': last_post_date})
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
