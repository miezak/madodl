#!/usr/bin/env python3

import os, sys
import re
from io import BytesIO
from html.parser import HTMLParser
from itertools import chain
import urllib.parse
import argparse
import logging
import logging.handlers
import pkg_resources
import time
import json

if sys.hexversion < 0x30400f0:
    sys.stderr.write('madodl requires Python 3.4 or newer.\n')
    sys.exit(1)

try:
    import unicurses
except ImportError:
    sys.stderr.write('Need UniCurses to use madodl!\n')
    sys.exit(1)

try:
    import pycurl
except ImportError:
    sys.stderr.write('Need pycURL to use madodl!\n')
    sys.exit(1)

try:
    import yaml
except ImportError:
    sys.stderr.write('Need PyYAML to use madodl!\n')
    sys.exit(1)

loc = {
    'DOMAIN'   : 'manga.madokami.com' ,
    'API'      : '/stupidapi/'        ,
    'USER'     : 'homura'             ,
    'PASS'     : 'megane'             ,
    'FTPPORT'  : 24430                ,
    'SFTPPORT' : 38460                ,
    'MLOC'     : '/Manga/'            ,
    'SEARCH'   : '/search?q='         ,
}

# emulate struct
class Struct: pass

def die(msg, lvl='error', **kwargs):
    if lvl:
      getattr(log, lvl.lower())(msg, **kwargs)
    sys.exit(1)

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
    val = val.strip()
    hdrs[name.lower()] = val

def curl_debug(dbg_type, dbg_msg):
    log.debug("%d: %s" % (dbg_type, dbg_msg.decode('iso-8859-1')))

def curl_common_init(buf):
    handle = pycurl.Curl()
    handle.setopt(pycurl.WRITEDATA, buf)
    handle.setopt(pycurl.HEADERFUNCTION, curl_hdr)
    handle.setopt(pycurl.DEBUGFUNCTION, curl_debug)
    handle.setopt(pycurl.USERPWD, '%s:%s' % (gconf._user, gconf._pass))
    handle.setopt(pycurl.FOLLOWLOCATION, True)
    handle.setopt(pycurl.VERBOSE, True)
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
    #c.setopt(c.ACCEPT_ENCODING, 'gzip')
    c.setopt(c.USE_SSL, True)
    c.setopt(c.SSL_VERIFYPEER, False)
    c.setopt(c.URL, 'https://'+loc['DOMAIN']+loc['API']+'dumbtree')
    log.info('curling JSON tree...')
    c.perform()
    c.close()

def conv_bytes(bvar):
    if bvar / 1024**3 >= 1:
        ret = str(round((bvar / 1024**3), 2)) + ' GB'
    elif bvar / 1024**2 >= 1:
        ret = str(round((bvar / 1024**2), 2)) + ' MB'
    elif bvar / 1024 >= 1:
        ret = str(round((bvar / 1024), 2)) + ' KB'
    else:
        ret = str(bvar) + ' B'

    return ret

def curl_progress(ttdl, tdl, ttul, tul):
    _time = time.time()
    # ensure we are printing every 2 sec
    tdiff = _time - gconf._time
    if tdiff < 2:
        return
    if not gconf._fsz and ttdl:
        gconf._fsz = conv_bytes(ttdl)
    gconf._time = _time
    dlspeed = (tdl - gconf._lastdl) / tdiff
    dls_conv = conv_bytes(dlspeed) + '/s'
    tdl_conv = conv_bytes(tdl)
    # clear line manually since redrawln() isn't
    # working for me
    gconf._stdscr.addstr(2, 0, ' '*gconf._COLS)
    gconf._stdscr.refresh()
    gconf._stdscr.addstr(2, 0, 'size %s | downloaded %s | speed %s' \
                     % (gconf._fsz, tdl_conv, dls_conv))
    gconf._stdscr.refresh()
    gconf._lastdl = tdl

def check_curl_error(h, fh, exp=False):
    res = h.getinfo(h.RESPONSE_CODE)
    if exp:
        fh.truncate()
        if res in (0, 200):
            raise
        msg = hdrs['retstr'] if hdrs['retstr'] \
        else 'HTTP res: %d' % res
        raise RuntimeError(msg)
    if res != 200:
        fh.truncate()
        if res == 401:
            msg = 'Bad user/password.'              \
            if '' not in (gconf._user, gconf._pass) \
            else 'Insufficient authentication information given.'
        else:
            msg = hdrs['retstr']
        raise RuntimeError(msg)

def curl_to_file(fname):
    gconf._fsz = 0
    gconf._time = 0
    gconf._lastdl = 0
    # unicurses doesn't seem to add these manually...
    gconf._LINES, gconf._COLS = unicurses.getmaxyx(gconf._stdscr)
    with open(os.path.join(gconf._outdir, fname), 'wb') as fh:
        c = curl_common_init(fh)
        c.setopt(c.URL, os.path.join(gconf._cururl, \
                 urllib.parse.quote(fname)))
        c.setopt(c.NOPROGRESS, False)
        c.setopt(c.XFERINFOFUNCTION, curl_progress)
        try: c.perform()
        except pycurl.error:
            check_curl_error(c, fh, True)
        check_curl_error(c, fh)
        c.close()

def curl_to_buf(url):
    buf = BytesIO()
    c = curl_common_init(buf)
    c.setopt(c.URL, url)
    try: c.perform()
    except pycurl.error:
        check_curl_error(c, buf, True)
    check_curl_error(c, buf)
    c.close()

    return buf

