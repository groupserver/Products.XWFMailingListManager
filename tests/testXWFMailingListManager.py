# Copyright IOPEN Technologies Ltd., 2003
# richard@iopen.net
#
# For details of the license, please see LICENSE.
#
# You MUST follow the rules in README_STYLE before checking in code
# to the head. Code which does not follow the rules will be rejected.  
#
import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Testing import ZopeTestCase

ZopeTestCase.installProduct('XWFMailingListManager')

from Products.XWFMailingListManager import XWFMailingListManager
XWFMailingListManager.XWFMailingListManager
                                                             
from Products.XWFMailingListManager.XWFMailingListManager import XWFMailingListManager
class TestXWFMailingListManager(ZopeTestCase.ZopeTestCase):
    def afterSetUp(self):
        self.folder._setObject('ListManager', 
                               XWFMailingListManager('ListManager', 'List Manager'))
        
        self.mm = getattr(self.folder, 'ListManager', None)
        
    def afterClear(self):
        pass

    def test_01_exists(self):
        self.failUnless(self.mm)
    
if __name__ == '__main__':
    framework(descriptions=1, verbosity=1)
else:
    import unittest
    def test_suite():
        suite = unittest.TestSuite()
        suite.addTest(unittest.makeSuite(TestXWFMailingListManager))
        return suite
