#!/usr/bin/env python3

#
# various parsers
#

import re
import logging
from html.parser import HTMLParser

import madodl.out as _out
import madodl.gvars as _g
from madodl.exceptions import *

class ParseCommon:
    ''' ADDME '''

    ALL = float(1 << 32)

    def __init__(self):
        self._idx=0
        self._alltoks = []
        self._all = False
        self._vols = []
        self._chps = []

    def push_to_last(self, uval=-1):
        val = self.cur_tok_val() if uval < 0 else uval
        if self.last:
            _g.log.debug(self.last)
            self._vols.append(val)
        else:
            _g.log.debug(self.last)
            self._chps.append(val)

        return None

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

    def regex_mismatch(self, goodtyp, badtyp, uidx=-1):
        _g.log.warning('regex falsely picked up {} token as {}. '
                       'Replacing type.'.format(goodtyp, badtyp))
        _idx_ = self._idx if uidx < 0 else uidx
        self._alltoks[_idx_]['typ'] = goodtyp
        # put back original token value so integers in non volume/chapter
        # tokens don't stay in float format.
        if badtyp == 'NUM':
            self._alltoks[_idx_]['val'] = self._alltoks[_idx_]['raw']

        return None

    def eat_delim(self, norng=False):
        self._idx += 1
        typset = {'DLM',} if norng else {'DLM', 'RNG'}
        while self._idx < len(self._alltoks):
            if self._alltoks[self._idx]['typ'] in typset:
                if not norng and self._alltoks[self._idx]['typ'] == 'RNG':
                    self.regex_mismatch('DLM', 'RNG')
                    self._idx += 1
            else:
                break
            self._idx += 1

        return None

class ParseFile(ParseCommon):
    '''An inflexible title parser.

       This class parses a file with the expectation
       that there will be a volume/chapter number somewhere
       in the filename.
    '''
    def __init__(self, f, title):
        if not f:
            _out.die('File parameter is empty!')
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
            _out.die('Encountered a file without an extension, which is '
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
            _g.log.debug('{} {}'.format(self._idx, t))
            if t == 'VOL':
                self.last = True
                if not self.seenvol:
                    self.seenvol = True
                vidx = self._idx
                self.eat_delim()
                if self.cur_tok_typ() != 'NUM':
                    self.regex_mismatch('DAT', 'VOL', vidx)
                    self._idx += 1
                    continue
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
                    self._idx += 1
                    continue
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
                        self._idx += 1
                        continue
                    wildnums.append(self._alltoks[nidx])
                elif self.cur_tok_typ() == 'RNG':
                    self.eat_delim()
                    if self.cur_tok_typ() != 'NUM':
                        self.regex_mismatch('DAT', 'NUM', nidx)
                        self.regex_mismatch('DAT', 'RNG')
                        self._idx += 1
                        continue
                    st = self.get_tok_val(nidx)
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
            elif t in {'PLT', 'PRE', 'PRL', 'ART'}:
                # shouldn't have vol/chp
                if self._vols or self._chps:
                    self.regex_mismatch('DAT', t)
                    self._idx += 1
                    continue
                self.other = t
            elif t == 'OMK':
                # probably should have vol/chp
                if not self._vols and not self._chps:
                    _g.log.warning('regex picked up a bonus type without '
                                'a vol/chp identifier, which may be '
                                'incorrect. Adding anyway...')
                self.other = t
            elif t == 'ALL':
                self._all = True
            elif t == 'GRB':
                if self.get_tok_typ(self._idx+1) not in {'VOL', 'CHP', 'ALL',
                                              'OMK', 'PLT', 'PRE',
                                              'PRL', 'ART'}:
                    self._idx += 1
                    if (self.cur_tok_typ() == 'NUM' and
                        self.get_tok_typ(self._idx+1) != 'DAT'):
                        continue
                    tmptag = ''
                    while self.cur_tok_typ() not in {'GRE', None}:
                        if self.cur_tok_typ() == 'NUM':
                            self.regex_mismatch('DAT', 'NUM')
                        tmptag += str(self.cur_tok_val())
                        self._idx += 1
                    if self.cur_tok_val() == None:
                        _out.die('BUG: tag matching couldn`t find GRE')
                    if tmptag[:len(title)].lower().strip() == title.lower():
                        if (self.get_tok_typ(self._idx-1) in
                            {'PLT', 'PRE', 'PRO', 'PRL', 'ART', 'OMK'}):
                            continue # non-group tag with title in text
                    self._tag.append(tmptag)
            elif t == 'DAT':
                ''.join([self._title, self.cur_tok_val()])
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
                if -1 < dot < 2:
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
            if req:
                del req[0]
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
                    raise RequestError('bad char {}'.format(val))
                self._alltoks.append({'typ' : typ, 'val' : val})
            what = self.get_tok_typ(0)
            if what not in {'VOL', 'CHP'}:
                if what != 'NUM':
                    raise RequestError('bad vol/ch format')
                else:
                    _g.log.warning('No vol/ch prefix. Assuming volume.')
                    what = 'VOL'
                    tmp = [0 for z in range(len(self._alltoks)+1)]
                    for idx in range(len(self._alltoks)):
                        tmp[idx+1] = self._alltoks[idx]
                    self._alltoks = tmp
            elif len(self._alltoks) == 1 or self.get_tok_typ(1) != 'NUM':
                raise RequestError('no number specified for {}'.format(what))
            self.last = True if what == 'VOL' else False
            tokcpy = self._alltoks[:]
            self._idx = idx = 1
            while idx < len(self._alltoks)+1:
                typ = self.cur_tok_typ()
                val = self.cur_tok_val()
                _g.log.debug('{} {}'.format(typ, val))
                if typ is None:
                    break
                if typ == 'RNG':
                    if self._idx == len(self._alltoks)-1:
                        if self.get_tok_typ(self._idx-1) != 'NUM':
                            raise RequestError('bad range for {}'.format(what))
                        else:
                            self.push_to_last(self.ALL)
                            break
                    if ((self.get_tok_typ(self._idx-1) != 'NUM' and
                         self.get_tok_typ(self._idx+1) != 'NUM') or
                         self.get_tok_typ(self._idx+1) == 'COM'):
                        raise RequestError('bad range for {}'.format(what))
                    st = int(float(self.get_tok_val(self._idx-1)))
                    end = float(self.get_tok_val(self._idx+1))
                    if st > end:
                        end += st
                    st += 1
                    for n in range(st, int(end)+1):
                        self.push_to_last(float(n))
                    if end % 1:
                        self.push_to_last(end)
                    self._idx += 1
                elif typ == 'COM':
                    if (self._idx == len(self._alltoks)-1 or
                        self._alltoks[self._idx+1]['typ'] != 'NUM'):
                        _g.log.warning('Extraneous comma detected. Removing.')
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
        else:
            self.cont_td = False
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
