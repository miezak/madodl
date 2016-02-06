#!/usr/bin/env python3

import os, sys
import re
from io import BytesIO
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
            raise OSError
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

    #body = buf.getvalue()
    #print(body.decode(enc))

class ParseFile():
    '''An inflexible title parser.

       This class parses a file with the expectation
       that there will be a volume/chapter number somewhere
       in the filename.
    '''
    def __init__(self, f):
        if not f:
            die('File parameter is empty!')
        self.f = f
        self.vols = []
        self.chps = []
        self.alltoks = []
        self.idx = 0
        # func pointers for less typing
        cur_tok_typ    = self.cur_tok_typ
        cur_tok_val    = self.cur_tok_val
        regex_mismatch = self.regex_mismatch
        eat_delim      = self.eat_delim
        push_to_last   = self.push_to_last
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
            ('ART', r'artbook')             ,
            ('PLT', r'pilot')               ,
            ('PRL', r'prologu?e')           ,
            ('PRE', r'prelude')             ,
            ('OMK', r'''(?x)
                        \+?(?=(-|_|\.|\s+)*)
                        (omake|extra|bonus)
                     ''') ,
            ('NUM', r'\d+(\.\d+)?')         ,
            ('COM', r',')                   ,
            ('DAT', r'.')                   ,
        ]
        tok_regex = '|'.join('(?P<%s>%s)' % p for p in tok_spec)

        for t in re.finditer(tok_regex, f, flags=re.I):
            typ = t.lastgroup
            val = t.group(typ)
            self.alltoks.append({'typ' : typ, 'val' : val})

        if self.alltoks[len(self.alltoks)-1]['typ'] != 'EXT':
            die('FATAL', 'Encountered a file without an extension, which is '\
                         'not currently supported. Bailing.')
        for t in self.alltoks:
            if t['typ'] == 'NUM':
                t['val'] = float(t['val'])

        # variable stores whether vol or chp
        # was seen last. True = vol, False = chp
        self.last = None
        self.seenchp = False
        self.seenvol = False
        self.other = None
        wildnums = []
        while self.idx < len(self.alltoks):
            t = cur_tok_typ()
            #print(str(self.idx)+' '+t)
            if t == 'VOL':
                self.last = True
                if not self.seenvol:
                    self.seenvol = True
                vidx = self.idx
                eat_delim()
                if cur_tok_typ() != 'NUM':
                    regex_mismatch('DAT', 'VOL', vidx)
                    self.idx += 1 ; continue
                vval = cur_tok_val()
                self.vols.append(vval)
                # we need this line in case of a range
                # with a fractional e.g. vol1.5-3 in which
                # case we assume the successive volumes are
                # whole volumes.
                vval = int(vval) + 1
                eat_delim(True)
                if cur_tok_typ() == 'RNG':
                    eat_delim()
                    if self.idx == len(self.alltoks):
                        # open-ended range
                        self.vols.append(str(vidx)+'-all')
                        continue
                    elif cur_tok_typ() == 'NUM':
                        for n in range(vval, int(cur_tok_val()+1)):
                            self.vols.append(float(n))
                        if cur_tok_val() % 1:
                            self.vols.append(cur_tok_val())
                        self.idx += 1
                continue # XXX
            elif t == 'CHP':
                self.last = False
                if not self.seenchp:
                    self.seenchp = True
                cidx = self.idx
                eat_delim()
                if cur_tok_typ() != 'NUM':
                    regex_mismatch('DAT', 'VOL', vidx)
                    self.idx += 1 ; continue
                cval = cur_tok_val()
                self.chps.append(cval)
                # we need this line in case of a range
                # with a fractional e.g. vol1.5-3 in which
                # case we assume the successive volumes are
                # whole volumes.
                cval = int(cval) + 1
                eat_delim(True)
                if cur_tok_typ() == 'RNG':
                    eat_delim()
                    if self.idx == len(self.alltoks):
                        # open-ended range
                        self.vols.append(str(vidx)+'-all')
                        continue
                    elif cur_tok_typ() == 'NUM':
                        for n in range(cval, int(cur_tok_val()+1)):
                            self.chps.append(float(n))
                        if cur_tok_val() % 1:
                            self.chps.append(cur_tok_val())
                        self.idx += 1
                continue # XXX
            elif t == 'COM':
                if self.last is None:
                    regex_mismatch('DAT', 'COM')
                    continue
                comidx = self.idx
                eat_delim()
                if cur_tok_typ() != 'NUM':
                    regex_mismatch('DAT', 'COM', comidx)
                comval = cur_tok_val()
                push_to_last(comval)
                eat_delim(True)
                if cur_tok_typ() == 'RNG':
                    comval = int(comval) + 1
                    eat_delim()
                    if cur_tok_typ() == 'NUM':
                        for n in range(comval, int(cur_tok_val())+1):
                            push_to_last(float(n))
            elif t == 'RNG':
                regex_mismatch('DLM', 'RNG')
            elif t == 'NUM':
                # spotted a number without a vol/chp prefix
                nidx = self.idx
                eat_delim(True)
                if cur_tok_typ() == 'COM':
                    eat_delim()
                    if cur_tok_typ() != 'NUM':
                        regex_mismatch('DAT', 'NUM', nidx)
                        regex_mismatch('DAT', 'COM')
                        self.idx += 1 ; continue
                    wildnums.append(self.alltoks[nidx]['val'])
                elif cur_tok_typ() == 'RNG':
                    eat_delim()
                    if cur_tok_typ() != 'NUM':
                        regex_mismatch('DAT', 'NUM', nidx)
                        regex_mismatch('DAT', 'RNG')
                        self.idx += 1 ; continue
                    wildnums.append(self.alltoks[nidx]['val'])
                    rngb = int(self.alltoks[nidx]['val']) + 1
                    for n in range(rngb, int(cur_tok_val())+1):
                        wildnums.append(float(n))
                elif cur_tok_typ() == 'DAT':
                    regex_mismatch('DAT', 'NUM')
                else:
                    wildnums.append(self.alltoks[nidx]['val'])
            elif t in ('PLT', 'PRL', 'ART'):
                # shouldn't have vol/chp
                if self.vols or self.chps:
                    regex_mismatch('DAT', 't')
                    self.idx += 1 ; continue
                self.other = t
            elif t == 'OMK':
                # probably should have vol/chp
                if not self.vols and not self.chps:
                    log.warning('regex picked up a bonus type without '\
                                'a vol/chp identifier, which may be '  \
                                'incorrect. Adding anyway...')
                self.other = t

            self.idx += 1

        if wildnums:
            if not self.vols and not self.chps:
                # assuming vol
                for n in sorted(wildnums):
                    self.vols.append(n)
            elif not self.vols:
                # assuming vol
                for n in sorted(wildnums):
                    self.vols.append(n)
            elif not self.chps:
                # assuming chp
                for n in sorted(wildnums):
                    self.chps.append(n)
        #print(self.alltoks)

    def push_to_last(self, uval=False):
        val = uval if uval is not False else cur_tok_val()
        if self.last:
            log.debug(self.last)
            self.vols.append(val)
        else:
            log.debug(self.last)
            self.chps.append(val)

    def cur_tok_typ(self):
        if self.idx == len(self.alltoks):
            return None
        return self.alltoks[self.idx]['typ']

    def cur_tok_val(self):
        if self.idx == len(self.alltoks):
            return None
        return self.alltoks[self.idx]['val']

    def regex_mismatch(self, goodt, badt, uidx=False):
        log.warning('regex falsely picked up %s token as %s. ' \
                    'Replacing type.' % (goodt, badt))
        if uidx is not False:
            self.alltoks[uidx]['typ'] = goodt
        else:
            self.alltoks[self.idx]['typ'] = goodt

    def eat_delim(self, norng=False):
        self.idx += 1
        typtuple = ('DLM',) if norng else ('DLM', 'RNG')
        while self.idx < len(self.alltoks):
            if self.alltoks[self.idx]['typ'] in typtuple:
                if not norng and self.alltoks[self.idx]['typ'] == 'RNG':
                    self.regex_mismatch('DLM', 'RNG')
                    self.idx += 1
            else: break
            self.idx += 1

    def __repr__(self):
        return print('%s\n\t%s %s' % (self.f, self.vols, self.chps))

