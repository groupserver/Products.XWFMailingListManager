import time, pytz
from datetime import datetime, timedelta

from zope.app.apidoc import interface

from Products.CustomUserFolder.interfaces import ICustomUser, IGSUserInfo
from Products.XWFChat.interfaces import IGSGroupFolder
from Products.GSContent.interfaces import IGSGroupInfo
from Products.GSGroupMember.groupmembership import user_member_of_group,
  user_participation_coach_of_group, user_admin_of_group
from Products.XWFCore.XWFUtils import munge_date
from Products.XWFMailingListManager.queries import MessageQuery
from Products.GSProfile import interfaces as profileinterfaces

class GSGroupMemberPostingInfo(object)

    def __init__(self, group, user):
        assert IGSGroupFolder.providedBy(group),\
          '%s is not a group' % group
        assert ICustomUser.providedBy(user), '%s is not a user' % user
        
        self.userInfo = IGSUserInfo(user)
        self.user = user
        self.groupInfo = IGSGroupInfo(group)
        self.group = group
        
        mailingListManager = self.mailingListManager = group.ListManager
        mailingList = self.mailingList =\
          mailingListManager.get_list(group.getId())

        da = group.zsqlalchemy 
        assert da
        self.messageQuery = MessageQuery(group, da)
        
        self.__status = None
        self.__canPost == None
    
    @property
    def whoCanPost(self):
        retval = u'No one can post messages.'
        assert retval
        assert type(retval) == unicode
        return retval
        
    @property
    def status(self):
        if self.__status == None:
            justCall = self.canPost
        retval = self.__status
        assert retval
        assert type(retval) == unicode
        return retval

    @property
    def canPost(self):
        if self.__canPost == None:
            self.__canPost = \
              not(self.group_is_closed()) or\
              (self.user_is_member() and\
                self.user_is_posting_member() and\
                not(self.user_posting_limit_hit()) and\
                not(self.user_blocked_from_posting()) and\
                self.user_has_required_properties())
        retval = self.__canPost
        assert type(retval) == bool
        return retval
        
    def group_is_closed(self):
        '''A closed group is one where only members can post. It is 
          defined by the Germanic-property "unclosed", which GroupServer
          inherited from MailBoxer. (We would love to change its name, but
          it would break too much code.)
          
          If the "unclosed" property is "True" then the group is open to 
          any poster, and we do not have to bother with any member-specific
          checks. Support groups are like this.
          
          If the "unclosed" property is "Fase" then we have to perform the
          member-specific checks to ensure that the posting user is allowed
          to post.
        '''
        retval = self.mailingList.getProperty('unclosed', False)
        if retval:
            self.__status = u'the group %s is open to anyone posting' %\
              self.groupInfo.name
        else:
            self.__status = u'only members can post to the group %s' %\
              self.groupInfo.name
        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def user_is_memeber(self):
        retval = user_member_of_group(self.user, self.group)
        if retval:
            self.__status = u'a member of %s' % self.groupInfo
        else:
            self.__status = u'not a member of %s' % self.groupInfo
        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def user_is_posting_memeber(self):
        '''Check the "posting_members" property of the mailing list,
        which is assumed to be a lines-property containing the user-IDs of
        the people who can post. If the property does not contain any
        values, it is assumed that everyone is a posting member.
        '''
        postingMembers = self.mailingList.getProperty('posting_members', [])
        if postingMembers:
            retval = self.userInfo.id in postingMembers
        else:
            retval = True
        if retval:
            self.__status = u'a posting member of %s' %\
               self.groupInfo.name
        else:
            self.__status = u'not a posting member of %s' %\
               self.groupInfo.name
        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def user_posting_limits_hit(self):
        '''The posting limits are based on the *rate* of posting to the 
        group. The maximum allowed rate of posting is defined by the 
        "senderlimit" and "senderinterval" properties of the mailing list
        for the group. If the user has exceeded his or her posting limits
        if  more than "senderlimit" posts have been sent in
        "senderinterval" seconds to the group.
        '''
        if user_participation_coach_of_group(self.userInfo, self.groupInfo):
            retval = False
            self.__status = u'the participation coach of %s' %\
              self.groupInfo.name
        elif user_admin_of_group(self.userInfo, self.groupInfo):
            retval = False
            self.__status = u'an administrator of %s' %\
              self.groupInfo.name
        else:
            # The user is not the participation coach or the administrator
            # of the group
            sid = self.groupInfo.siteInfo.id
            gid = self.groupInfo.id
            uid = self.userInfo.id
            limit = self.mailingList.getValueFor('senderlimit')
            interval = self.mailingList.getValueFor('senderinterval')
            earlyDate = datetime.now(pytz.utc) - timedelta(interval)
            count = self.messageQuery.num_posts_after_date(sid, gid, uid, 
                                                           earlyDate)
            if count >= limit:
                # The user has made over the allowed number of posts in
                # the interval
                retval = True
                self.__status = u'have exceeded the posting limit'
            else:
                retval = False
                self.__status = u'are under the posting limit'
        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def user_blocked_from_posting(self):
        '''Blocking a user from posting is a powerful, but rarely used
        tool. Rather than removing a disruptive member from the group, or
        moderating the user, the user can be blocked from posting.
        '''
        blockedMemberIds = self.mailingList.getProperty('blocked_members', 
                                                        [])
        if (self.userInfo.id in blockedMemberIds):
            retval = True
            self.__status = u'blocked from posting'
        else:
            retval = False
            self.__status = u'not blocked from posting'
        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def user_has_required_properties(self):
        requiredSiteProperties = self.get_required_site_properties()
        requiredGroupProperties = self.get_required_group_properties()
        requiredProperties = requiredSiteProperties + requiredGroupProperties
        
        retval = False
        self.__status = u'required properties not set'
        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def get_required_site_properties(self):
        site_root = self.groupInfo.group.site_root()
        assert hasattr(site_root, 'GlobalConfiguration')
        config = site_root.GlobalConfiguration
        interfaceName = config.getProperty('profileInterface',
                                           'IGSCoreProfile')
        assert hasattr(profileinterfaces, interfaceName), \
            'Interface "%s" not found.' % interfaceName
        profileInterface = getattr(profileinterfaces, interfaceName)
        
        retval = [n for n, a in interface.getFieldsInOrder(profileInterface)]

        assert type(retval) == list
        return retval

    def get_required_group_properties(self):
        retval = self.mailingList.getProperty('required_properties', [])
        assert type(retval) == list
        return retval

