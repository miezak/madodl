#!/usr/bin/env python

from setuptools import setup

setup(
    name='madodl'   ,
    version='0.1.0' ,
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
    install_requires=['pycurl', 'pyyaml'] ,
    packages=['madodl'] ,
    entry_points={
        'console_scripts' : [
            'madodl=madodl.madodl:main',
        ],
    } ,
)
