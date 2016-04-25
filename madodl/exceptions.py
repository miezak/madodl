#!/usr/bin/env python3

#
# custom exceptions
#

class Error(Exception):
    '''Base class for madodl exceptions.'''
    def __init__(self, msg):
        self._msg = msg

    def __repr(self):
        return 'madodl: {} {}'.format(self.__class__.__name__, self._msg)

class CurlError(Error):
    pass

class RequestError(Error):
    pass

class ConfigError(Error):
    pass
