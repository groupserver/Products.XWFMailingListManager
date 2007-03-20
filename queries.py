import sqlalchemy as sa

class MessageQuery( object ):
    def __init__( self, context, da ):
        self.context = context

        session = da.getSession()
        metadata = session.getMetaData()

        self.topicTable = sa.Table('topic', metadata, autoload=True)
        self.postTable = sa.Table('post', metadata, autoload=True)
        self.fileTable = sa.Table('file', metadata, autoload=True)

    def topic_id_from_post_id( self, post_id ):
        """ Given a post_id, determine which topic it came from.
        
        """
        pt = self.postTable
        statement = pt.select()
        statement.append_whereclause(pt.c.post_id==post_id)
        r = statement.execute()
        
        topic_id = None
        if r.rowcount:
            result = r.fetchone()
            topic_id = result['topic_id']
        
        return topic_id
        
    def latest_topics( self, site_id, group_ids=[], limit=None, offset=0 ):
        """
            Returns: 
             ({'topic_id': ID, 'subject': String, 'first_post_id': ID,
               'last_post_id': ID, 'count': Int, 'last_post_date': Date}, ...)

        """
        tt = self.topicTable
        
        statement = tt.select()

        statement.append_whereclause(tt.c.site_id==site_id)
        if group_ids:
            statement.append_whereclause(tt.c.group_id.in_(*group_ids))
        
        statement.limit = limit
        statement.offset = offset
        statement.order_by(sa.desc(tt.c.last_post_date))
        
        r = statement.execute()
        
        if r.rowcount:
            return [ {'topic_id': x['topic_id'],
                      'subject': unicode(x['original_subject'], 'utf-8'),
                      'first_post_id': x['first_post_id'],
                      'last_post_id': x['last_post_id'],
                      'count': x['num_posts'],
                      'last_post_date': x['last_post_date']} for x in r ]
        
        return None

    def _nav_post( self, curr_post_id, direction, topic_id=None ):
        op = direction == 'prev' and '<=' or '>='
        dir = direction == 'prev' and 'desc' or 'asc'
        
        topic_id_filter = ''
        if topic_id:
            topic_id_filter = 'post.topic_id=curr_post.topic_id and'
        
        q = sa.text("""select post.date, post.post_id, post.topic_id,
                       post.subject, post.user_id, post.has_attachments
                    from post, 
                   (select date,group_id,site_id,post_id,topic_id from post where 
                    post_id='%(curr_post_id)s') as curr_post where
                   post.group_id=curr_post.group_id and
                   post.site_id=curr_post.site_id and
                   post.date %(op)s curr_post.date and
                   %(topic_id_filter)s
                   post.post_id != curr_post.post_id
                   order by post.date %(dir)s limit 1""" % locals(),
                   engine=self.postTable.engine)
        
        r = q.execute().fetchone()
        if r:
             return {'post_id': r['post_id'],
                     'topic_id': r['topic_id'],
                     'subject': unicode(r['subject'], 'utf-8'),
                     'date': r['date'],
                     'author_id': r['user_id'],
                     'has_attachments': r['has_attachments']}
        return None

    def previous_post( self, curr_post_id ):
        """ Find the post prior to the given post ID.

            Returns:
               {'post_id': ID, 'topic_id': ID, 'subject': String,
                'date': Date, 'author_id': String, 'has_attachments': Bool}
             or
                None

        """
        return self._nav_post(curr_post_id, 'prev')


    def next_post( self, curr_post_id ):
        """ Find the post after the given post ID.

            Returns:
               {'post_id': ID, 'topic_id': ID, 'subject': String,
                'date': Date, 'author_id': String, 'has_attachments': Bool}
             or
                None
        
        """
        return self._nav_post(curr_post_id, 'next')

    def _nav_topic( self, curr_topic_id, direction ):
        op = direction == 'prev' and '<=' or '>='
        dir = direction == 'prev' and 'desc' or 'asc'
        
        q = sa.text("""select topic.last_post_date as date,
                              topic.topic_id, topic.last_post_id,
                              topic.original_subject as subject
                    from topic, 
                   (select topic_id,last_post_date as date,group_id,site_id
                    from topic where 
                    topic_id='%s') as curr_topic where
                   topic.group_id=curr_topic.group_id and
                   topic.site_id=curr_topic.site_id and
                   topic.last_post_date %s curr_topic.date and
                   topic.topic_id != curr_topic.topic_id
                   order by date %s limit 1""" % 
                   (curr_topic_id, op, dir),
                   engine=self.postTable.engine)
        
        r = q.execute().fetchone()
        if r:
             return {'topic_id': r['topic_id'],
                     'last_post_id': r['last_post_id'],
                     'subject': unicode(r['subject'], 'utf-8'),
                     'date': r['date']}
        return None

    def previous_topic( self, curr_topic_id ):
        """ Find the topic prior to the given topic ID.

            Returns:
               {'last_post_id': ID, 'topic_id': ID,
                'subject': String, 'date': Date}
             or
                None

        """
        return self._nav_topic(curr_topic_id, 'prev')

    def next_topic( self, curr_topic_id ):
        """ Find the topic after the given topic ID.

            Returns:
               {'last_post_id': ID, 'topic_id': ID,
                'subject': String, 'date': Date}
             or
                None
        
        """
        return self._nav_topic(curr_topic_id, 'next')
    
    def topic_post_navigation( self, curr_post_id ):
        """ Retrieve first/last, next/prev navigation relative to a post, within a topic.
            Used for navigation of single posts *within* a topic, not for general post
            navigation.

            Returns:
                {'first_post_id': ID, 'last_post_id': ID,
                 'previous_post_id': ID, 'next_post_id': ID}
            
            ID may be None.
             
        """
        topic_id = None
        first_post_id = None
        last_post_id = None
        next_post_id = None
        previous_post_id = None
        
        tt = self.topicTable
        pt = self.postTable
        
        topic_id = self.topic_id_from_post_id(curr_post_id)

        if topic_id:
            statement = tt.select()
        
            statement.append_whereclause(tt.c.topic_id==topic_id)
        
            r = statement.execute()
        
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
        
        return {'first_post_id': first_post_id, 'last_post_id': last_post_id,
                'previous_post_id': previous_post_id, 'next_post_id': next_post_id}
        
    def topic_posts( self, topic_id ):
        """ Retrieve all the posts in a topic.
            
            Returns:
                ({'post_id': ID, 'subject': String,
                  'date': Date, 'author_id': ID,
                  'body': Text}, ...)
             or
                None

        """
        pt = self.postTable
        statement = pt.select()
        statement.append_whereclause(pt.c.topic_id==topic_id)
        statement.order_by(sa.asc(pt.c.date))
        
        r = statement.execute()
        if r.rowcount:
            return [ {'post_id': x['post_id'],
                      'subject': unicode(x['subject'], 'utf-8'),
                      'date': x['date'],
                      'author_id': x['user_id'],
                      'body': unicode(x['body'], 'utf-8')} for x in r ]
        
        return None

    def post( self, post_id ):
        """ Retrieve a particular post.
            
            Returns:
                {'post_id': ID, 'subject': String,
                 'date': Date, 'author_id': ID,
                 'body': Text}
             or
                None

        """
        pt = self.postTable
        statement = pt.select()
        statement.append_whereclause(pt.c.post_id==post_id)
        
        r = statement.execute()
        if r.rowcount:
            assert r.rowcount == 1, "Posts should always be unique"
            row = r.fetchone()
            return {'post_id': row['post_id'],
                    'subject': unicode(row['subject'], 'utf-8'),
                    'date': row['date'],
                    'author_id': row['user_id'],
                    'body': unicode(row['body'], 'utf-8')}
        
        return None
