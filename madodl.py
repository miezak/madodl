#!/usr/bin/env python3

import os, sys
import re
from io import BytesIO
from html.parser import HTMLParser
from time import sleep
import urllib.parse
import argparse
import logging

try:
    import pycurl
except ImportError:
    sys.stderr.write('Need pycurl to use madodl!\n')
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

def die(lvl, msg):
    if lvl:
      getattr(log, lvl.lower())(msg)
    sys.exit(1)

hdrs = {}
def curl_hdr(hdr_line):
    hdr_line = hdr_line.decode('iso-8859-1')
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
            die('error', "couldn't open file for writing")
    else:
        c = curl_common_init(fname)
    #c.setopt(c.ACCEPT_ENCODING, 'gzip')
    c.setopt(c.USE_SSL, True)
    c.setopt(c.SSL_VERIFYPEER, False)
    c.setopt(c.URL, 'https://'+loc['DOMAIN']+loc['API']+'dumbtree')
    log.info('curling JSON tree...')
    c.perform()
    c.close()

def curl_url(url):
    buf = BytesIO()
    c = curl_common_init(buf)
    c.setopt(c.URL, url)
    c.perform()
    c.close()
    enc = None
    if 'content-type' in hdrs:
        content_type = hdrs['content-type'].lower()
        match = re.search('charset=(\S+)', content_type)
        if match:
            enc = match.group(1)
    if enc is None:
        enc = 'iso-8859-1'
        log.info('assuming encoding is %s' % enc)

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

    def __repr__(self):
        pass

class ParseFile(ParseCommon):
    '''An inflexible title parser.

       This class parses a file with the expectation
       that there will be a volume/chapter number somewhere
       in the filename.
    '''
    def __init__(self, f):
        if not f:
            die('File parameter is empty!')
        ParseCommon.__init__(self)
        self._f = f
        # Token abbreviations:
        # EXT -> Extension
        # GRB -> Group Beginning
        # GRE -> Group End
        # RNG -> Range
        # DLM -> Delimiter
        # VOL -> Volume
        # CHP -> Chapter
        # ART -> Artbook
        # PLT -> Pilot
        # PRL -> Prolog
        # PRE -> Prelude
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
            die('FATAL', 'Encountered a file without an extension, which is '\
                         'not currently supported. Bailing.')
        for t in self._alltoks:
            if t['typ'] == 'NUM':
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
            #print(str(self._idx)+' '+t)
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
                    wildnums.append(self._alltoks[nidx]['val'])
                elif self.cur_tok_typ() == 'RNG':
                    self.eat_delim()
                    if self.cur_tok_typ() != 'NUM':
                        self.regex_mismatch('DAT', 'NUM', nidx)
                        self.regex_mismatch('DAT', 'RNG')
                        self._idx += 1 ; continue
                    wildnums.append(self._alltoks[nidx]['val'])
                    rngb = int(self._alltoks[nidx]['val']) + 1
                    for n in range(rngb, int(self.cur_tok_val())+1):
                        wildnums.append(float(n))
                elif self.cur_tok_typ() == 'DAT':
                    self.regex_mismatch('DAT', 'NUM')
                else:
                    wildnums.append(self._alltoks[nidx]['val'])
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

            self._idx += 1

        if wildnums:
            if not self._vols and not self._chps:
                # assuming vol
                for n in sorted(wildnums):
                    self._vols.append(n)
            elif not self._vols:
                # assuming vol
                for n in sorted(wildnums):
                    self._vols.append(n)
            elif not self._chps:
                # assuming chp
                for n in sorted(wildnums):
                    self._chps.append(n)

        self._vols = sorted(set(self._vols))
        self._chps = sorted(set(self._chps))

    def __repr__(self):
        print('%s\n\t%s %s' % (self._f, self._vols, self._chps))

class ParseRequest(ParseCommon):
    ''' ADDME '''

    def __init__(self, req):
        ParseCommon.__init__(self)
        self.name = req[0]
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
                            self.set_cur_tok_val(tmpm)
                            minidx = idx
                            prev.append(tmpv)
                    else:
                        prev.append(val)
                        minidx = idx
            tokcpy = self._alltoks[:]
            for self._idx in range(1, len(self._alltoks)):
                typ = self.cur_tok_typ()
                val = self.cur_tok_val()
                log.debug(str(typ)+' '+str(val))
                if typ == 'RNG':
                    if self._idx == len(self._alltoks)-1:
                        if self.get_tok_typ(self._idx-1) != 'NUM':
                            raise RuntimeError('bad range for %s' % what)
                        else: break
                    if ((self.get_tok_typ(self._idx-1) != 'NUM' and \
                         self.get_tok_typ(self._idx+1) != 'NUM') or \
                         self.get_tok_typ(self._idx+1) == 'COM'):
                        raise RuntimeError('bad range for %s' % what)
                    if self.get_tok_typ(self._idx+1) != 'NUM':
                        self.push_to_last(float(val))
                        self.push_to_last(self.ALL)
                    else:
                        st = float(self.get_tok_val(self._idx-1))
                        self.push_to_last(st)
                        st = int(st) + 1
                        end = float(self.get_tok_val(self._idx+1))
                        for n in range(st, int(end)+1):
                            self.push_to_last(float(n))
                        if end % 1:
                            self.push_to_last(end)
                elif typ == 'COM':
                    if self._idx == len(self._alltoks)-1 or \
                       self._alltoks[self._idx+1]['typ'] != 'NUM':
                        log.warning('Extraneous comma detected. Removing.')
                        diff = len(self._alltoks) - len(tokcpy)
                    else:
                        self._idx += 1
                        self.push_to_last(float(self.cur_tok_val()))
                elif typ == 'NUM':
                    self.push_to_last(float(self.cur_tok_val()))

            self._vols = sorted(set(self._vols))
            self._chps = sorted(set(self._chps))

    def __repr__(self):
        print(self._vols, self._chps)

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

    def __repr__(self):
        pass #print(self.resultnum, self.results)