def parse_req(v_or_c='all'):
    global all_seen
    v_or_c = re.sub(r'\s', '', v_or_c)
    v_or_c = v_or_c.lower()
    if v_or_c == 'all':
        if all_seen:
            log.warning('Already requested all files. Ignoring second param.')
            return True
        all_seen = True
        return False
    tok_spec =  [
        ('VOL', r'v(ol)?')      ,
        ('CHP', r'ch?')         ,
        ('NUM', r'\d+(\.\d+)?') ,
        ('RNG', r'-')           ,
        ('COM', r',')           ,
        ('BAD', r'.')           ,
    ]
    tok_regex = '|'.join('(?P<%s>%s)' % p for p in tok_spec)
    self.alltoks = []
    for t in re.finditer(tok_regex, v_or_c):
        typ = t.lastgroup
        val = t.group(typ)
        if typ == 'BAD':
            raise RuntimeError('bad char %s' % val)
        self.alltoks.append({'typ' : typ, 'val' : val})
    if self.alltoks[0]['typ'] not in ('VOL', 'CHP'):
        if self.alltoks[0]['typ'] != 'NUM':
            raise RuntimeError('bad vol/ch format')
        else:
            log.warning('No vol/ch prefix. Assuming volume.')
    elif len(self.alltoks) == 1 or \
        self.alltoks[1]['typ'] != 'NUM':
        raise RuntimeError('no number specified for %s' % self.alltoks[0]['val'])
    prev = []
    for self.idx in range(1, len(self.alltoks)):
        if self.alltoks[self.idx]['typ'] == 'NUM':
            if prev:
                tmpv = self.alltoks[self.idx]['val'][:]
                tmpm = min(prev)
                if tmpv < tmpm:
                    self.alltoks[minidx]['val'] = tmpv
                    self.alltoks[self.idx]['val'] = tmpm
                    minidx = idx
                prev.append(tmpv)
            else:
                prev.append(self.alltoks[idx]['val'])
                minidx = idx
    tokcpy = self.alltoks[:]
    for idx in range(1, len(self.alltoks)):
        if self.alltoks[idx]['typ'] == 'RNG':
            if idx == len(self.alltoks)-1:
                if self.alltoks[idx-1]['typ'] != 'NUM':
                    raise RuntimeError('bad range for %s' \
                                        % self.alltoks[0]['val'])
                else: break
            if ((self.alltoks[idx-1]['typ'] != 'NUM' and \
                 self.alltoks[idx+1]['typ'] != 'NUM') or \
               (self.alltoks[idx+1]['typ'] == 'COM')):
                raise RuntimeError('bad range for %s' % self.alltoks[0]['val'])
        elif self.alltoks[idx]['typ'] == 'COM':
            if idx == len(self.alltoks)-1 or self.alltoks[idx+1]['typ'] != 'NUM':
                log.warning('Extraneous comma detected. Removing.')
                diff = len(self.alltoks) - len(tokcpy)
                del tokcpy[idx - diff]

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

