# -*- coding: utf-8 *-*
import datetime
import sqlalchemy as sa
from zope.sqlalchemy import mark_changed
from gs.database import getTable, getSession


class DigestQuery(object):
    def __init__(self, context):
        self.context = context

        self.digestTable = getTable('group_digest')
        self.now = datetime.datetime.now()

    def has_digest_since(self, site_id, group_id,
                        interval=datetime.timedelta(0.9)):
        """ Have there been any digests sent in the last 'interval' time
        period?

        """
        sincetime = self.now - interval
        dt = self.digestTable

        statement = dt.select()

        statement.append_whereclause(dt.c.site_id == site_id)
        statement.append_whereclause(dt.c.group_id == group_id)
        statement.append_whereclause(dt.c.sent_date >= sincetime)

        session = getSession()
        r = session.execute(statement)

        result = False
        if r.rowcount:
            result = True

        return result

    def no_digest_but_active(self, interval='7 days',
                            active_interval='3 months'):
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
                            active_interval=active_interval)  # FIXME?
        retval = []
        if r.rowcount:
            retval = [{'site_id': x['site_id'],
                        'group_id': x['group_id']} for x in r]
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
