#!/usr/bin/env python

import sys
from setuptools import setup, find_packages

if sys.hexversion < 0x30400f0:
    sys.stderr.write('madodl requires Python 3.4 or newer.\n')
    sys.exit(1)

exec(open('madodl/version.py').read()) # get __version__

setup(
    name='madodl'       ,
    version=__version__ ,
    description='madokami manga fetcher' ,
    author='miezak'               ,
    author_email='miezak@cock.li' ,
    url='https://github.com/miezak/madodl' ,
    license='BSD' ,
    classifiers=[
        'Development Status :: 3 - Alpha' ,
        'Environment :: Console' ,
        'Intended Audience :: End Users/Desktop' ,
        'License :: OSI Approved :: BSD License' ,
        'Operating System :: OS Independent' ,
        'Programming Language :: Python :: 3 :: Only' ,
        'Topic :: Internet :: File Transfer Protocol (FTP)' ,
        'Topic :: Internet :: WWW/HTTP'                     ,
        'Topic :: Text Processing'                          ,
    ] ,
    keywords='madokami manga' ,
    install_requires=['pycurl', 'pyyaml', 'unicurses==1.2'] ,
    dependency_links=['https://github.com/miezak/unicurses/archive/master.zip#egg=unicurses-1.2',] ,
    packages=find_packages() ,
    entry_points={
        'console_scripts' : [
            'madodl=madodl.main:main',
        ],
    } ,
)