def create_nwo_path(name):
    '''Create the exact path that the manga `name` should be in.

       This path is constructed in the `New World Order` format
       described here: manga.madokami.com/Info/NewWorldOrder.txt

       Parameters:
       name - the name of the manga to convert to NWO format.
    '''
    if not name:
        die('error', 'need a name with at least one character!')
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
    c.setopt(c.URL, 'ftp://'+loc['DOMAIN']+ml+path+'/'+name+'/')
    c.perform()
    c.close()
    return buf

def search_query(name=''):
    return curl_url('https://'+loc['DOMAIN']+loc['SEARCH']+name)

def rm_req_elems(req, comp):
    for n in comp:
        if n in req:
            req.remove(n)

def _(msg):
    if not silent:
        print('%s: %s' % (os.path.basename(__file__), msg))

VERSION = '0.1.0'
#
# TODO:
# - Check if a naming scheme is using _only_ chapters without a ch prefix,
#   and thus, should default to chapters instead of vols. Probable solution
#   would be to check for two or more leading zeros (there probably aren't
#   100 volumes)
#
def main():

    args_parser = \
    argparse.ArgumentParser(description='Download manga from madokami.',\
                            usage='%(prog)s [-dhsv] [-p ident val ...] '\
                                            '-m manga '                 \
                                            '[volume(s)] [chapter(s)] ...')
    args_parser.add_argument('-d', action='store_true', dest='debug', \
                             help='print debugging messages')
    args_parser.add_argument('-s', action='store_true', dest='silent', \
                             help='silence message output')
    args_parser.add_argument('-v', action='store_true', dest='verbose', \
                             help='print verbose messages')
    args_parser.add_argument('-V', '--version', action='version',
                             version='madodl ' + VERSION)
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
    args = args_parser.parse_args()
    if args.silent:
        loglvl = logging.CRITICAL
    elif args.debug:
        loglvl = logging.DEBUG
    elif args.verbose:
        loglvl = logging.INFO
    else:
        loglvl = logging.ERROR
    global log, silent, compv, compc
    silent = args.silent
    log = logging.getLogger('stream_logger')
    log.setLevel(loglvl)
    cons_hdlr = logging.StreamHandler()
    cons_hdlr.setLevel(loglvl)
    logfmt = logging.Formatter('%(filename)s: %(funcName)s(): ' \
                               '%(levelname)s: %(message)s')
    cons_hdlr.setFormatter(logfmt)
    log.addHandler(cons_hdlr)

    for m in args.manga:
        name = m[0]
        req = ParseRequest(m)
        #jsonfh = curl_json_list('f.json', True)
        sout = search_query(name).getvalue().decode()
        qp = ParseQuery()
        qp.feed(sout)
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
            die('error', 'manga not found')
        if qp.mresultnum > 1:
            print('Multiple matches found. Please choose from the selection '\
                  'below:\n')
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
        else:
            m = qp.mresults[0][0]
            _('one match found: %s' % os.path.basename(qp.mresults[0][1]))
        sout = search_exact(m, True).getvalue().decode()
        log.info('\n-----\n'+sout+'-----')
        compv = []
        compc = []
        allf = []
        compfile = None
        reqv_cpy = req._vols[:]
        reqc_cpy = req._chps[:]
        for f in sout.splitlines():
            fo = ParseFile(f)
            vq = [] ; cq = []
            apnd = False
            if req._all:
                if fo._all:
                    log.info('found complete archive')
                    log.info('file - %s' % f)
                    compfile = f
                    break
                continue
            for fov in fo._vols:
                if fov in req._vols:
                    if fov in compv: # already seen this vol
                        for foc in fo._chps: # then check if vol is split
                            if foc not in compc: # with all new chps
                                continue # is new
                            else:
                                log.warning('dup vol and chps seen')
                                break
                        else: # all new
                            apnd = True
                            vq.append(fov)
                    else:
                        apnd = True
                        vq.append(fov)
            if apnd:
                for foc in fo._chps:
                    cq.append(foc)
            for reqc in req._chps:
                if reqc in fo._chps and reqc not in cq:
                    if len(fo._chps) == 1: # only a single chp
                        cq.append(reqc)
            if vq:
                log.info('found vol %s ' % str(vq))
            if cq:
                log.info('found chp %s ' % str(cq))
            if vq or cq:
                allf.append((f, vq, cq))
                log.info('file - %s' % f)
            for v in vq: compv.append(v)
            for c in cq: compc.append(c)
            rm_req_elems(reqv_cpy, vq)
            rm_req_elems(reqc_cpy, cq)
            compv = list(set(compv))
            compc = list(set(compc))
        compv = sorted(compv)
        compc = sorted(compc)
        if compfile:
            _('downloading complete archive...')
        elif compv or compc:
            _('downloading volume/chapters...')
            for f,v,c in allf:
                sys.stdout.write('\rcurrent - %s' % f)
                # curl file ...
            print()
        else:
            _('could not find requested volume/chapters.')

if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt:
        print()
        _('caught signal, exiting...')
else:
    sys.stderr.write('madodl.py does not have a public API, and is not ' \
                     'meant to be called as a module. Use at your own risk.\n')