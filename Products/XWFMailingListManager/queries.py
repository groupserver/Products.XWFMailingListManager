from sqlalchemy.exc import NoSuchTableError
import sqlalchemy as sa
import datetime
from pytz import UTC

from zope.sqlalchemy import mark_changed
from gs.database import getTable, getSession

import logging
log = logging.getLogger("XMLMailingListManager.queries") #@UndefinedVariable

LAST_NUM_DAYS = 60

def to_unicode(s):
    retval = s
    if not isinstance(s, unicode):
        retval = unicode(s, 'utf-8')

    return retval    

def summary(s):
    if not isinstance(s, unicode):
        s = unicode(s, 'utf-8')
    
    return s[:160]

class DigestQuery(object):
    def __init__(self, context):
        self.context = context
         
        self.digestTable = getTable('group_digest')
        self.now = datetime.datetime.now()

    def has_digest_since(self, site_id, group_id, interval=datetime.timedelta(0.9)):
        """ Have there been any digests sent in the last 'interval' time period?
        
        """
        sincetime = self.now-interval
        dt = self.digestTable
        
        statement = dt.select()

        statement.append_whereclause(dt.c.site_id==site_id)
        statement.append_whereclause(dt.c.group_id==group_id)
        statement.append_whereclause(dt.c.sent_date >= sincetime)

        session = getSession()
        r = session.execute(statement)
        
        result = False
        if r.rowcount:
            result = True
            
        return result

    def no_digest_but_active(self, interval='7 days', active_interval='3 months'):
        """ Returns a list of dicts containing site_id and group_id
            which have not received a digest in the 'interval' time period.
        
        """
        s = sa.text("""select DISTINCT topic.site_id,topic.group_id from 
               (select site_id, group_id, max(sent_date) as sent_date from
                group_digest group by site_id,group_id) as latest_digest,topic
                where (topic.site_id=latest_digest.site_id and
                       topic.group_id=latest_digest.group_id and
                latest_digest.sent_date < CURRENT_TIMESTAMP-interval :interval
                and topic.last_post_date >
                CURRENT_TIMESTAMP-interval :active_interval)""")
        
        session = getSession()
        r = session.execute(s, interval=interval,
                            active_interval=active_interval) 
        retval = []
        if r.rowcount:
            retval = [ {'site_id': x['site_id'],
                        'group_id': x['group_id']} for x in r ]
        return retval
    
    def update_group_digest(self, site_id, group_id):
        """ Update the group_digest table when we send out a new digest.
        
        """
        dt = self.digestTable
        
        statement = dt.insert()

        session = getSession()
        session.execute(statement,
                        params={'site_id': site_id,
                                'group_id': group_id,
                                'sent_date': self.now})

        mark_changed(session)

