# -*- coding: utf-8 *-*
from sqlalchemy.exc import NoSuchTableError
import sqlalchemy as sa
from gs.database import getTable, getSession
from querydigest import DigestQuery  # lint:ok
from querymember import MemberQuery  # lint:ok


def to_unicode(s):
    retval = s
    if not isinstance(s, unicode):
        retval = unicode(s, 'utf-8')
    return retval


def summary(s):
    if not isinstance(s, unicode):
        s = unicode(s, 'utf-8')
    return s[:160]


class MessageQuery(object):
    def __init__(self, context):
        self.context = context

        self.topicTable = getTable('topic')
        self.topicKeywordsTable = getTable('topic_keywords')
        self.postTable = getTable('post')
        self.fileTable = getTable('file')

        try:
            self.post_id_mapTable = getTable('post_id_map')
        except NoSuchTableError:
            self.post_id_mapTable = None

    def __add_std_where_clauses(self, statement, table,
                                       site_id, group_ids=[]):
        '''Add the standard "where" clauses to an SQL statement

        DESCRIPTION
            It is very common to only search a table for an
            object from a particular set of groups, on a particular site.
            This method add the appropriate where-clauses to do this.

        ARGUMENTS
            "statement":  An SQL statement.
            "site_id":    The IS for the site that is being searched.
            "group_ids":  A list of IDs of the groups that are being
                          searched.
        RETURNS
            The SQL statement, with the site-restrection and group
            restrictions appended to the "WHERE" clause.

        SIDE EFFECTS
        '''
        statement.append_whereclause(table.c.site_id == site_id)
        if group_ids:
            inStatement = table.c.group_id.in_(group_ids)
            statement.append_whereclause(inStatement)
        return statement

    def marshal_topic(self, x):
        retval = {'topic_id': x['topic_id'],
                'site_id': x['site_id'],
                'group_id': x['group_id'],
                'subject': to_unicode(x['original_subject']),
                'keywords': x['keywords'],
                'first_post_id': x['first_post_id'],
                'last_post_id': x['last_post_id'],
                'count': x['num_posts'],
                'last_post_date': x['last_post_date']}
        assert retval
        return retval

    def marshall_post(self, x):
        return {'post_id': x['post_id'],
                'site_id': x['site_id'],
                'group_id': x['group_id'],
                'subject': to_unicode(x['subject']),
                'date': x['date'],
                'author_id': x['user_id'],
                'hidden': x['hidden'],
                'files_metadata': x['has_attachments']
                          and self.files_metadata(x['post_id']) or [],
                'body': to_unicode(x['body']),
                'summary': summary(x['body'])}

    def post_id_from_legacy_id(self, legacy_post_id):
        """ Given a legacy (pre-1.0) GS post_id, determine what the new
        post ID is, if we know.

        This is primarily used for backwards compatibility in the redirection
        system.

        """
        pit = self.post_id_mapTable
        if pit is None:
            return None

        statement = pit.select()

        statement.append_whereclause(pit.c.old_post_id == legacy_post_id)

        session = getSession()
        r = session.execute(statement)

        post_id = None
        if r.rowcount:
            result = r.fetchone()
            post_id = result['new_post_id']

        return post_id

    def topic_id_from_post_id(self, post_id):
        """ Given a post_id, determine which topic it came from.

        """
        pt = self.postTable
        statement = pt.select()
        statement.append_whereclause(pt.c.post_id == post_id)

        session = getSession()
        r = session.execute(statement)

        topic_id = None
        if r.rowcount:
            result = r.fetchone()
            topic_id = result['topic_id']

        return topic_id

    def latest_posts(self, site_id, group_ids=[], limit=None, offset=0):
        statement = self.postTable.select(limit=limit, offset=offset,
                                 order_by=sa.desc(self.postTable.c.date))
        self.__add_std_where_clauses(statement, self.postTable,
                                     site_id, group_ids)
        session = getSession()
        r = session.execute(statement)

        retval = []
        if r.rowcount:
            retval = [self.marshall_post(x) for x in r]

        return retval

    def post_count(self, site_id, group_ids=[]):
        statement = sa.select([sa.func.sum(self.topicTable.c.num_posts)])
        self.__add_std_where_clauses(statement, self.topicTable,
                                           site_id, group_ids)
        session = getSession()
        r = session.execute(statement)

        retval = r.scalar()
        if retval is None:
            retval = 0
        assert retval >= 0
        return retval

    def topic_count(self, site_id, group_ids=[]):
        statement = sa.select([sa.func.count(self.topicTable.c.topic_id)])
        self.__add_std_where_clauses(statement, self.topicTable,
                                     site_id, group_ids)
        session = getSession()
        r = session.execute(statement)

        retval = r.scalar()
        assert retval >= 0
        return retval

    def latest_topics(self, site_id, group_ids=[], limit=None, offset=0):
        """
            Returns:
             ({'topic_id': ID, 'subject': String, 'first_post_id': ID,
               'last_post_id': ID, 'count': Int, 'last_post_date': Date,
               'group_id': ID, 'site_id': ID}, ...)

        """
        tt = self.topicTable
        statement = tt.select(limit=limit, offset=offset,
                              order_by=sa.desc(tt.c.last_post_date))
        self.__add_std_where_clauses(statement, self.topicTable,
                                     site_id, group_ids)

        session = getSession()
        r = session.execute(statement)

        retval = []
        if r.rowcount:
            retval = [{self.marshal_topic(x)} for x in r]

        return retval

    def _nav_post(self, curr_post_id, direction, topic_id=None):
        op = direction == 'prev' and '<=' or '>='
        navDir = direction == 'prev' and 'desc' or 'asc'

        topic_id_filter = ''
        if topic_id:
            topic_id_filter = 'post.topic_id=curr_post.topic_id and'
        #FIXME: This should use :thingies: rather than %s
        s = sa.text("""select post.date, post.post_id, post.topic_id,
                       post.subject, post.user_id, post.has_attachments
                    from post,
                   (select date,group_id,site_id,post_id,topic_id from post
                   where
                post_id=:curr_post_id) as curr_post where
                post.group_id=curr_post.group_id and
                post.site_id=curr_post.site_id and
                post.date %s curr_post.date and
                %s
                post.post_id != curr_post.post_id
                order by post.date %s limit 1""" %
                    (op, topic_id_filter, navDir))

        session = getSession()
        d = {'curr_post_id': curr_post_id}
        r = session.execute(s, params=d).fetchone()
        if r:
            return {'post_id': r['post_id'],
                    'topic_id': r['topic_id'],
                    'subject': to_unicode(r['subject']),
                    'date': r['date'],
                    'author_id': r['user_id'],
                    'has_attachments': r['has_attachments']}
        return None

    def previous_post(self, curr_post_id):
        """ Find the post prior to the given post ID.

            Returns:
               {'post_id': ID, 'topic_id': ID, 'subject': String,
                'date': Date, 'author_id': String, 'has_attachments': Bool}
             or
                None

        """
        return self._nav_post(curr_post_id, 'prev')

    def next_post(self, curr_post_id):
        """ Find the post after the given post ID.

            Returns:
               {'post_id': ID, 'topic_id': ID, 'subject': String,
                'date': Date, 'author_id': String, 'has_attachments': Bool}
             or
                None

        """
        return self._nav_post(curr_post_id, 'next')

    def _nav_topic(self, curr_topic_id, direction):
        op = direction == 'prev' and '<=' or '>='
        dir_ = direction == 'prev' and 'desc' or 'asc'

        s = sa.text("""select topic.last_post_date as date,
                              topic.topic_id, topic.last_post_id,
                              topic.original_subject as subject
                    from topic,
                   (select topic_id,last_post_date as date,group_id,site_id
                    from topic where
                    topic_id=:curr_topic_id) as curr_topic where
                   topic.group_id=curr_topic.group_id and
                   topic.site_id=curr_topic.site_id and
                   topic.last_post_date %s curr_topic.date and
                   topic.topic_id != curr_topic.topic_id
                   order by date %s limit 1""" % (op, dir_))

        session = getSession()
        r = session.execute(s,
                            params={'curr_topic_id': curr_topic_id}).fetchone()
        if r:
            return {'topic_id': r['topic_id'],
                    'last_post_id': r['last_post_id'],
                    'subject': to_unicode(r['subject']),
                    'date': r['date']}
        return None

    def later_topic(self, curr_topic_id):
        """ Find the topic prior to the given topic ID.

            Returns:
               {'last_post_id': ID, 'topic_id': ID,
                'subject': String, 'date': Date}
             or
                None

        """
        return self._nav_topic(curr_topic_id, 'prev')

    def earlier_topic(self, curr_topic_id):
        """ Find the topic after the given topic ID.

            Returns:
               {'last_post_id': ID, 'topic_id': ID,
                'subject': String, 'date': Date}
             or
                None

        """
        return self._nav_topic(curr_topic_id, 'next')

    def topic_post_navigation(self, curr_post_id):
        """ Retrieve first/last, next/prev navigation relative to a post,
            within a topic.  Used for navigation of single posts *within* a
            topic, not for general post navigation.

            Returns:
                {'first_post_id': ID, 'last_post_id': ID,
                 'previous_post_id': ID, 'next_post_id': ID}

            ID may be None.

        """
        first_post_id = None
        last_post_id = None
        next_post_id = None
        previous_post_id = None

        tt = self.topicTable

        topic_id = self.topic_id_from_post_id(curr_post_id)

        if topic_id:
            statement = tt.select()

            statement.append_whereclause(tt.c.topic_id == topic_id)

            session = getSession()
            r = session.execute(statement)

            if r.rowcount:
                result = r.fetchone()

                first_post_id = result['first_post_id']
                last_post_id = result['last_post_id']

            r = self._nav_post(curr_post_id, 'next', topic_id)
            if r:
                assert r['topic_id'] == topic_id,\
                    "Topic ID should always match"
                next_post_id = r['post_id']

            r = self._nav_post(curr_post_id, 'prev', topic_id)
            if r:
                assert r['topic_id'] == topic_id,\
                    "Topic ID should always match"
                previous_post_id = r['post_id']
        retval = {'first_post_id': first_post_id,
                  'next_post_id': next_post_id,
                  'previous_post_id': previous_post_id,
                  'last_post_id': last_post_id}
        return retval

    def topic_posts(self, topic_id):
        """ Retrieve all the posts in a topic.

            Returns:
                ({'post_id': ID, 'subject': String,
                  'date': Date, 'author_id': ID,
                  'files_metadata': [Metadata],
                  'body': Text}, ...)
             or
                []

        """
        pt = self.postTable
        statement = pt.select(order_by=sa.asc(pt.c.date))
        statement.append_whereclause(pt.c.topic_id == topic_id)

        session = getSession()
        r = session.execute(statement)
        retval = []
        if r.rowcount:
            retval = [self.marshall_post(x) for x in r]
        return retval

    def post(self, post_id):
        """ Retrieve a particular post.

            Returns:
                {'post_id': ID, 'group_id': ID, 'site_id': ID,
                 'subject': String,
                 'date': Date, 'author_id': ID,
                 'body': Text, 'hidden': DateOrNull,
                 'files_metadata': [Metadata]
                 }
             or
                None

        """
        pt = self.postTable
        statement = pt.select()
        statement.append_whereclause(pt.c.post_id == post_id)

        session = getSession()
        r = session.execute(statement)
        if r.rowcount:
            assert r.rowcount == 1, "Posts should always be unique"
            row = r.fetchone()

            return self.marshall_post(row)

        return None

    def topic(self, topic_id):
        """
            Returns:
             {'topic_id': ID, 'subject': String, 'first_post_id': ID,
               'last_post_id': ID, 'count': Int, 'last_post_date': Date,
               'group_id': ID, 'site_id': ID}
        """
        tt = self.topicTable
        statement = tt.select()
        statement.append_whereclause(tt.c.topic_id == topic_id)

        session = getSession()
        r = session.execute(statement)

        retval = None
        if r.rowcount:
            assert r.rowcount == 1, "Topics should always be unique"
            row = r.fetchone()
            retval = self.marshal_topic(row)
        return retval

    def files_metadata(self, post_id):
        """ Retrieve the metadata of all files associated with this post.

            Returns:
                {'file_id': ID, 'mime_type': String,
                 'file_name': String, 'file_size': Int}
             or
                []

        """
        ft = self.fileTable
        statement = ft.select()
        statement.append_whereclause(ft.c.post_id == post_id)

        session = getSession()
        r = session.execute(statement)
        out = []
        if r.rowcount:
            out = []
            for row in r:
                out.append({'file_id': row['file_id'],
                            'file_name': to_unicode(row['file_name']),
                            'date': row['date'],
                            'mime_type': to_unicode(row['mime_type']),
                            'file_size': row['file_size']})

        return out

    def active_groups(self, interval='1 day'):
        """Retrieve all active groups

        An active group is one which has had a post added to it within
        "interval".

        ARGUMENTS
            "interval"  An SQL interval, as a string, made up of
                        "quantity unit". The quantity is an integer value,
                        while the unit is one of "second", "minute", "hour",
                        "day", "week", "month", "year", "decade",
                        "century", or "millennium".

        RETURNS
            A list of dictionaries, which contain "group_id" and "site_id".

        SIDE EFFECTS
            None.

        See Also
            Section 8.5.1.4 of the PostgreSQL manual:
          http://www.postgresql.org/docs/8.0/interactive/datatype-datetime.html
        """
        statement = sa.text("""SELECT DISTINCT group_id, site_id
                               FROM topic
         WHERE age(CURRENT_TIMESTAMP, last_post_date) < INTERVAL :interval""")

        session = getSession()
        r = session.execute(statement, params={'interval': interval})
        retval = []
        if r.rowcount:
            retval = [{'site_id': x['site_id'],
                        'group_id': x['group_id']} for x in r]
        return retval

    def topic_search(self, search_string, site_id, group_ids=()):
        """ Retrieve all the topics matching a particular search string.

            Returns:
             ({'topic_id': ID, 'subject': String, 'first_post_id': ID,
               'last_post_id': ID, 'count': Int, 'last_post_date': Date,
               'group_id': ID, 'site_id': ID}, ...)"""
        tt = self.topicTable
        tkt = self.topicKeywordsTable
        cols = (tt.c.topic_id, tt.c.site_id, tt.c.group_id,
               tt.c.original_subject, tt.c.first_post_id, tt.c.last_post_id,
               tt.c.num_posts, tt.c.last_post_date, tkt.c.keywords)
        statement = sa.select(cols, order_by=sa.desc(tt.c.last_post_date),
                              limit=30)
        self.__add_std_where_clauses(statement, tt,
                                     site_id, group_ids)
        if search_string:
            q = ' & '.join(search_string)
            statement.append_whereclause(tt.c.fts_vectors.match(q))
        statement.append_whereclause(tt.c.topic_id == tkt.c.topic_id)

        session = getSession()
        r = session.execute(statement)
        retval = []
        if r.rowcount:
            retval = [self.marshal_topic(x) for x in r]
        return retval

    def num_posts_after_date(self, site_id, group_id, user_id, date):
        assert type(site_id) == str
        assert type(group_id) == str
        assert type(user_id) == str

        pt = self.postTable
        cols = [sa.func.count(pt.c.post_id)]
        statement = sa.select(cols)
        statement.append_whereclause(pt.c.site_id == site_id)
        statement.append_whereclause(pt.c.group_id == group_id)
        statement.append_whereclause(pt.c.user_id == user_id)
        statement.append_whereclause(pt.c.date > date)

        session = getSession()
        r = session.execute(statement)

        retval = r.scalar()
        assert type(retval) == long, 'retval is %s' % type(retval)
        return retval
