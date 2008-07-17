import time, pytz
from datetime import datetime, timedelta

from zope.app.apidoc import interface
from zope.component import createObject

from Products.CustomUserFolder.interfaces import ICustomUser, IGSUserInfo
from Products.XWFChat.interfaces import IGSGroupFolder
from Products.GSContent.interfaces import IGSGroupInfo
from Products.GSGroupMember.groupmembership import user_member_of_group,\
  user_participation_coach_of_group, user_admin_of_group
from Products.XWFCore.XWFUtils import munge_date
from Products.XWFMailingListManager.queries import MessageQuery
from Products.GSProfile import interfaces as profileinterfaces

class GSGroupMemberPostingInfo(object):

    def __init__(self, group, user):
        assert IGSGroupFolder.providedBy(group),\
          '%s is not a group' % group
        #assert ICustomUser.providedBy(user), '%s is not a user' % user
        
        site_root = group.aq_parent.aq_parent.aq_parent.aq_parent.aq_parent
        self.site_root = site_root
        
        mailingListManager = self.mailingListManager = site_root.ListManager
        mailingList = self.mailingList =\
          mailingListManager.get_list(group.getId())

        self.userInfo = createObject('groupserver.UserFromId', 
                                      site_root, user.getId())
        self.user = self.userInfo.user
        
        self.groupInfo = IGSGroupInfo(group)
        self.group = group
        
        da = site_root.zsqlalchemy 
        assert da
        self.messageQuery = MessageQuery(group, da)
        
        self.__status = None
        self.__statusNum = 0
        self.__canPost = None
        self.__profileInterfaces = None
    
    @property
    def whoCanPost(self):
        retval = u'no one can post messages.'
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
    def statusNum(self):
        retval = self.__statusNum
        assert type(retval) == int
        return retval

    @property
    def canPost(self):
        if self.__canPost == None:
            self.__canPost = \
              self.group_is_unclosed() or\
               (not(self.user_anonymous()) and\
                self.user_is_member() and\
                self.user_has_preferred_email_addresses() and\
                self.user_is_posting_member() and\
                not(self.user_posting_limit_hit()) and\
                not(self.user_blocked_from_posting()) and\
                self.user_has_required_properties())
        retval = self.__canPost
        assert type(retval) == bool
        return retval
        
    def group_is_unclosed(self):
        '''A closed group is one where only members can post. It is 
          defined by the Germanic-property "unclosed", which GroupServer
          inherited from MailBoxer. (We would love to change its name, but
          it would break too much code.)
          
          If the "unclosed" property is "True" then the group is open to 
          any poster, and we do not have to bother with any member-specific
          checks. Support groups like this.
          
          If the "unclosed" property is "False" then we have to perform the
          member-specific checks to ensure that the posting user is allowed
          to post.
        '''
        retval = self.mailingList.getProperty('unclosed', False)
        if retval:
            self.__status = u'the group is open to anyone posting'
            self.__statusNum = self.__statusNum + 0
        else:
            self.__status = u'not a member'
            self.__statusNum = self.__statusNum + 1

        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def user_anonymous(self):
        retval = self.userInfo.anonymous
        if retval:
            self.__status = u'not logged in'
            self.__statusNum = self.__statusNum + 2
        else:
            self.__status = u'logged in'
            self.__statusNum = self.__statusNum + 0
            
        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def user_has_preferred_email_addresses(self):
        preferredEmailAddresses =\
          self.userInfo.user.get_defaultDeliveryEmailAddresses()
        retval = len(preferredEmailAddresses) >= 1
        if retval:
            self.__status = u'preferred email addresses'
        else:
            self.__status = u'no preferred email addresses'
            self.__statusNum = self.__statusNum + 4
        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def user_is_member(self):
        retval = user_member_of_group(self.user, self.group)
        if retval:
            self.__status = u'a member'
            self.__statusNum = self.__statusNum + 0
        else:
            self.__status = u'not a member'
            self.__statusNum = self.__statusNum + 8
        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def user_is_posting_member(self):
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
            self.__status = u'posting member'
            self.__statusNum = self.__statusNum + 0
        else:
            self.__status = u'not a posting member'
            self.__statusNum = self.__statusNum + 16
        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def user_posting_limit_hit(self):
        '''The posting limits are based on the *rate* of posting to the 
        group. The maximum allowed rate of posting is defined by the 
        "senderlimit" and "senderinterval" properties of the mailing list
        for the group. If the user has exceeded his or her posting limits
        if  more than "senderlimit" posts have been sent in
        "senderinterval" seconds to the group.
        '''
        if user_participation_coach_of_group(self.userInfo, self.groupInfo):
            retval = False
            self.__status = u'participation coach'
            self.__statusNum = self.__statusNum + 0
        elif user_admin_of_group(self.userInfo, self.groupInfo):
            retval = False
            self.__status = u'administrator of'
            self.__statusNum = self.__statusNum + 0
        else:
            # The user is not the participation coach or the administrator
            # of the group
            sid = self.groupInfo.siteInfo.id
            gid = self.groupInfo.id
            uid = self.userInfo.id
            limit = self.mailingList.getValueFor('senderlimit')
            interval = self.mailingList.getValueFor('senderinterval')
            earlyDate = datetime.now(pytz.utc) - timedelta(seconds=interval)
            count = self.messageQuery.num_posts_after_date(sid, gid, uid, 
                                                           earlyDate)
            if count >= limit:
                # The user has made over the allowed number of posts in
                # the interval
                retval = True
                self.__status = u'the posting limit has been exceeded'
                self.__statusNum = self.__statusNum + 32
            else:
                retval = False
                self.__status = u'under the posting limit'
                self.__statusNum = self.__statusNum + 0
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
            self.__statusNum = self.__statusNum + 64
        else:
            retval = False
            self.__status = u'not blocked from posting'
            self.__statusNum = self.__statusNum + 0
        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def user_has_required_properties(self):
        '''The user must have the required properties filled out before
        he or she can post to the group — otherwise they would not be
        required, would they! The required properties can come from one
        of two places: the properties that are required for the site, and
        the properties required for the group. 
        '''
        requiredSiteProperties = self.get_required_site_properties()
        requiredGroupProperties = self.get_required_group_properties()
        requiredProperties = requiredSiteProperties + requiredGroupProperties
        
        retval = True
        self.__status = u'required properties set'
        for p in requiredProperties:
            if not(self.userInfo.get_property(p, None)):
              retval = False
              field = [a for n, a in self.get_site_properties() if n == p][0]
              self.__status = u'the required property %s is not set' %\
                field.title
              self.__statusNum = self.__statusNum + 128
              break
        assert type(self.__status) == unicode
        assert type(retval) == bool
        return retval

    def get_site_properties(self):
        '''Whole-heartly nicked from the GSProfile code, the site-wide
        user properties rely on a bit of voodoo: the schemas themselves
        are defined in the file-system, but which schema to use is stored
        in the "GlobalConfiguration" instance.
        '''
        if self.__profileInterfaces == None:
            assert hasattr(self.site_root, 'GlobalConfiguration')
            config = self.site_root.GlobalConfiguration
            interfaceName = config.getProperty('profileInterface',
                                               'IGSCoreProfile')
            assert hasattr(profileinterfaces, interfaceName), \
                'Interface "%s" not found.' % interfaceName
            profileInterface = getattr(profileinterfaces, interfaceName)
            self.__profileInterfaces =\
              interface.getFieldsInOrder(profileInterface)
        retval = self.__profileInterfaces
        return retval

    def get_required_site_properties(self):
        '''Site-properties are properties that are required to be a member
        of the site. It is very hard *not* to have required site-properties
        filled out, but as subscription-by-email is possible, we have to
        allow for the possibility.
        '''
        retval = [n for n, a in self.get_site_properties() if a.required]
        assert type(retval) == list
        return retval
        
    def get_required_group_properties(self):
        '''Required group properties are stored on the mailing-list 
        instance for the group. They are checked against the site-wide
        user properties, to ensure that it is *possible* to have the
        user-profile attribute filled.
        '''
        groupProps = self.mailingList.getProperty('required_properties', [])
        siteProps = [n for n, a in self.get_site_properties()]
        retval = []
        for prop in groupProps:
            if prop in siteProps:
                retval.append(prop)
        assert type(retval) == list
        return retval

