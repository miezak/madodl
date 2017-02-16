#!/usr/bin/env python3

#
# any functions relating to pycURL
#

import os
from   io import BytesIO
import re
import urllib.parse
import time
import pycurl
import unicurses

import madodl.util  as _util
import madodl.gvars as _g
from   madodl.exceptions import *

hdrs = {}
def curl_hdr(hdr_line):
    hdr_line = hdr_line.decode('iso-8859-1')

    if hdr_line[:5] == 'HTTP/':
        hdrs['retstr'] = re.sub('^[^ ]+ ', '', hdr_line)
        return

    if ':' not in hdr_line:
        return None

    name, val = hdr_line.split(':', 1)

    name = name.strip()
    val  = val.strip()

    hdrs[name.lower()] = val

    return None

def curl_debug(dbg_type, dbg_msg):
    _g.log.debug("{}: {}".format(dbg_type, dbg_msg.decode('iso-8859-1')))

    return None

def curl_common_init(buf):
    handle = pycurl.Curl()

    handle.setopt(pycurl.WRITEDATA, buf)
    handle.setopt(pycurl.HEADERFUNCTION, curl_hdr)
    handle.setopt(pycurl.DEBUGFUNCTION, curl_debug)

    handle.setopt(pycurl.USERPWD, '{}:{}'.format(_g.conf._user,_g.conf._pass))

    handle.setopt(pycurl.FOLLOWLOCATION, True)

    # avoid FTP CWD for fastest directory transversal
    handle.setopt(pycurl.FTP_FILEMETHOD, pycurl.FTPMETHOD_NOCWD)

    # we always set this flag and let the logging module
    # handle filtering.
    handle.setopt(pycurl.VERBOSE, True)

    # use ipv4 for VPNs
    handle.setopt(pycurl.IPRESOLVE, pycurl.IPRESOLVE_V4)
    handle.setopt(pycurl.USE_SSL, True)
    handle.setopt(pycurl.SSL_VERIFYPEER, False)
    # XXX
    handle.setopt(pycurl.SSL_VERIFYHOST, 0)

    return handle

def curl_json_list(fname, isf=False):
    '''Get the tree JSON output from stupidapi.

       Parameters:
       fname - file/buffer to send curl output to.
       isf - Specify whether fname is a file or not.

       Returns object that holds output.
    '''
    if isf:
        try:
            f = open(fname, 'wb')
            c = curl_common_init(f)
        except OSError:
            die("couldn't open file for writing")
    else:
        c = curl_common_init(fname)

    c.setopt(c.URL, 'https://{}{}dumbtree'.format(_g.loc['DOMAIN'],
                                                  _g.loc['API']))

    _g.log.info('curling JSON tree...')

    c.perform()
    c.close()

    return None

def curl_progress(ttdl, tdl, ttul, tul):
    _time = time.time()
    # ensure we are printing every 2 sec
    tdiff = _time - _g.conf._time

    if tdiff < 2:
        return

    if not _g.conf._fsz and ttdl:
        _g.conf._fsz = _util.conv_bytes(ttdl)

    _g.conf._time = _time

    dlspeed = (tdl - _g.conf._lastdl) / tdiff
    if ttdl:
        tdlperc = int((tdl / ttdl) * 100)
    else:
        tdlperc = 0

    dls_conv = _util.conv_bytes(dlspeed) + '/s'
    tdl_conv = _util.conv_bytes(tdl)

    # needed for pause/resume screen painting
    _g.conf._tdl_conv = tdl_conv

    # clear line manually since redrawln() isn't
    # working for me
    _g.conf._stdscr.addstr(2, 0, ' '*_g.conf._COLS)
    _g.conf._stdscr.refresh()
    _g.conf._stdscr.addstr(2, 0,
        'size {} | downloaded {} ({}%) | speed {}'.format(_g.conf._fsz,
                                                          tdl_conv, tdlperc,
                                                          dls_conv))
    _g.conf._stdscr.refresh()

    _g.conf._lastdl = tdl

    return None

def check_curl_error(h, fh, proto, exp=False):
    res = h.getinfo(h.RESPONSE_CODE)

    if proto == 'HTTP':
        okres = {0, 200} # OK
    elif proto == 'FTP':
        okres = {0, 226} # transfer complete

    if exp:
        fh.truncate()

        if res in okres:
            raise

        # XXX need to handle FTP too
        #msg = hdrs['retstr'] if hdrs['retstr'] else 'HTTP res: {}'.format(res)
        msg = 'retcode: {}'.format(res)

        raise CurlError(msg)

    if res not in okres:
        # XXX
        #raise CurlError(str(res))
        fh.truncate()

        if res == 401:
            msg = 'Bad user/password.'                     \
                if '' not in {_g.conf._user,_g.conf._pass} \
                else 'Insufficient authentication information given.'
        else:
            msg = hdrs['retstr']

        raise CurlError(msg)

    return None

def curl_to_file(url, fname, proto, port=None):
    _g.conf._fsz    = 0
    _g.conf._time   = 0
    _g.conf._lastdl = 0

    # unicurses doesn't seem to add these manually...
    _g.conf._LINES,_g.conf._COLS = unicurses.getmaxyx(_g.conf._stdscr)

    with open(os.path.join(_g.conf._outdir, fname), 'wb') as fh:
        c = curl_common_init(fh)

        c.setopt(c.URL, url) #'/'.join(rempath, urllib.parse.quote(fname)))
        c.setopt(c.NOPROGRESS, False)
        c.setopt(c.XFERINFOFUNCTION, curl_progress)
        if port:
            c.setopt(c.PORT, port)

        try:
            c.perform()
        except pycurl.error:
            check_curl_error(c, fh, proto, True)
        check_curl_error(c, fh, proto)

        c.close()

    return None

def curl_to_buf(url, proto, c=None, buf=None):
    if ((c   and buf is None) or
        (buf and c   is None)):
        _out.die('bad arguments!')

    if c is None:
        buf = BytesIO()
        c = curl_common_init(buf)

    c.setopt(c.URL, url)

    try:
        c.perform()
    except pycurl.error:
        check_curl_error(c, buf, proto, True)
    check_curl_error(c, buf, proto)

    c.close()

    return buf