def search_exact(name=''):
    buf = BytesIO()
    path = create_nwo_path(name)
    c = curl_common_init(buf)
    c.setopt(c.DIRLISTONLY, True)
    c.setopt(c.USE_SSL, True)
    c.setopt(c.SSL_VERIFYPEER, False)
    c.setopt(c.USERPWD, loc['USER']+':'+loc['PASS'])
    c.setopt(c.PORT, loc['FTPPORT'])
    c.setopt(c.URL, 'ftp://'+loc['DOMAIN']+loc['MLOC']+path+'/'+name+'/')
    c.perform()
    c.close()
    return buf

VERSION = '0.1.0'
def main():
    args_parser = \
    argparse.ArgumentParser(description='Download manga from madokami.',\
                            usage='%(prog)s [-dhsv] [-p ident val ...] '\
                                            '<-m manga '                \
                                            '[volume(s)] [chapter(s)]>')
    args_parser.add_argument('-d', action='store_true', dest='debug', \
                             help='print debugging messages')
    args_parser.add_argument('-s', action='store_true', dest='silent', \
                             help='silent message output')
    args_parser.add_argument('-v', action='store_true', dest='verbose', \
                             help='print verbose messages')
    args_parser.add_argument('-V', '--version', action='version',
                             version='madodl ' + VERSION[0])
    args_parser.add_argument('-m', nargs='*', action='append', dest='manga', \
                             help='''the name of the manga to download.
                                  if no arguments are supplied, all manga under
                                  this name are downloaded. otherwise, -m takes
                                  a list of volumes and/or a list of chapters
                                  to download.
                                  the format for these lists are as follows:\n
                                  v(list) or vol(list)\nwhere list is one of:\n
                                  1-\n
                                  1-(...), num, ...''')
    args = args_parser.parse_args()
    if args.silent:
        loglvl = logging.CRITICAL
    elif args.debug:
        loglvl = logging.DEBUG
    elif args.verbose:
        loglvl = logging.INFO
    else:
        loglvl = logging.WARNING
    global log, all_seen, compdl
    log = logging.getLogger('stream_logger')
    log.setLevel(loglvl)
    cons_hdlr = logging.StreamHandler()
    cons_hdlr.setLevel(loglvl)
    logfmt = logging.Formatter('%(filename)s: %(funcName)s(): ' \
                               '%(levelname)s: %(message)s')
    cons_hdlr.setFormatter(logfmt)
    log.addHandler(cons_hdlr)

    if args.manga is not None:
        if [] in args.manga:
            die('error', '`-m` flag requires at least one argument')
    else:
        die('error', '`-m` must be invoked')
    for req in args.manga:
        all_seen=False
        if len(req) == 1:
            parse_req('all')
        elif len(req) == 2:
            parse_req(req[1])
        else:
            parse_req(req[1])
            parse_req(req[2])
    #jsonfh = curl_json_list('f.json', True)
    #sout = search_exact(args.manga[0][0])
    #for f in sout.getvalue().decode().splitlines():
    #    ParseFile(f).__repr__()
    a=ParseFile(args.manga[0][0])
    a.__repr__()
    if a.other:
        print(a.other)

if __name__ == '__main__':
    main()
else:
    sys.stderr.write('madodl.py does not have a public API, and is not ' \
                     'meant to be called as a module. Use at your own risk.\n')