class MemberQuery(object):
    # how many user ID's should we attempt to pass to the database before
    # we just do the filtering ourselves to avoid the overhead on the database
    USER_FILTER_LIMIT = 200

    def __init__(self, context):
        self.context = context
         
        self.emailSettingTable = getTable('email_setting')
        self.userEmailTable = getTable('user_email')
        self.groupUserEmailTable = getTable('group_user_email')
        self.emailBlacklist = getTable('email_blacklist')

    def address_is_blacklisted(self, emailAddress):
        s = self.emailBlacklist.select()
        ilike = self.emailBlacklist.c.email.op('ILIKE')
        s.append_whereclause(ilike(emailAddress))
        
        session = getSession()
        r = session.execute(s)
        
        retval = (r.rowcount > 0)
        assert type(retval) == bool
        return retval

    def process_blacklist(self, email_addresses):
        eb = self.emailBlacklist

        blacklist = eb.select()
        session = getSession()

        r = session.execute(blacklist)
        blacklisted_addresses = []
        if r.rowcount:
            for row in r:
                blacklist_email = row['email'].strip()
                if blacklist_email:
                    blacklisted_addresses.append(blacklist_email)
                    
        for blacklist_email in blacklisted_addresses:
            if blacklist_email in email_addresses:
                email_addresses.remove(blacklist_email)
                log.warn('Found blacklisted email address: "%s" in email list' % blacklist_email)

        return email_addresses

    def get_member_addresses(self, site_id, group_id, id_getter, preferred_only=True, process_settings=True, verified_only=True):
        # TODO: We currently can't use site_id
        site_id = ''

        user_ids = id_getter(ids_only=True)
        est = self.emailSettingTable        
        uet = self.userEmailTable
        guet = self.groupUserEmailTable
        session = getSession() 
        ignore_ids = []
        email_addresses = []

        # process anything that might include/exclude specific email addresses
        # or block email delivery
        if process_settings:
            email_settings = est.select()
            email_settings.append_whereclause(est.c.site_id==site_id)
            email_settings.append_whereclause(est.c.group_id==group_id)
            
            r = session.execute(email_settings)
        
            if r.rowcount:
                for row in r:
                    ignore_ids.append(row['user_id'])
        
            cols = [guet.c.user_id, guet.c.email]
            email_group = sa.select(cols)
            
            email_group.append_whereclause(guet.c.site_id==site_id)
            email_group.append_whereclause(guet.c.group_id==group_id)
            if verified_only:
                email_group.append_whereclause(guet.c.email==uet.c.email)
                email_group.append_whereclause(uet.c.verified_date != None)
         
            r = session.execute(email_group)
            if r.rowcount:
                n_ignore_ids = []
                for row in r:
                    # double check for security that this user should actually
                    # be receiving email for this group
                    if row['user_id'] in user_ids and row['user_id'] not in ignore_ids:
                        n_ignore_ids.append(row['user_id'])
                        email_addresses.append(row['email'].lower())

                ignore_ids += n_ignore_ids

            # remove any ids we have already processed
            user_ids = filter(lambda x: x not in ignore_ids, user_ids)

        email_user = uet.select()
        if preferred_only:
            email_user.append_whereclause(uet.c.is_preferred==True)
        if verified_only:
            email_user.append_whereclause(uet.c.verified_date != None)
                    
        if len(user_ids) <= self.USER_FILTER_LIMIT:
            email_user.append_whereclause(uet.c.user_id.in_(user_ids))

        r = session.execute(email_user)
        if r.rowcount:
            for row in r:
                if len(user_ids) > self.USER_FILTER_LIMIT:
                    if row['user_id'] in user_ids:
                        email_addresses.append(row['email'].lower())                        
                else:
                    email_addresses.append(row['email'].lower())

        email_addresses = self.process_blacklist(email_addresses)

        return email_addresses

    def get_digest_addresses(self, site_id, group_id, id_getter):
        # TODO: We currently can't use site_id
        site_id = ''
        
        user_ids = id_getter(ids_only=True)
        est = self.emailSettingTable        
        uet = self.userEmailTable
        guet = self.groupUserEmailTable

        email_settings = est.select()
        email_settings.append_whereclause(est.c.site_id==site_id)
        email_settings.append_whereclause(est.c.group_id==group_id)
        email_settings.append_whereclause(est.c.setting=='digest')
        
        session = getSession() 
        r = session.execute(email_settings)
        
        digest_ids = []
        ignore_ids = []
        email_addresses = []
        if r.rowcount:
            for row in r:
                if row['user_id'] in user_ids:
                    digest_ids.append(row['user_id'])
        
        email_group = guet.select()
        email_group.append_whereclause(guet.c.site_id==site_id)
        email_group.append_whereclause(guet.c.group_id==group_id)
        email_group.append_whereclause(guet.c.user_id.in_(digest_ids))
        
        r = session.execute(email_group)
        if r.rowcount:
            for row in r:
                ignore_ids.append(row['user_id'])
                email_addresses.append(row['email'].lower())
        
        # remove any ids we have already processed
        digest_ids = filter(lambda x: x not in ignore_ids, digest_ids)

        email_user = uet.select()
        email_user.append_whereclause(uet.c.is_preferred==True)      
        email_user.append_whereclause(uet.c.user_id.in_(digest_ids))
        email_user.append_whereclause(uet.c.verified_date != None)
        
        r = session.execute(email_user)
        if r.rowcount:
            for row in r:
                if row['user_id'] in user_ids:
                    email_addresses.append(row['email'].lower())

        email_addresses = self.process_blacklist(email_addresses)

        return email_addresses
        