class ParseCommon:
    ''' ADDME '''

    ALL = float(1 << 32)

    def __init__(self):
        self._idx=0
        self._alltoks = []
        self._all = False
        self._vols = []
        self._chps = []

    def push_to_last(self, uval=False):
        val = uval if uval is not False else self.cur_tok_val()
        if self.last:
            log.debug(self.last)
            self._vols.append(val)
        else:
            log.debug(self.last)
            self._chps.append(val)

    def cur_tok_typ(self):
        if self._idx == len(self._alltoks):
            return None
        return self._alltoks[self._idx]['typ']

    def cur_tok_val(self):
        if self._idx == len(self._alltoks):
            return None
        return self._alltoks[self._idx]['val']

    def set_cur_tok_typ(self, newtyp):
        if self._idx == len(self._alltoks):
            return False
        self._alltoks[self._idx]['typ'] = newtyp
        return True

    def set_cur_tok_val(self, newval):
        if self._idx == len(self._alltoks):
            return False
        self._alltoks[self._idx]['val'] = newval
        return True

    def get_tok_typ(self, uidx):
        return self._alltoks[uidx]['typ']

    def get_tok_val(self, uidx):
        return self._alltoks[uidx]['val']

    def set_tok_typ(self, uidx, newtyp):
        self._alltoks[uidx]['typ'] = newtyp
        return True

    def set_tok_val(self, uidx, newval):
        self._alltoks[uidx]['val'] = newval
        return True

    def regex_mismatch(self, goodt, badt, uidx=False):
        log.warning('regex falsely picked up %s token as %s. ' \
                    'Replacing type.' % (goodt, badt))
        if uidx is not False:
            self._alltoks[uidx]['typ'] = goodt
        else:
            self._alltoks[self._idx]['typ'] = goodt

    def eat_delim(self, norng=False):
        self._idx += 1
        typtuple = ('DLM',) if norng else ('DLM', 'RNG')
        while self._idx < len(self._alltoks):
            if self._alltoks[self._idx]['typ'] in typtuple:
                if not norng and self._alltoks[self._idx]['typ'] == 'RNG':
                    self.regex_mismatch('DLM', 'RNG')
                    self._idx += 1
            else: break
            self._idx += 1

