# -*- coding: utf-8 -*-
############################################################################
#
# Copyright © 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012,
#             2013, 2014, 2015 OnlineGroups.net and Contributors.
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
from setuptools import setup, find_packages
import codecs
import os
from version import get_version

with codecs.open('README.rst', encoding='utf-8') as f:
    long_description = f.read()
with codecs.open(os.path.join("docs", "HISTORY.rst"),
                 encoding='utf-8') as f:
    long_description += '\n' + f.read()

setup(name='Products.XWFMailingListManager',
      version=get_version(),
      description="",
      long_description=long_description,
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          "Environment :: Web Environment",
          "Framework :: Zope2",
          "Intended Audience :: Developers",
          'License :: OSI Approved :: Zope Public License',
          "Natural Language :: English",
          "Operating System :: POSIX :: Linux",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2",
          "Programming Language :: Python :: 2.7",
          "Programming Language :: Python :: Implementation :: CPython",
          "Topic :: Software Development :: Libraries :: Python Modules",
      ],
      keywords='',
      author='Richard Waid',
      author_email='richard@iopen.net',
      maintainer='Michael JasonSmith',
      maintainer_email='mpj17@onlinegroups.net',
      url='https://github.com/groupserver/Products.XWFMailingListManager/',
      license='ZPL 2.1',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['Products'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'pytz',
          'SQLAlchemy',
          'zope.component',
          'zope.globalrequest',
          'zope.interface',
          'AccessControl',
          'Zope2',
          'gs.cache[redis]',  # With Redis support
          'gs.core',
          'gs.database',
          'gs.group.base',
          'gs.group.list.base',
          'gs.group.list.check',
          'gs.group.list.command',
          'gs.group.list.email.text',
          'gs.group.list.sender',
          'gs.group.list.store',
          'gs.group.member.canpost',
          'gs.profile.notify',
          'Products.GSAuditTrail',
          'Products.GSProfile',
          'Products.XWFCore',
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
