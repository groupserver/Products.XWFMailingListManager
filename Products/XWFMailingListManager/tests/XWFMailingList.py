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
from mock import (patch, create_autospec)
import os
from unittest import TestCase
from Products.GSGroup import GSGroupInfo
import Products.XWFMailingListManager.XWFMailingList  # lint:ok
from Products.XWFMailingListManager.XWFMailingList import XWFMailingList


class XWFMailingListTest(TestCase):
    def setUp(self):
        self.mailingList = XWFMailingList('ethel', 'Ethel the Frog',
                                          'ethel@groups.example.com')
        self.groupInfo = create_autospec(GSGroupInfo, instance=True)

    @staticmethod
    def load_file_to_request(filename):
        retval = {}
        infilename = os.path.join('Products', 'XWFMailingListManager',
                                  'tests', 'emails', filename)
        with open(infilename, 'rb') as infile:
            emailData = infile.read()
        retval['Mail'] = emailData
        return retval

    @patch.object('Products.XWFMailingListManager.XWFMailingList.log')
    def test_outlook(self, log):
        req = self.load_file_to_request('ms-outlook-01.eml')
        with patch.object(self.mailingList, 'groupInfo'):

        self.mailingList.manage_listboxer(req)