class ParseFile(ParseCommon):
    '''An inflexible title parser.

       This class parses a file with the expectation
       that there will be a volume/chapter number somewhere
       in the filename.
    '''
    def __init__(self, f, title):
        if not f:
            die('File parameter is empty!')
        ParseCommon.__init__(self)
        self._f = f
        self._tag = []
        self._title = ''
        # Token abbreviations:
        # EXT -> Extension
        # GRB -> Group Beginning
        # GRE -> Group End
        # RNG -> Range
        # DLM -> Delimiter
        # VOL -> Volume
        # CHP -> Chapter
        # ALL -> Complete Archive
        # ART -> Artbook
        # PLT -> Pilot
        # PRL -> Prolog
        # PRE -> Prelude
        # PRO -> Prototype
        # OMK -> Omake
        # NUM -> Number
        # COM -> Comma Separator
        # DAT -> Data
        #
        # Multi-character alpha regex have to
        # be checked in a certain order because
        # they are then grouped with logical `ORs`.
        # In case of mismatches, The logic following
        # the matching trys to sort out the tokens in
        # a somewhat sane matter.
        #
        # NOTE: anything starting with `v` needs to be put _before_ VOL
        #       anything starting with `c` needs to be put _before_ CHP
        tok_spec = [
            ('EXT', r'\.[^\.]+$')    ,
            ('GRB', r'(\(|\[|<|\{)') ,
            ('GRE', r'(\)|\]|>|\})') ,
            ('RNG', r'(-|\.\.)')     ,
            ('DLM', r'(-|_|\.|\s+)') ,
            ('VOL', r'''(?x)
                        v(ol(ume)?)?
                        (?=(-|_|\.|\s+)*[0-9]) # look-ahead assertion
                     ''') ,
            ('CHP', r'''(?x)
                        (c(h(a?p(ter)?)?)?|e(p(isode)?)?)
                        (?=(-|_|\.|\s+)*[0-9])
                     ''') ,
            ('ALL', r'complete')  ,
            ('ART', r'artbook')   ,
            ('PLT', r'pilot')     ,
            ('PRL', r'prologu?e') ,
            ('PRE', r'prelude')   ,
            ('PRO', r'prototype') ,
            ('OMK', r'''(?x)
                        \+?(?=(-|_|\.|\s+)*)
                        (omake|extra|bonus|special)
                     ''') ,
            ('NUM', r'\d+(\.\d+)?') ,
            ('COM', r',')           ,
            ('DAT', r'.')           ,
        ]
        tok_regex = '|'.join('(?P<%s>%s)' % p for p in tok_spec)

        for t in re.finditer(tok_regex, f, flags=re.I):
            typ = t.lastgroup
            val = t.group(typ)
            self._alltoks.append({'typ' : typ, 'val' : val})

        if self._alltoks[-1]['typ'] != 'EXT':
            die('Encountered a file without an extension, which is '\
                         'not currently supported. Bailing.', lvl='FATAL')

        for t in self._alltoks:
            if t['typ'] == 'NUM':
                t['raw'] = t['val']
                t['val'] = float(t['val'])

        # variable stores whether vol or chp
        # was seen last. True = vol, False = chp
        self.last = None
        self.seenchp = False
        self.seenvol = False
        self.other = None
        wildnums = []
        while self._idx < len(self._alltoks):
            t = self.cur_tok_typ()
            log.debug(str(self._idx)+' '+t)
            if t == 'VOL':
                self.last = True
                if not self.seenvol:
                    self.seenvol = True
                vidx = self._idx
                self.eat_delim()
                if self.cur_tok_typ() != 'NUM':
                    self.regex_mismatch('DAT', 'VOL', vidx)
                    self._idx += 1 ; continue
                vval = self.cur_tok_val()
                self._vols.append(vval)
                # we need this line in case of a range
                # with a fractional e.g. vol1.5-3 in which
                # case we assume the successive volumes are
                # whole volumes.
                vval = int(vval) + 1
                self.eat_delim(True)
                if self.cur_tok_typ() == 'RNG':
                    self.eat_delim()
                    if self._idx == len(self._alltoks):
                        # open-ended range
                        self._vols.append(vidx)
                        self._vols.append(self.ALL)
                        continue
                    elif self.cur_tok_typ() == 'NUM':
                        for n in range(vval, int(self.cur_tok_val()+1)):
                            self._vols.append(float(n))
                        if self.cur_tok_val() % 1:
                            self._vols.append(self.cur_tok_val())
                        self._idx += 1
                continue # XXX
            elif t == 'CHP':
                self.last = False
                if not self.seenchp:
                    self.seenchp = True
                cidx = self._idx
                self.eat_delim()
                if self.cur_tok_typ() != 'NUM':
                    self.regex_mismatch('DAT', 'VOL', vidx)
                    self._idx += 1 ; continue
                cval = self.cur_tok_val()
                self._chps.append(cval)
                # we need this line in case of a range
                # with a fractional e.g. vol1.5-3 in which
                # case we assume the successive volumes are
                # whole volumes.
                cval = int(cval) + 1
                self.eat_delim(True)
                if self.cur_tok_typ() == 'RNG':
                    self.eat_delim()
                    if self._idx == len(self._alltoks):
                        # open-ended range
                        self._vols.append(vidx)
                        self._vols.append(self.ALL)
                        continue
                    elif self.cur_tok_typ() == 'NUM':
                        for n in range(cval, int(self.cur_tok_val()+1)):
                            self._chps.append(float(n))
                        if self.cur_tok_val() % 1:
                            self._chps.append(self.cur_tok_val())
                        self._idx += 1
                continue # XXX
            elif t == 'COM':
                if self.last is None:
                    self.regex_mismatch('DAT', 'COM')
                    continue
                comidx = self._idx
                self.eat_delim()
                if self.cur_tok_typ() != 'NUM':
                    self.regex_mismatch('DAT', 'COM', comidx)
                    continue
                comval = self.cur_tok_val()
                self.push_to_last(comval)
                self.eat_delim(True)
                if self.cur_tok_typ() == 'RNG':
                    comval = int(comval) + 1
                    self.eat_delim()
                    if self.cur_tok_typ() == 'NUM':
                        for n in range(comval, int(self.cur_tok_val())+1):
                            self.push_to_last(float(n))
            elif t == 'RNG':
                self.regex_mismatch('DLM', 'RNG')
            elif t == 'NUM':
                # spotted a number without a vol/chp prefix
                nidx = self._idx
                self.eat_delim(True)
                if self.cur_tok_typ() == 'COM':
                    self.eat_delim()
                    if self.cur_tok_typ() != 'NUM':
                        self.regex_mismatch('DAT', 'NUM', nidx)
                        self.regex_mismatch('DAT', 'COM')
                        self._idx += 1 ; continue
                    wildnums.append(self._alltoks[nidx])
                elif self.cur_tok_typ() == 'RNG':
                    self.eat_delim()
                    if self.cur_tok_typ() != 'NUM':
                        self.regex_mismatch('DAT', 'NUM', nidx)
                        self.regex_mismatch('DAT', 'RNG')
                        self._idx += 1 ; continue
                    st = self.cur_tok_val()
                    self._alltoks[nidx]['val'] = tmprng = []
                    tmprng.append(st)
                    rngb = int(st) + 1
                    for n in range(rngb, int(self.cur_tok_val())+1):
                        tmprng.append(float(n))
                    if self.cur_tok_val() % 1:
                        tmprng.append(float(self.cur_tok_val()))
                    wildnums.append(self._alltoks[nidx])
                elif self.cur_tok_typ() == 'DAT':
                    self.regex_mismatch('DAT', 'NUM')
                else:
                    wildnums.append(self._alltoks[nidx])
            elif t in ('PLT', 'PRE', 'PRL', 'ART'):
                # shouldn't have vol/chp
                if self._vols or self._chps:
                    self.regex_mismatch('DAT', 't')
                    self._idx += 1 ; continue
                self.other = t
            elif t == 'OMK':
                # probably should have vol/chp
                if not self._vols and not self._chps:
                    log.warning('regex picked up a bonus type without '\
                                'a vol/chp identifier, which may be '  \
                                'incorrect. Adding anyway...')
                self.other = t
            elif t == 'ALL':
                self._all = True
            elif t == 'GRB':
                if self.get_tok_typ(self._idx+1) not in ('VOL', 'CHP', 'ALL', \
                                              'OMK', 'PLT', 'PRE',            \
                                              'PRL', 'ART'):
                    self._idx += 1
                    if self.cur_tok_typ() == 'NUM' and \
                       self.get_tok_typ(self._idx+1) != 'DAT':
                        continue
                    tmptag = ''
                    while self.cur_tok_typ() not in ('GRE', None):
                        tmptag += str(self.cur_tok_val())
                        self._idx += 1
                    if self.cur_tok_val() == None:
                        die('BUG: tag matching couldn`t find GRE')
                    if tmptag[:len(title)].lower().strip() == title.lower():
                        if self.get_tok_typ(self._idx-1) in \
                            ('PLT', 'PRE', 'PRO', 'PRL', 'ART', 'OMK'):
                            continue # non-group tag with title in text
                    self._tag.append(tmptag)
            elif t == 'DAT':
                self._title += self.cur_tok_val()
                if self.get_tok_val(self._idx+1) == ' ':
                    self._title += ' '

            self._idx += 1

        if wildnums:
            # These are numbers that did not have
            # a prefix, so we do our best to guess.
            wnls = [n['val'] for n in wildnums]
            wnsubls = []
            for n in wnls:
                if isinstance(n, list):
                    wnls.extend(n)
                    wnsubls.append(n)
            if wnsubls:
                for l in wnsubls: wnls.remove(l)
            del wnsubls
            if len(wildnums[0]['raw']) >= 3:
                dot = wildnums[0]['raw'].find('.')
                if dot != -1 and dot < 2:
                    pass
                else:
                    self._chps.extend(sorted(wnls))
            elif not self._vols and not self._chps:
                if not max(wnls) % 100:
                    # assuming chp
                    self._chps.extend(sorted(wnls))
                else:
                    # assuming vol
                    self._vols.extend(sorted(wnls))
            elif not self._vols:
                # assuming vol
                self._vols.extend(sorted(wnls))
            elif not self._chps:
                # assuming chp
                self._chps.extend(sorted(wnls))

        self._title = self._title.strip()

        self._vols = sorted(set(self._vols))
        self._chps = sorted(set(self._chps))

