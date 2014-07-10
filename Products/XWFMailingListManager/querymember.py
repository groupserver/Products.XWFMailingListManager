# -*- coding: utf-8 *-*
import sqlalchemy as sa
from gs.database import getTable, getSession
import logging
log = logging.getLogger("XMLMailingListManager.querymember")


class MemberQuery(object):
    # how many user ID's should we attempt to pass to the database before
    # we just do the filtering ourselves to avoid the overhead on the
    # database
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
                m = 'Found blacklisted email address: "%s" in email list' %\
                    blacklist_email
                log.warn(m)

        return email_addresses

    def get_member_addresses(self, site_id, group_id, id_getter,
                             preferred_only=True, process_settings=True,
                             verified_only=True):
        # TODO: We currently can't use site_id
        site_id = ''

        user_ids = id_getter(ids_only=True)
        est = self.emailSettingTable
        uet = self.userEmailTable
        guet = self.groupUserEmailTable
        session = getSession()
        ignore_ids = []
        email_addresses = []

        # process anything that might include/exclude specific email
        # addresses or block email delivery
        if process_settings:
            email_settings = est.select()
            email_settings.append_whereclause(est.c.site_id == site_id)
            email_settings.append_whereclause(est.c.group_id == group_id)

            r = session.execute(email_settings)

            if r.rowcount:
                for row in r:
                    ignore_ids.append(row['user_id'])

            cols = [guet.c.user_id, guet.c.email]
            email_group = sa.select(cols)

            email_group.append_whereclause(guet.c.site_id == site_id)
            email_group.append_whereclause(guet.c.group_id == group_id)
            if verified_only:
                email_group.append_whereclause(guet.c.email == uet.c.email)
                email_group.append_whereclause(uet.c.verified_date != None)

            r = session.execute(email_group)
            if r.rowcount:
                n_ignore_ids = []
                for row in r:
                    # double check for security that this user should
                    # actually be receiving email for this group
                    if ((row['user_id'] in user_ids)
                            and (row['user_id'] not in ignore_ids)):
                        n_ignore_ids.append(row['user_id'])
                        email_addresses.append(row['email'].lower())

                ignore_ids += n_ignore_ids

            # remove any ids we have already processed
            user_ids = filter(lambda x: x not in ignore_ids, user_ids)

        email_user = uet.select()
        if preferred_only:
            email_user.append_whereclause(uet.c.is_preferred == True)
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
        # FIXME: The user-group-email-settings were historically recorded
        #        without a site identifier, relying on the
        #        group-identifiers to be unique. We need to fix this. Sadly
        #        this will require a lot of work to test. Just adding a
        #        site identifier check here will cause the digests to not
        #        go out.
        # email_settings.append_whereclause(est.c.site_id == site_id)
        email_settings.append_whereclause(est.c.group_id == group_id)
        email_settings.append_whereclause(est.c.setting == 'digest')

        session = getSession()
        r = session.execute(email_settings)

        digest_ids = []
        ignore_ids = []
        email_addresses = []
        if r.rowcount:
            for row in r:
                if ((row['user_id'] in user_ids)
                        and (row['user_id'] not in digest_ids)):
                    digest_ids.append(row['user_id'])

        email_group = guet.select()
        email_group.append_whereclause(guet.c.site_id == site_id)
        email_group.append_whereclause(guet.c.group_id == group_id)
        email_group.append_whereclause(guet.c.user_id.in_(digest_ids))

        r = session.execute(email_group)
        if r.rowcount:
            for row in r:
                ignore_ids.append(row['user_id'])
                email_addresses.append(row['email'].lower())

        # remove any ids we have already processed
        digest_ids = [x for x in digest_ids if x not in ignore_ids]

        email_user = uet.select()
        #lint:disable
        email_user.append_whereclause(uet.c.is_preferred == True)
        email_user.append_whereclause(uet.c.user_id.in_(digest_ids))
        email_user.append_whereclause(uet.c.verified_date != None)
        #lint:enable

        r = session.execute(email_user)
        if r.rowcount:
            for row in r:
                if row['user_id'] in user_ids:
                    email_addresses.append(row['email'].lower())
        email_addresses = self.process_blacklist(email_addresses)
        return email_addresses