class MessageQuery(object):
    def __init__(self, context):
        self.context = context
        
        self.topicTable = getTable('topic')
        self.topic_word_countTable = getTable('topic_word_count')
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
        statement.append_whereclause(table.c.site_id==site_id)
        if group_ids:
            inStatement = table.c.group_id.in_(group_ids)
            statement.append_whereclause(inStatement)

        return statement

    def post_id_from_legacy_id(self, legacy_post_id):
        """ Given a legacy (pre-1.0) GS post_id, determine what the new
        post ID is, if we know.
        
        This is primarily used for backwards compatibility in the redirection
        system.
        
        """
        pit = self.post_id_mapTable
        if pit == None:
            return None
        
        statement = pit.select()
        
        statement.append_whereclause(pit.c.old_post_id==legacy_post_id)
        
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
        statement.append_whereclause(pt.c.post_id==post_id)

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
            retval = [self.marshall_post(x) for x in r ]

        return retval
    
    def post_count(self, site_id, group_ids=[]):
        statement = sa.select([sa.func.sum(self.topicTable.c.num_posts)]) #@UndefinedVariable
        self.__add_std_where_clauses(statement, self.topicTable, 
                                           site_id, group_ids)
        session = getSession()
        r = session.execute(statement)

        retval = r.scalar()
        if retval == None:
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
            retval = [ {'topic_id': x['topic_id'], 
                        'site_id': x['site_id'], 
                        'group_id': x['group_id'], 
                        'subject': to_unicode(x['original_subject']),
                        'first_post_id': x['first_post_id'], 
                        'last_post_id': x['last_post_id'], 
                        'count': x['num_posts'], 
                        'last_post_date': x['last_post_date']} for x in r ]
                        
        return retval

    def _nav_post(self, curr_post_id, direction, topic_id=None):
        op = direction == 'prev' and '<=' or '>='
        dir = direction == 'prev' and 'desc' or 'asc'
        
        topic_id_filter = ''
        if topic_id:
            topic_id_filter = 'post.topic_id=curr_post.topic_id and'
        
        s = sa.text("""select post.date, post.post_id, post.topic_id,
                       post.subject, post.user_id, post.has_attachments
                    from post, 
                   (select date,group_id,site_id,post_id,topic_id from post where 
                post_id=:curr_post_id) as curr_post where
                post.group_id=curr_post.group_id and
                post.site_id=curr_post.site_id and
                post.date %s curr_post.date and
                %s
                post.post_id != curr_post.post_id
                order by post.date %s limit 1""" % (op, topic_id_filter, dir))
        
        session = getSession()
        r = session.execute(s, params={'curr_post_id': curr_post_id}).fetchone()
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
        """ Retrieve first/last, next/prev navigation relative to a post, within a topic.
            Used for navigation of single posts *within* a topic, not for general post
            navigation.

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
        
            statement.append_whereclause(tt.c.topic_id==topic_id)
        
            session = getSession()
            r = session.execute(statement)
        
            if r.rowcount:
                result = r.fetchone()
            
                first_post_id = result['first_post_id']
                last_post_id = result['last_post_id']
        
            r = self._nav_post(curr_post_id, 'next', topic_id)
            if r:
                assert r['topic_id'] == topic_id, "Topic ID should always match"
                next_post_id = r['post_id']
            
            r = self._nav_post(curr_post_id, 'prev', topic_id)
            if r:
                assert r['topic_id'] == topic_id, "Topic ID should always match"
                previous_post_id = r['post_id']
        retval = {'first_post_id': first_post_id, 
                  'next_post_id': next_post_id,
                  'previous_post_id': previous_post_id, 
                  'last_post_id': last_post_id,}
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
        statement.append_whereclause(pt.c.topic_id==topic_id)
        
        session = getSession()
        r = session.execute(statement)
        retval = []
        if r.rowcount:
            retval = [self.marshall_post(x) for x in r ]

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
        statement.append_whereclause(pt.c.post_id==post_id)
        
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
        statement.append_whereclause(tt.c.topic_id==topic_id)

        retval = None
        
        session = getSession()
        r = session.execute(statement)
        if r.rowcount:
            assert r.rowcount == 1, "Topics should always be unique"
            row = r.fetchone()
            retval = {'topic_id': row['topic_id'], 
                      'site_id': row['site_id'],
                      'group_id': row['group_id'],
                      'subject': to_unicode(row['original_subject']), 
                      'first_post_id': row['first_post_id'],
                      'last_post_id': row['last_post_id'],
                      'last_post_date': row['last_post_date'],
                      'count': row['num_posts']}
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
        statement.append_whereclause(ft.c.post_id==post_id)
       
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
        tt = self.topicTable
        statement = sa.text("""SELECT DISTINCT group_id, site_id
                               FROM topic 
         WHERE age(CURRENT_TIMESTAMP, last_post_date) < INTERVAL :interval""")

        session = getSession()
        r = session.execute(s, params={'interval': interval})
        retval = []
        if r.rowcount:
            retval = [ {'site_id': x['site_id'], 
                        'group_id': x['group_id']} for x in r ]
        return retval        
  
    def topic_search(self, search_string, site_id, group_ids=()):
        """ Retrieve all the topics matching a particular search string.
        
            Returns:
             ({'topic_id': ID, 'subject': String, 'first_post_id': ID,
               'last_post_id': ID, 'count': Int, 'last_post_date': Date,
               'group_id': ID, 'site_id': ID}, ...)
               
        """
        tt = self.topicTable
        twc = self.topic_word_countTable
        t = tt.join(twc, twc.c.topic_id==tt.c.topic_id)
        statement = sa.select((tt.c.topic_id,tt.c.site_id,tt.c.group_id,
                               tt.c.original_subject, tt.c.first_post_id,
                               tt.c.last_post_id, tt.c.num_posts,
                               tt.c.last_post_date), from_obj=[t],
                              order_by=sa.desc(tt.c.last_post_date),
                              limit=30)
        self.__add_std_where_clauses(statement, tt, 
                                     site_id, group_ids)
        
        statement.append_whereclause(twc.c.word.in_(search_string.split()))
        
        session = getSession()
        r = session.execute(statement)

        retval = []
        if r.rowcount:
            retval = [ {'topic_id': x['topic_id'], 
                        'site_id': x['site_id'], 
                        'group_id': x['group_id'], 
                        'subject': to_unicode(x['original_subject']),
                        'first_post_id': x['first_post_id'], 
                        'last_post_id': x['last_post_id'], 
                        'count': x['num_posts'], 
                        'last_post_date': x['last_post_date']} for x in r ]
        return retval

    def num_posts_after_date(self, site_id, group_id, user_id, date):
        assert type(site_id)  == str
        assert type(group_id) == str
        assert type(user_id)  == str
                
        pt = self.postTable
        cols = [sa.func.count(pt.c.post_id)]
        statement = sa.select(cols)
        statement.append_whereclause(pt.c.site_id  == site_id)
        statement.append_whereclause(pt.c.group_id == group_id)
        statement.append_whereclause(pt.c.user_id  == user_id)
        statement.append_whereclause(pt.c.date  > date)
        
        session = getSession()
        r = session.execute(statement)

        retval = r.scalar()
        assert type(retval) == long, 'retval is %s' % type(retval)
        return retval