class ParseRequest(ParseCommon):
    ''' ADDME '''

    def __init__(self, req):
        ParseCommon.__init__(self)
        self._name = req[0]
        del req[0]
        if not req:
            self._all = True
            return
        for vc in req:
            vc = re.sub(r'\s', '', vc)
            vc = vc.lower()
        if 'all' in req:
            self._all = True
            del req[0]
            if req: del req[0]
            return
        tok_spec =  [
            ('VOL', r'v(ol)?')      ,
            ('CHP', r'ch?p?')       ,
            ('NUM', r'\d+(\.\d+)?') ,
            ('RNG', r'-')           ,
            ('COM', r',')           ,
            ('BAD', r'.')           ,
        ]
        tok_regex = '|'.join('(?P<%s>%s)' % p for p in tok_spec)
        for vc in req:
            self._alltoks = []
            for t in re.finditer(tok_regex, vc):
                typ = t.lastgroup
                val = t.group(typ)
                if typ == 'BAD':
                    raise RuntimeError('bad char %s' % val)
                self._alltoks.append({'typ' : typ, 'val' : val})
            what = self.get_tok_typ(0)
            if what not in ('VOL', 'CHP'):
                if what != 'NUM':
                    raise RuntimeError('bad vol/ch format')
                else:
                    log.warning('No vol/ch prefix. Assuming volume.')
                    what = 'VOL'
                    tmp = [0 for z in range(len(self._alltoks)+1)]
                    for idx in range(len(self._alltoks)):
                        tmp[idx+1] = self._alltoks[idx]
                    self._alltoks = tmp
            elif len(self._alltoks) == 1 or self.get_tok_typ(1) != 'NUM':
                raise RuntimeError('no number specified for %s' % what)
            self.last = True if what == 'VOL' else False
            prev = []
            for idx in range(1, len(self._alltoks)):
                typ = self.get_tok_typ(idx)
                if typ == 'NUM':
                    if prev:
                        tmpv = self.get_tok_val(idx)[:]
                        tmpm = min(prev)
                        if tmpv < tmpm:
                            self.set_tok_val(minidx, tmpv)
                            self.set_tok_val(idx, tmpm)
                            minidx = idx
                            prev.append(tmpv)
                    else:
                        prev.append(self.get_tok_val(idx))
                        minidx = idx
            tokcpy = self._alltoks[:]
            self._idx = idx = 1
            while idx < len(self._alltoks)+1:
                typ = self.cur_tok_typ()
                val = self.cur_tok_val()
                log.debug(str(typ)+' '+str(val))
                if typ is None: break
                if typ == 'RNG':
                    if self._idx == len(self._alltoks)-1:
                        if self.get_tok_typ(self._idx-1) != 'NUM':
                            raise RuntimeError('bad range for %s' % what)
                        else:
                            self.push_to_last(self.ALL)
                            break
                    if ((self.get_tok_typ(self._idx-1) != 'NUM' and \
                         self.get_tok_typ(self._idx+1) != 'NUM') or \
                         self.get_tok_typ(self._idx+1) == 'COM'):
                        raise RuntimeError('bad range for %s' % what)
                    st = int(self.get_tok_val(self._idx-1))+1
                    end = float(self.get_tok_val(self._idx+1))
                    for n in range(st, int(end)+1):
                        self.push_to_last(float(n))
                    if end % 1:
                        self.push_to_last(end)
                    self._idx += 1
                elif typ == 'COM':
                    if self._idx == len(self._alltoks)-1 or \
                       self._alltoks[self._idx+1]['typ'] != 'NUM':
                        log.warning('Extraneous comma detected. Removing.')
                        del self._alltoks[self._idx]
                        continue
                    else:
                        self._idx += 1
                        self.push_to_last(float(self.cur_tok_val()))
                elif typ == 'NUM':
                    self.push_to_last(float(self.cur_tok_val()))

                self._idx += 1

            self._vols = sorted(set(self._vols))
            self._chps = sorted(set(self._chps))

