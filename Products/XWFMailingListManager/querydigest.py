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
        s = sa.text("""SELECT DISTINCT topic.site_id, topic.group_id FROM
  (SELECT site_id, group_id, max(sent_date) AS sent_date
     FROM group_digest GROUP BY site_id,group_id) AS latest_digest, topic
  WHERE topic.site_id = latest_digest.site_id
    AND topic.group_id = latest_digest.group_id
    AND latest_digest.sent_date < CURRENT_TIMESTAMP-interval :interval
    AND topic.last_post_date > CURRENT_TIMESTAMP-interval :active_interval""")

        session = getSession()
        d = {'interval': interval, 'active_interval': active_interval}
        r = session.execute(s, params=d)
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