class ParseQuery(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.lasttag = None
        self.resultnum = None
        self.results = []
        self.h1b = False
        self.h1e = False
        self.contb = False
        self.conte = False
        self.cont_td = False
        self.prev = None

    def handle_starttag(self, tag, attr):
        if tag == 'h1':
            self.h1b = True
        elif tag == 'div':
            if ('class', 'container') in attr:
                self.contb = True
        if tag == 'a' and self.prev == 'td' and self.contb and not self.conte:
            self.cont_td = True
            self.href = attr[0][1]
        else: self.cont_td = False
        self.prev = tag

    def handle_endtag(self, tag):
        if tag == 'h1':
            self.h1e = True
        elif tag == 'div' and self.contb:
            self.conte = True

    def handle_data(self, data):
        if self.h1b and not self.h1e:
            data = data.lstrip().rstrip()
            if data.startswith('Search'):
                self.resultnum = int(data[-2])
        if self.contb and not self.conte:
            if self.cont_td:
                if data.strip():
                    if data[0] != '/':
                        self.results[-1][1] += data
                    else:
                        self.results.append([self.href,data])

def create_nwo_path(name):
    '''Create the exact path that the manga `name` should be in.

       This path is constructed in the `New World Order` format
       described here: manga.madokami.com/Info/NewWorldOrder.txt

       Parameters:
       name - the name of the manga to convert to NWO format.
    '''
    if not name:
        die('need a name with at least one character!')
        return None
    name = re.sub(r'^(the|an?) ', '', name, flags=re.I)
    name = name.upper()
    return re.sub(r'^(.)(.|)?(.|)?(.|)?.*', r'\1/\1\2/\1\2\3\4', name)

def search_exact(name='',ml=False):
    buf = BytesIO()
    path = create_nwo_path(name) if not ml else ''
    c = curl_common_init(buf)
    c.setopt(c.DIRLISTONLY, True)
    c.setopt(c.USE_SSL, True)
    c.setopt(c.SSL_VERIFYPEER, False)
    c.setopt(c.USERPWD, loc['USER']+':'+loc['PASS'])
    c.setopt(c.PORT, loc['FTPPORT'])
    ml = loc['MLOC'] if not ml else ''
    log.info('ftp://'+loc['DOMAIN']+ml+path+'/'+name+'/')
    gconf._cururl = \
    os.path.join('https://', loc['DOMAIN'], ml, path) + name
    c.setopt(c.URL, 'ftp://'+loc['DOMAIN']+ml+path+'/'+name+'/')
    c.perform()
    c.close()
    return buf

def search_query(name=''):
    return curl_to_buf('https://'+loc['DOMAIN']+loc['SEARCH']+name)

## Helper Functions ##

def rm_req_elems(req, comp):
    for n in comp:
        if n in req:
            req.remove(n)

def common_elem(iter1, iter2):
    assert iter1 and iter2
    loc1 = iter1 ; loc2 = iter2
    for elem in loc1:
        if elem in loc2:
            yield elem

    return

######################

def apply_tag_filters(f, title, cv, cc):
    f._preftag  = False
    f._npreftag = False
    if not f._tag or not gconf._alltags:
        return True
    tlow = [t.lower() for t in f._tag]
    titlel = title.lower()
    for t in gconf._alltags:
        if t._for != 'all':
            for d in t._for:
                for k in d:
                    if titlel == k.lower():
                        break
            else: continue
            for v in f._vols:
                if v in cv:
                    break
            else: continue
            for c in f._chps:
                if c in cc:
                    break
            else: continue
        log.info('N '+t._name+' '+t._filter+' '+t._case+' '+str(tlow))
        log.info('NN '+str(t._name.lower() in tlow))
        if t._name.lower() in tlow:
            if (t._case == 'exact' and t._name not in f._tag) or \
               (t._case == 'upper' and t._name not in \
                                       [t.upper() for t in f._tag]):
                return False
            curt = t._name.lower()
            if t._filter == 'out':
                del f
                return False
            # TODO: handle `for` sub-opt for pref
            if t._filter == 'prefer':
                f._preftag = True
            elif t._filter == 'not prefer':
                f._npreftag = True
        else:
            if t._filter == 'only':
                del f
                return False
    return True

def check_preftags(vc, vcq, fo, allf, npref, v_or_c):
    if v_or_c:
        ftupidx = 1
        what = 'vol'
        whatls = fo._vols
    else:
        ftupidx = 2
        what = 'chp'
        whatls = fo._chps
    if fo._preftag:
            for ftup in allf:
                if vc in ftup[ftupidx]:
                    log.info('replacing %s with preferred'\
                             ' tag %s' % (ftup[0], fo._f))
                    allf.remove(ftup)
                    vcq.extend(whatls)
                    return 'break'
            else:
                die("BUG: couldn't find any dup %s in %s "\
                    "when replacing with pref tag" % (what, whatls), \
                    lvl='critical')
    elif not fo._npreftag and npref:
        for t in npref:
            if vc in t[ftupidx]:
                tup = t ; break
        else:
            log.warning('dup vol and chps seen')
            return 'break'
        log.info('replacing nonpreferred %s '\
                 'with %s' % (tup[0], fo._f))
        allf.remove(tup)
        npref.remove(tup)
        return 'continue'

    return None

def walk_thru_listing(req, title, dir_ls):
    '''Walk through FTP directory listing and extract requested data.

       Parameters:
       req - User requested files.
       title - Title of the series requested.
       dir_ls - FTP directory listing.

       Returns a 4-tuple of three lists and one str.

       The objects contain, in order:
       matched (volumes, chapters, filenames), and the complete archive
       filename (if matched) in the case that all volumes are requested.
    '''
    compv = []
    compc = []
    allf = []
    npref = []
    compfile = None
    if req._vols and req._vols[-1] == req.ALL:
        oerng_v = True
        oest_v = req._vols[-2]
    else: oerng_v = False
    if req._chps and req._chps[-1] == req.ALL:
        oerng_c = True
        oest_c = req._chps[-2]
    else: oerng_c = False
    reqv_cpy = req._vols[:]
    reqc_cpy = req._chps[:]
    for f in dir_ls.splitlines():
        # FIXME:
        # handle this in a more fail-safe manner.
        if f == 'Viz Releases':
            continue # a common sub-dir
        fo = ParseFile(f, title)
        if not apply_tag_filters(fo, title, compv, compc):
            log.info('** filtered out ' + fo._f)
            continue
        vq = [] ; cq = []
        apnd = False
        if fo._all and req._all:
            # XXX need pref filt handling here
            log.info('found complete archive')
            log.info('file - %s' % f)
            compfile = f
            break
        elif req._all and not req._vols:
            for c in fo._chps:
                if c not in cq and c not in compc:
                    cq.append(c)
                else:
                    act = check_preftags(fov, vq, fo, allf, npref, True)
                    if isinstance(act, str):
                        if fo._preftag:
                            continue
                        if act == 'break': break
                        cq.append(c)
                        continue
                    cq = [] ; break
        for fov in fo._vols:
            if (oerng_v and fov >= oest_v) or req._all or fov in req._vols:
                if fov in compv: # already seen this vol
                    for foc in fo._chps: # then check if vol is split
                        if compc and foc not in compc: # with all new chps
                            continue # is new
                        else:
                            act = check_preftags(fov, vq, fo, allf, npref, True)
                            if isinstance(act, str):
                                log.info('ACT '+act)
                                if fo._preftag:
                                    apnd = True
                                if act == 'break'   : break
                                if act == 'continue':
                                    # always npref
                                    apnd = True
                                    continue
                            break
                    else: # all new
                        apnd = True
                        vq.append(fov)
                else:
                    apnd = True
                    vq.append(fov)
        if apnd:
            cq.extend(fo._chps)

        # XXX the chapter logic is really hackish and probably
        # needs to be completely rewritten.
        if len(req._chps) > 1 and len(fo._chps) == len(req._chps) \
           and req._chps[0] == fo._chps[0]:
            rmax = None
            fomax = None
            last = req._chps[0]
            for i in range(1, len(req._chps)):
                if req._chps[i] == last+1:
                    rmax = req._chps[i]
                else: break
                last = req._chps[i]
            last = fo._chps[0]
            for i in range(1, len(fo._chps)):
                if fo._chps[i] == last+1:
                    fomax = fo._chps[i]
                else: break
                last = fo._chps[i]
            if None in {rmax, fomax} or rmax != fomax:
                pass
            else:
                #iter_celems = common_elem(req.chps, (cq, compc))
                #for cclash in iter_celems:
                #    pass # ADDME do chk...
                for i in req._chps:
                    if i <= rmax:
                        cq.append(float(i))
                    else: break
        #if len(fo._chps) == 1: # only a single chp
        if req._chps:
            if oerng_c and fo._chps and min(fo._chps) >= oest_c:
                for c in fo._chps:
                    if c in cq or c in compc:
                        act = check_preftags(c, cq, fo, allf, npref, False)
                        if act == 'break'   : break
                        if act == 'continue': continue
                        break
                else:
                    if fo._chps and min(fo._chps) >= oest_c:
                        cq.extend(fo._chps)
            else:
                for c in req._chps:
                    if (req._all or c in fo._chps) and c not in cq:
                        if c not in compc:
                            cq.append(c)
                        else:
                            act = check_preftags(c, cq, fo, allf, npref, False)
                            if act == 'break'   : break
                            if act == 'continue':
                                # always npref, continue is simply explicit
                                cq.append(c)
                                continue
        if vq:
            log.info('found vol %s ' % str(vq))
        if cq:
            log.info('found chp %s ' % str(cq))
        if vq or cq:
            if fo._npreftag:
                npref.append((f, vq, cq))
            allf.append((f, vq, cq))
            log.info('file - %s' % f)
        compv.extend(vq)
        compc.extend(cq)
        rm_req_elems(reqv_cpy, vq)
        rm_req_elems(reqc_cpy, cq)
        compv = list(set(compv))
        compc = list(set(compc))
    compv = sorted(compv)
    compc = sorted(compc)
    return (compv, compc, allf, compfile)

def _(msg, file=sys.stderr, **kwargs):
    if not gconf._no_output:
        print('%s: %s' % (os.path.basename(__file__), msg), file=file, **kwargs)

def init_args():

    def output_file(f):
        f = os.path.normpath(f)
        if not os.path.exists(f):
            try:
                os.makedirs(f)
            except PermissionError:
                raise argparse.ArgumentTypeError('Insufficient permissions to '\
                    'create %s directory.' % f)
            except NotADirectoryError:
                raise argparse.ArgumentTypeError('Non-directory in path.')
        elif not os.path.isdir(f):
            raise argparse.ArgumentTypeError('%s is not a directory.' % f)
        elif not os.access(f, os.R_OK | os.W_OK | os.X_OK):
            raise argparse.ArgumentTypeError( \
                'Insufficient permissions to write to %s directory.' % f)
        if f[-1] != os.sep:
            f += os.sep

        return f

    try:
         _version = pkg_resources.get_distribution('madodl').version
    except pkg_resources.DistributionNotFound:
        _version = '(local)'

    args_parser = \
    argparse.ArgumentParser(description='Download manga from madokami.',   \
                            usage='%(prog)s [-dhsv] [-p ident val ...] '   \
                                            '-m manga '                    \
                                            '[volume(s)] [chapter(s)] ... '\
                                            '[-o out-dir]')
    args_parser.add_argument('-d', action='store_true', dest='debug', \
                             help='print debugging messages')
    args_parser.add_argument('-s', action='store_true', dest='silent', \
                             help='silence message output')
    args_parser.add_argument('-v', action='store_true', dest='verbose', \
                             help='print verbose messages')
    args_parser.add_argument('-V', '--version', action='version',
                             version='madodl ' + _version)
    args_parser.add_argument('-m', nargs='+', action='append', dest='manga', \
                             required=True,                                  \
                             metavar=('manga', 'volume(s) chapter(s)'),      \
                             help='''
                                  The name of the manga to download.
                                  If only the manga title is given, all manga
                                  under this name are downloaded. otherwise, -m
                                  takes a list of volumes and/or a list of
                                  chapters to download.
                                  ''')
    args_parser.add_argument('-o', type=output_file, dest='outdir', \
                             metavar='outdir', \
                             help='directory to save files to')
    args_parser.add_argument('-a', dest='auth', metavar='user:pw',
                            help='madokami user and password')
    args = args_parser.parse_args()
    if args.silent:
        loglvl = logging.CRITICAL
    elif args.debug:
        loglvl = logging.DEBUG
    elif args.verbose:
        loglvl = logging.INFO
    else:
        loglvl = logging.ERROR
    global log, silent
    silent = args.silent
    log = logging.getLogger('stream_logger')
    log.setLevel(loglvl)
    cons_hdlr = logging.StreamHandler()
    cons_hdlr.setLevel(loglvl)
    logfmt = logging.Formatter('%(filename)s: %(funcName)s(): ' \
                               '%(levelname)s: %(message)s')
    cons_hdlr.setFormatter(logfmt)
    log.addHandler(cons_hdlr)

    return args

# global config struct
gconf = Struct()

def nullfilter(r): return 0

def logfile_filter(record):
    if gconf._loglevel == 'all':
        return 1
    if (record.levelname == 'DEBUG' and gconf._loglevel != 'debug') or \
       (record.levelname == 'INFO' and gconf._loglevel != 'verbose'):
        return 0

    return 1

def init_config():
    c = None
    alltags = []
    global gconf
    VALID_OPTS = (
        'tags',
        'no_output',
        'logfile',
        'loglevel',
        'usecache',
        'cachefile',
        'user',
        'pass',
    )
    class TagFilter:
        VALID_CASE = (
            'lower' ,
            'upper' ,
            'any'   ,
            'exact' ,
        )
        VALID_FILTER = (
            'only'       ,
            'out'        ,
            'prefer'     ,
            'not prefer' ,
        )
        DEFAULT_CASE = 'any'
        DEFAULT_FILTER = 'prefer'
        DEFAULT_FOR = 'all'
        def __init__(self, tag, default=False):
            self._tag = tag
            self._for = []
            if 'name' not in self._tag:
                log.error('empty name in config tag filter')
                raise yaml.YAMLError
            self._name = self._tag['name']
            if default:
                self._case = self.DEFAULT_CASE
                self._filter = self.DEFAULT_FILTER
                self._for = self.DEFAULT_FOR
                return
            if 'case' not in self._tag:
                self._case = self.DEFAULT_CASE
            else: self._case = self._tag['case']
            if 'filter' not in self._tag:
                self._filter = self.DEFAULT_FILTER
            else: self._filter = self._tag['filter']
            if 'for' not in self._tag:
                self._for = self.DEFAULT_FOR
            if self._case not in self.VALID_CASE:
                log.error('bad case value for %s' % self._tag['name'])
                self._case = self.DEFAULT_CASE
            if self._filter not in self.VALID_FILTER:
                log.error('bad filter value for %s' % self._tag['name'])
                self._filter = self.DEFAULT_FILTER
            if self._for == 'all' or self._tag['for'] in ('all',['all']):
                return
            else:
                log.warning('madodl currently only handles the value '\
                            '`all` for tag filters, and will handle ' \
                            'any filters as if such.')
                for kv in self._tag['for']:
                    for name in kv:
                        r = ParseRequest(list( \
                        chain.from_iterable(   \
                        [[name],kv[name].split()])))
                        self._for.append({name : r})

    def set_simple_opt(yh, opt, vals, default):
        if opt in yh:
            if not yh[opt]:
               setattr(gconf, '_'+opt, default)
            elif default is None and not vals:
                setattr(gconf, '_'+opt, yh[opt])
            elif yh[opt] in vals:
                setattr(gconf, '_'+opt, yh[opt])
            else:
                log.error('bad config value for %s' % opt)
                setattr(gconf, '_'+opt, default)
        else:
            setattr(gconf, '_'+opt, default)

    h = os.path.expanduser('~')
    gconf._home = h
    if os.name == 'posix':
        if os.path.exists('{0}/.config/madodl/config.yml'.format(h)):
            c = '{0}/.config/madodl/config.yml'.format(h)
        elif os.path.exists('{0}/.madodl/config.yml'.format(h)):
            c = '{0}/.madodl/config.yml'.format(h)
        elif os.path.exists('{0}/.madodl.yml'.format(h)):
            c = '{0}/.madodl.yml'.format(h)
        else:
            log.warning('log file not found. using defaults.')
    elif os.name == 'nt':
        if os.path.exists('{0}\.madodl\config.yml'.format(h)):
            c = '{0}\.madodl\config.yml'.format(h)
        else:
            log.warning('log file not found. using defaults.')
    else:
        log.warning('madodl doesn`t current support a config file on your OS. '\
                    'Using defaults.')
    if not c:
        # XXX check back
        # FIXME: these should be None!
        gconf._user = ''
        gconf._pass = ''
        gconf._alltags = ''
        gconf._default_outdir = os.getcwd()
        gconf._no_output = False
        gconf._usecache = False
        gconf._cachefile = None
        return
    with open(c) as cf:
        try:
            yh = yaml.safe_load(cf)
            for opt in yh.keys():
                if opt not in VALID_OPTS:
                    raise RuntimeError('bad option `%s` in config file' % opt)
            if 'tags' in yh and yh['tags']:
                for t in yh['tags']:
                    alltags.append(TagFilter(t))
            gconf._alltags = alltags
            binopt = (True, False)
            set_simple_opt(yh, 'no_output', binopt, False)
            set_simple_opt(yh, 'logfile', None, None)
            if gconf._logfile:
                set_simple_opt(yh, 'loglevel', ('verbose', 'debug', 'all'), \
                               'verbose')
                if gconf._loglevel in ('debug', 'all'):
                    loglvl = logging.DEBUG
                else:
                    loglvl = logging.INFO
                # by default, log files will rotate at 10MB with one bk file.
                logfile_hdlr = logging.handlers.RotatingFileHandler \
                (gconf._logfile, maxBytes=10e6, backupCount=1)
                logfile_hdlr.setLevel(loglvl)
                logfile_hdlr.addFilter(logfile_filter)
                log.addHandler(logfile_hdlr)
            else: gconf._loglevel = None
            set_simple_opt(yh, 'usecache', binopt, False)
            if gconf._usecache:
                set_simple_opt(yh, 'cachefile', None, \
                           os.path.join(h, '.cache', 'madodl', 'files.json'))
            else: gconf._cachefile = None
            set_simple_opt(yh, 'default_outdir', None, os.getcwd())
            set_simple_opt(yh, 'user', None, None)
            if gconf._user:
                set_simple_opt(yh, 'pass', None, None)
            else: gconf._pass = None
        except yaml.YAMLError as e:
            log.error('config file error: %s' % str(e))

class breaks(object):
# Great idea from:
# http://stackoverflow.com/a/23665658
    class Break(Exception):
      """Break out of the with statement"""

    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value.__enter__()

    def __exit__(self, etype, value, traceback):
        error = self.value.__exit__(etype, value, traceback)
        if etype == self.Break:
            return True
        return error

def get_listing(manga):
    badret = ('', '')
    if gconf._usecache:
        def match_dir(diriter, ldict):
            global mlow
            try:
                cdir = next(diriter)
            except StopIteration:
                for cdict in ldict:
                    if cdict['name'].lower() == mlow:
                        return (cdict['contents'], cdict['name'])
                return None
            for cdict in ldict:
                if cdict['name'] == cdir:
                    return match_dir(diriter, cdict['contents'])
            else: return None
        jsonloc =                                                   \
        os.path.join(gconf._home, '.cache', 'madodl', 'files.json') \
        if not gconf._cachefile else gconf._cachefile
        jsondirloc = os.path.dirname(jsonloc)
        if not os.path.exists(jsonloc):
            os.makedirs(jsondirloc, 0o770, True)
            curl_json_list(jsonloc, True)
        assert os.path.exists(jsonloc)
        d1,d2,d3 = create_nwo_path(manga).split('/')
        mdir = None
        with breaks(open(jsonloc, errors='surrogateescape')) as f:
            jobj = json.load(f)
            for o in jobj[0].get('contents'):
                if o['name'] == 'Manga':
                    jobj = o['contents'] ; break
            global mlow
            mlow = manga.lower()
            mdir, title = match_dir(iter((d1,d2,d3)), jobj) or badret
            if not mdir:
                log.warning("couldn't find title in JSON file. Trying " \
                            "online query.")
                raise breaks.Break
            gconf._cururl = 'https://' + loc['DOMAIN'] + loc['MLOC'] \
                + d1 + '/' + d2 + '/' + d3 + '/' + title
            dirls = '\n'.join([f['name'] for f in mdir]) + '\n'
            log.info('\n-----\n'+dirls+'-----')
            return (dirls, title)
    qout = search_query(manga).getvalue().decode()
    qp = ParseQuery()
    qp.feed(qout)
    # FIXME:
    # this is a temporary workaround to
    # filter out non-manga results until
    # madokami allows for this granularity itself.
    qp.mresultnum = 0
    qp.mresults = []
    for url, r in qp.results:
        if r.startswith('/Manga') and r.count('/') >= 5:
            qp.mresults.append([url,r])
            qp.mresultnum += 1
    if qp.mresultnum == 0:
        die('manga not found')
    if qp.mresultnum > 1:
        print('Multiple matches found. Please choose from the '\
              'selection below:\n')
        i = 1
        for url, f in qp.mresults:
            print(str(i)+':', os.path.basename(f))
            i += 1
        print()
        while 1:
            try:
                ch = int(input('choice > '))
                if ch in range(1, i): break
                print('Pick a number between 1 and %d' % (i-1))
            except ValueError:
                print('Invalid input.')
        m = qp.mresults[ch-1][0]
        title = os.path.basename(qp.mresults[ch-1][1])
    else:
        m = qp.mresults[0][0]
        title = os.path.basename(qp.mresults[0][1])
        _('one match found: %s' % title)
    dirls = search_exact(m, True).getvalue().decode()

    log.info('\n-----\n'+dirls+'-----')
    return (dirls, title)

def main_loop(manga_list):
    global compc, compv
    for m in manga_list:
            req = ParseRequest(m)
            sout, title = get_listing(req._name)
            compv, compc, allf, compfile = \
            walk_thru_listing(req, title, sout)
            if req._vols and req._vols[-1] == req.ALL: del req._vols[-1]
            if req._chps and req._chps[-1] == req.ALL: del req._chps[-1]
            missv = str([v for v in req._vols if v not in compv]).strip('[]')
            missc = str([c for c in req._chps if c not in compc]).strip('[]')
            if missv:
                _("couldn't find vol(s): " + missv)
            if missc:
                _("couldn't find chp(s): " + missc)
            if any((compfile, compc, compv)):
                try:
                    stdscr = unicurses.initscr()
                    gconf._stdscr = stdscr
                    unicurses.noecho()
                    if compfile:
                        _('downloading complete archive... ', end='')
                        gconf._stdscr.erase()
                        gconf._stdscr.addstr(0, 0, compfile)
                        gconf._stdscr.refresh()
                        curl_to_file(compfile)
                    elif compv or compc:
                        _('downloading volume/chapters... ', end='')
                        for f,v,c in allf:
                            #log.info('DL ' + f)
                            gconf._stdscr.erase()
                            gconf._stdscr.addstr(0, 0, 'title - %s' % title)
                            gconf._stdscr.addstr(1, 0, 'current - %s' % f)
                            gconf._stdscr.refresh()
                            curl_to_file(f)
                except:
                    raise
                finally:
                    unicurses.nocbreak()
                    gconf._stdscr.keypad(False)
                    unicurses.echo()
                    unicurses.endwin()
                print('done', file=sys.stderr)
            else:
                _('could not find requested volume/chapters.')
                return 1

    return 0

#
# TODO:
# - handle the case where a complete archive has no prefixes (and is probably
#   the only file in the directory)
# - handle sub-directories in file listing
# - extension filters
# - allow greedy v/c matching
#
def main():
    try:
        args = init_args()
        init_config()
        if args.outdir:
            gconf._outdir = args.outdir
        else:
            gconf._outdir = gconf._default_outdir
        if args.auth:
            up = args.auth.split(':', 1)
            if len(up) == 1 or '' in up:
                die('argument -a: bad auth format')
            gconf._user, gconf._pass = up
        if args.silent or gconf._no_output:
            # go ahead and set this so it is globally known.
            # there is no need for distinction at this point.
            gconf._no_output = True
            log.addFilter(nullfilter)
        ret = main_loop(args.manga)
    except (KeyboardInterrupt, EOFError):
        print()
        _('caught user signal, exiting...')
        return 0

    return ret

if __name__ == '__main__':
    sys.exit(main())
