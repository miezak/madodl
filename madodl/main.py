#!/usr/bin/env python3

#
# madodl entry point
#
# For now, this file will contain the initialization of argument handling and
# config file stuff, as well as the search and processing logic.
#

import os, sys
from io        import BytesIO
from itertools import chain
import urllib.parse
import argparse
import logging
import logging.handlers
import pkg_resources
import json

def local_import():
    global _curl, _parsers, _util, _out

    import madodl.curl    as _curl
    import madodl.parsers as _parsers
    import madodl.util    as _util
    import madodl.out     as _out

import madodl.gvars as _g
from madodl.exceptions import *

if sys.hexversion < 0x30400f0:
    sys.stderr.write('madodl requires Python 3.4 or newer.\n')
    sys.exit(1)

def dep404(what):
    sys.stderr.write('Need ' + what + ' to use madodl!\n')
    sys.exit(1)

try:
    import unicurses
except ImportError:
    dep404('UniCurses')

try:
    import pycurl
except ImportError:
    dep404('pycURL')

try:
    import yaml
except ImportError:
    dep404('PyYAML')

loc = {
    'DOMAIN'   : 'manga.madokami.al' ,
    'API'      : '/stupidapi/'       ,
    'USER'     : 'homura'            ,
    'PASS'     : 'megane'            ,
    'FTPPORT'  : 24430               ,
    'SFTPPORT' : 38460               ,
    'MLOC'     : '/Manga/'           ,
    'SEARCH'   : '/search?q='        ,
}
_g.loc = loc

# emulate struct
class Struct:
    pass

#
# returns an FTP LISTing
#
def search_exact(name='', have_path=False):
    buf = BytesIO()

    # need to unquote for LIST to work properly with nocwd
    name = urllib.parse.unquote(name)
    path = _util.create_nwo_path(name) if not have_path else ''

    c = _curl.curl_common_init(buf)

    #c.setopt(c.DIRLISTONLY, True)
    c.setopt(c.USE_SSL, True)
    c.setopt(c.SSL_VERIFYPEER, False)
    c.setopt(c.USERPWD, '{}:{}'.format(loc['USER'], loc['PASS']))
    c.setopt(c.PORT, loc['FTPPORT'])

    ml = loc['MLOC'] if not have_path else ''

    path_noscheme = '{}{}{}/{}/'.format(loc['DOMAIN'], ml, path, name)

    _g.log.info('ftp://' + path_noscheme)

    return _curl.curl_to_buf('ftp://' + path_noscheme, 'FTP', c, buf)

def search_query(name=''):
    return _curl.curl_to_buf('https://{}{}{}'.format(loc['DOMAIN'],
                                                     loc['SEARCH'], name),
                             'HTTP')

#
# filter files according to tag rules.
#
# NOTE: if a tag is defined multiple times, the first definition is used.
#
# Returns True if we keep this file and False if we filter it out.
#
def apply_tag_filters(f, title):
    f._preftag  = False
    f._npreftag = False

    if not any((f._tag, _g.conf._alltags)):
        return True

    taglow   = [t.lower() for t in f._tag]
    titlelow = title.lower()

    for t in _g.conf._alltags:
        _g.log.info('apply_tag_filters(): {} {} {} {}'.format(t._name,
                                                              t._filter,
                                                              t._case, taglow))
        _g.log.info('apply_tag_filters(): {}'.format(t._name.lower() in taglow))

        if t._name.lower() in taglow:
            if ((t._case == 'exact' and t._name not in f._tag) or
                (t._case == 'upper' and t._name not in
                                        [t.upper() for t in f._tag])):
                return True

            curtag = t._name.lower()
            # we need to check the `for` sub-opt before actually checking
            # the filter to make sure we don't apply the filters to titles
            # not in the `for` listing.
            if t._for != 'all':
                for d in t._for:
                    for ft in d.keys():
                        if ft.lower() == titlelow:
                            mreq = d[titlelow]
                            break # first come, first serve
                    else:
                        continue
                    break # need this too
                else:
                    return True

                if mreq != 'all':
                    if not (_util.common_elem(f._vols, mreq._vols) or
                            _util.common_elem(f._chps, mreq._chps)):
                        return True

            if t._ext != 'any' and f._ext not in t._ext:
                # extension match required, but not found
                if t._filter == 'only':
                    return False
                return True

            if t._filter == 'out':
                del f
                return False
            if t._filter == 'prefer':
                f._preftag = True
            elif t._filter == 'not prefer':
                f._npreftag = True
        else:
            if t._filter == 'only':
                # check if in `for` specifications
                if t._for != 'all':
                    for d in t._for:
                        for ft in d.keys():
                            if ft.lower() == titlelow:
                                mreq = d[titlelow]
                                break # first come, first serve
                        else:
                            continue
                        break # need this too
                    else:
                        return True

                    if mreq != 'all':
                        if not (_util.common_elem(f._vols, mreq._vols) or
                                _util.common_elem(f._chps, mreq._chps)):
                            return True

                # we wanted only a specific tag, but couldn't find it
                del f
                return False

    return True

def check_pref_tags(vc, vcq, fo, allf, npref, v_or_c):
    # v_or_c: True -> vol, False -> chp
    if v_or_c:
        ftupidx = 1
        what    = 'vol'
        whatls  = fo._vols
    else:
        ftupidx = 2
        what    = 'chp'
        whatls  = fo._chps

    if fo._preftag:
            for ftup in allf:
                if vc in ftup[ftupidx]:
                    _g.log.info('replacing {} with preferred'
                             ' tag {}'.format(ftup[0], fo._f))
                    allf.remove(ftup)
                    vcq.extend(whatls)
                    return 'break'
            else:
                _out.die("BUG: couldn't find any dup {} in {} "
                    "when replacing with pref tag".format(what, whatls),
                    lvl='critical')
    elif not fo._npreftag and npref:
        for t in npref:
            if vc in t[ftupidx]:
                tup = t
                break
        else:
            _g.log.warning('dup vol and chps seen')
            return 'break'

        _g.log.info('replacing nonpreferred {} '
                 'with {}'.format(tup[0], fo._f))
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
    compv    = []
    compc    = []
    allf     = []
    npref    = []
    compfile = None

    if req._vols and req._vols[-1] == req.ALL:
        oerng_v = True
        oest_v  = req._vols[-2]
    else:
        oerng_v = False

    if req._chps and req._chps[-1] == req.ALL:
        oerng_c = True
        oest_c  = req._chps[-2]
    else:
        oerng_c = False

    reqv_cpy = req._vols[:]
    reqc_cpy = req._chps[:]

    only_file = len(dir_ls) == 1

    for f in dir_ls:
        fo = _parsers.ParseFile(f.name, title)

        if not apply_tag_filters(fo, title):
            _g.log.info('!** filtered out tag {} **!'.format(fo._f))
            continue

        vq   = []
        cq   = []
        apnd = False

        if only_file and not any((fo._vols, fo._chps, fo._all)):
            # a single file with no prefix of anykind is most likely a complete
            # entry.
            fo._all = True

        if fo._all and req._all:
            # XXX need pref filt handling here
            _g.log.info('found complete archive\n'
                        'file - {}'.format(f.name))
            compfile = f
            break
        elif req._all and not req._vols:
            for c in fo._chps:
                if c not in cq and c not in compc:
                    cq.append(c)
                else:
                    act = check_pref_tags(fov, vq, fo, allf, npref, True)
                    if isinstance(act, str):
                        if fo._preftag:
                            continue
                        if act == 'break': break
                        cq.append(c)
                        continue
                    cq = []
                    break

        # TODO: add vol greedy match here
        if req._vols and not any({oerng_v, req._all}):
            too_many_vols = False

            for v in fo._vols:
                if v not in req._vols:
                    too_many_vols = True
                    break

            if too_many_vols:
                continue

        for fov in fo._vols:
            if (oerng_v and fov >= oest_v) or req._all or fov in req._vols:
                if fov in compv: # already seen this vol
                    for foc in fo._chps: # then check if vol is split
                        if compc and foc not in compc: # with all new chps
                            continue # is new
                        else:
                            act = check_pref_tags(fov, vq, fo, allf, npref,
                                                  True)
                            if isinstance(act, str):
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
        if (len(req._chps) > 1 and len(fo._chps) == len(req._chps)
            and req._chps[0] == fo._chps[0]):
            rmax  = None
            fomax = None
            last  = req._chps[0]

            for i in range(1, len(req._chps)):
                if req._chps[i] == last+1:
                    rmax = req._chps[i]
                else:
                    break
                last = req._chps[i]

            last = fo._chps[0]

            for i in range(1, len(fo._chps)):
                if fo._chps[i] == last+1:
                    fomax = fo._chps[i]
                else:
                    break
                last = fo._chps[i]

            if None in {rmax, fomax} or rmax != fomax:
                pass
            else:
                iter_celems = _util.common_elem_gen(req._chps, (cq, compc),
                                                    flat=False)

                for cclash in iter_celems:
                    check_pref_tags(cclash, cq, fo, allf, npref, False)

                for i in req._chps:
                    if i <= rmax:
                        cq.append(float(i))
                    else:
                        break

        if req._chps:
            if oerng_c and fo._chps and min(fo._chps) >= oest_c:
                for c in fo._chps:
                    if c in set(chain(cq, compc)): # in queue, check preftags
                        act = check_pref_tags(c, cq, fo, allf, npref, False)
                        if act == 'break'   : break
                        if act == 'continue': continue
                        break
                else:
                    # XXX do we need to check min() again?
                    if fo._chps and min(fo._chps) >= oest_c:
                        cq.extend(fo._chps)
            else:
                # TODO: add chp greedy match here
                # NOTE: the list-comprehension is non-greedy check
                if req._all or not [c for c in fo._chps if c not in
                                         req._chps]:
                    for c in _util.common_elem_gen(fo._chps, req._chps):
                        if c not in set(chain(cq, compc)):
                            cq.append(c)
                        else: # in queue, check preftags
                            act = check_pref_tags(c, cq, fo, allf, npref, False)

                            if act == 'break'   : break
                            if act == 'continue':
                                # always npref, continue is simply explicit
                                cq.append(c)
                                continue

        if vq:
            _g.log.info('found vol {}'.format(vq))

        if cq:
            _g.log.info('found chp {}'.format(cq))

        if vq or cq:
            if fo._npreftag:
                npref.append((f, vq, cq))

            allf.append((f, vq, cq))

            _g.log.info('file - {}'.format(f.name))

        compv.extend(vq)
        compc.extend(cq)

        _util.rm_req_elems(reqv_cpy, vq)
        _util.rm_req_elems(reqc_cpy, cq)

        compv = list(set(compv))
        compc = list(set(compc))

    compv = sorted(compv)
    compc = sorted(compc)

    return (compv, compc, allf, compfile)

def init_args():

    def output_file(f):
        f = os.path.normpath(f)

        if not os.path.exists(f):
            try:
                os.makedirs(f)
            except PermissionError:
                raise argparse.ArgumentTypeError('Insufficient permissions to '
                    'create {} directory.'.format(f))
            except NotADirectoryError:
                raise argparse.ArgumentTypeError('Non-directory in path.')
        elif not os.path.isdir(f):
            raise argparse.ArgumentTypeError('{} is not a directory.'.format(f))
        elif not os.access(f, os.R_OK | os.W_OK | os.X_OK):
            raise argparse.ArgumentTypeError(
                'Insufficient permissions to write to {} directory.'.format(f))

        if f[-1] != os.sep:
            f += os.sep

        return f

    try:
         _version = pkg_resources.get_distribution('madodl').version
    except pkg_resources.DistributionNotFound:
        _version = '(local)'

    args_parser = argparse.ArgumentParser(
                            description='Download manga from madokami.',
                            usage='%(prog)s [-dhsv] '
                                            '-m manga '
                                            '[volume(s)] [chapter(s)] ... '
                                            '[-o out-dir]')
    args_parser.add_argument('-d', action='store_true', dest='debug',
                             help='print debugging messages')
    args_parser.add_argument('-s', action='store_true', dest='silent',
                             help='silence message output')
    args_parser.add_argument('-v', action='store_true', dest='verbose',
                             help='print verbose messages')
    args_parser.add_argument('-V', '--version', action='version',
                             version='madodl ' + _version)
    args_parser.add_argument('-m', nargs='+', action='append', dest='manga',
                             required=True,
                             metavar=('manga', 'volume(s) chapter(s)'),
                             help='''
                                  The name of the manga to download.
                                  If only the manga title is given, all manga
                                  under this name are downloaded. otherwise, -m
                                  takes a list of volumes and/or a list of
                                  chapters to download.
                                  ''')
    args_parser.add_argument('-o', type=output_file, dest='outdir',
                             metavar='outdir',
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

    global _g, silent

    silent = args.silent

    _g.log = logging.getLogger('stream_logger')

    _g.log.setLevel(loglvl)

    cons_hdlr = logging.StreamHandler()
    cons_hdlr.setLevel(loglvl)

    logfmt = logging.Formatter('madodl: %(filename)s: %(funcName)s(): '
                               '%(levelname)s: %(message)s')
    cons_hdlr.setFormatter(logfmt)

    _g.log.addHandler(cons_hdlr)

    return args

def nullfilter(r): return 0

def logfile_filter(record):
    if _g.conf._loglevel == 'all':
        return 1

    if ((record.levelname == 'DEBUG' and _g.conf._loglevel != 'debug') or
        (record.levelname == 'INFO'  and _g.conf._loglevel != 'verbose')):
        return 0

    return 1

def init_config():
    c          = None
    alltags    = []
    VALID_OPTS = {
        'tags'              ,
        'no_output'         ,
        'confirm_selection' ,
        'logfile'           ,
        'loglevel'          ,
        'usecache'          ,
        'cachefile'         ,
        'user'              ,
        'pass'              ,
    }
    # for valid option values
    # None = an option whose validity cannot be ascertained
    binopt = {True, False}

    VALID_OPTVAL_CONFIRM_SELECTION = binopt
    VALID_OPTVAL_NO_OUTPUT         = binopt
    VALID_OPTVAL_LOGFILE           = None
    VALID_OPTVAL_LOGLEVEL          = {
        'verbose' ,
        'debug'   ,
        'all'     ,
    }
    VALID_OPTVAL_USECACHE          = binopt
    VALID_OPTVAL_CACHEFILE         = None
    VALID_OPTVAL_DEFAULT_OUTDIR    = None
    VALID_OPTVAL_USER              = None
    VALID_OPTVAL_PASS              = None

    DEFAULT_OPTVAL_CONFIRM_SELECTION = False
    DEFAULT_OPTVAL_NO_OUTPUT         = False
    DEFAULT_OPTVAL_LOGFILE           = None
    DEFAULT_OPTVAL_LOGLEVEL          = 'verbose'
    DEFAULT_OPTVAL_USECACHE          = False
    # set after we get local $HOME
    DEFAULT_OPTVAL_CACHEFILE         = lambda h: os.path.join(h, '.cache',
                                                         'madodl', 'files.json')
    DEFAULT_OPTVAL_DEFAULT_OUTDIR    = os.getcwd()
    DEFAULT_OPTVAL_USER              = None
    DEFAULT_OPTVAL_PASS              = None

    class TagFilter:
        VALID_CASE = {
            'lower' ,
            'upper' ,
            'any'   ,
            'exact' ,
        }
        VALID_FILTER = {
            'only'       ,
            'out'        ,
            'prefer'     ,
            'not prefer' ,
        }

        DEFAULT_CASE   = 'any'
        DEFAULT_EXT    = 'any'
        DEFAULT_FILTER = 'prefer'
        DEFAULT_FOR    = 'all'

        def __init__(self, tag, default=False):
            self._tag = tag
            self._for = []

            if 'name' not in self._tag:
                _g.log.error('empty name in config tag filter')
                raise yaml.YAMLError

            self._name = self._tag['name']

            if default:
                self._case   = self.DEFAULT_CASE
                self._ext    = self.DEFAULT_EXT
                self._filter = self.DEFAULT_FILTER
                self._for    = self.DEFAULT_FOR
                return

            if 'case' not in self._tag:
                self._case = self.DEFAULT_CASE
            else:
                self._case = self._tag['case']
                # check if value is ok.
                if self._case not in self.VALID_CASE:
                    _g.log.error('bad `case` value for {}'.format(self._name))
                    self._case = self.DEFAULT_CASE

            if 'ext' not in self._tag or self._tag['ext'] == 'any':
                self._ext = self.DEFAULT_EXT
            else:
                if type(self._tag['ext']) != list:
                    _g.log.error('`ext` value not in list format for {}'
                                   .format(self._name))
                # ensure we get all strings here.
                self._ext = [str(e) for e in self._tag['ext']]

            if 'filter' not in self._tag:
                self._filter = self.DEFAULT_FILTER
            else:
                self._filter = self._tag['filter']
                # check if value is ok.
                if self._filter not in self.VALID_FILTER:
                    _g.log.error('bad `filter` value for {}'.format(self._name))
                    self._filter = self.DEFAULT_FILTER

            if 'for' not in self._tag:
                self._for = self.DEFAULT_FOR

            if self._for == 'all' or self._tag['for'] in ('all',['all']):
                return
            else:
                if type(self._tag['for']) != list:
                    _g.log.error('`for` value not in list format for {}'
                                   .format(self._name))
                # XXX this is a mess.
                for kv in self._tag['for']:
                    for name in kv:
                        r = _parsers.ParseRequest(list(chain.from_iterable(
                                                  [[name],kv[name].split()])))
                        self._for.append({name : r})

    _g.conf._home = h = os.path.expanduser('~')

    if os.name == 'posix':
        if os.path.exists('{0}/.config/madodl/config.yml'.format(h)):
            c = '{0}/.config/madodl/config.yml'.format(h)
        elif os.path.exists('{0}/.madodl/config.yml'.format(h)):
            c = '{0}/.madodl/config.yml'.format(h)
        elif os.path.exists('{0}/.madodl.yml'.format(h)):
            c = '{0}/.madodl.yml'.format(h)
        else:
            _g.log.warning('log file not found. using defaults.')
    elif os.name == 'nt':
        if os.path.exists('{0}\.madodl\config.yml'.format(h)):
            c = '{0}\.madodl\config.yml'.format(h)
        else:
            _g.log.warning('log file not found. using defaults.')
    else:
        _g.log.warning('madodl doesn`t current support a config file on your '
                       'OS. Using defaults.')

    # NOTE: placed cautiously.
    DEFAULT_OPTVAL_CACHEFILE = DEFAULT_OPTVAL_CACHEFILE(h)

    if not c:
        # XXX check back
        # FIXME: these should be None!
        _g.conf._user              = ''
        _g.conf._pass              = ''
        _g.conf._alltags           = ''
        _g.conf._default_outdir    = DEFAULT_OPTVAL_DEFAULT_OUTDIR
        _g.conf._no_output         = DEFAULT_OPTVAL_NO_OUTPUT
        _g.conf._usecache          = DEFAULT_OPTVAL_USECACHE
        _g.conf._cachefile         = DEFAULT_OPTVAL_CACHEFILE
        _g.conf._confirm_selection = DEFAULT_OPTVAL_CONFIRM_SELECTION
        return

    # NOTE: placed cautiously.
    #
    #       Apparently Python keyword-defaults bind at time of func definition
    #       rather than at each call; thus we must have all our constants set
    #       before this definition. A possible solution would be to simply call
    #       the func with l=locals() passed manually as-needed to get a fresh
    #       dict of variables, but this way seems cleaner and less likely to
    #       accumulate bugs.
    def set_simple_opt(yh, opt, l=locals()):
        vals    = l['VALID_OPTVAL_'   + opt.upper()]
        default = l['DEFAULT_OPTVAL_' + opt.upper()]

        if opt in yh:
            if not yh[opt]:
               setattr(_g.conf, '_{}'.format(opt), default)
            elif default is None and not vals:
                setattr(_g.conf, '_{}'.format(opt), yh[opt])
            elif yh[opt] in vals:
                setattr(_g.conf, '_{}'.format(opt), yh[opt])
            else:
                _g.log.error('bad config value for {}'.format(opt))
                setattr(_g.conf, '_{}'.format(opt), default)
        else:
            setattr(_g.conf, '_{}'.format(opt), default)

    with open(c) as cf:
        try:
            yh = yaml.safe_load(cf)

            for opt in yh.keys():
                if opt not in VALID_OPTS:
                    raise ConfigError('bad option `{}` in config file'
                                       .format(opt))

            if 'tags' in yh and yh['tags']:
                for t in yh['tags']:
                    alltags.append(TagFilter(t))

            _g.conf._alltags = alltags

            set_simple_opt(yh, 'no_output')
            set_simple_opt(yh, 'logfile')

            if _g.conf._logfile:
                set_simple_opt(yh, 'loglevel')

                if _g.conf._loglevel in {'debug', 'all'}:
                    loglvl = logging.DEBUG
                else:
                    loglvl = logging.INFO

                # by default, log files will rotate at 10MB with one bkup file.
                logfile_hdlr = logging.handlers.RotatingFileHandler(
                    _g.conf._logfile, maxBytes=10e6, backupCount=1)
                logfile_hdlr.setLevel(loglvl)
                logfile_hdlr.addFilter(logfile_filter)
                _g.log.addHandler(logfile_hdlr)
            else:
                _g.conf._loglevel = None

            set_simple_opt(yh, 'confirm_selection')
            set_simple_opt(yh, 'usecache')
            if _g.conf._usecache:
                set_simple_opt(yh, 'cachefile')
            else:
                _g.conf._cachefile = None

            set_simple_opt(yh, 'default_outdir')
            set_simple_opt(yh, 'user')
            if _g.conf._user:
                set_simple_opt(yh, 'pass')
            else:
                _g.conf._pass = DEFAULT_OPTVAL_PASS
        except yaml.YAMLError as yerr:
            _g.log.error('config file error: {}'.format(yerr))

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

    if _g.conf._usecache:
        # XXX move this
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
            else:
                return None

        jsonloc = os.path.join(_g.conf._home, '.cache', 'madodl',
                               'files.json') \
            if not _g.conf._cachefile else _g.conf._cachefile

        jsondirloc = os.path.dirname(jsonloc)

        if not os.path.exists(jsonloc):
            os.makedirs(jsondirloc, 0o770, True)
            _curl.curl_json_list(jsonloc, True)

        assert os.path.exists(jsonloc)

        path     = _util.create_nwo_path(manga)
        d1,d2,d3 = path.split('/')
        mdir     = None

        with breaks(open(jsonloc, errors='surrogateescape')) as f:
            jobj = json.load(f)

            for o in jobj[0].get('contents'):
                if o['name'] == 'Manga':
                    jobj = o['contents']
                    break

            global mlow
            mlow = manga.lower()
            mdir, title = match_dir(iter((d1,d2,d3)), jobj) or badret

            if not mdir:
                _g.log.warning("couldn't find title in JSON file. Trying "
                               "online query.")
                _g.conf._found_in_cache = False
                raise breaks.Break

            _g.conf._found_in_cache = True
            _g.conf._cururl = 'https://{}{}{}/{}/{}/{}'.format(loc['DOMAIN'],
                                            loc['MLOC'], d1, d2, d3, title)

            _g.log.info('\n-----\n{}-----\n'.format(mdir))

            path = '/'.join((path, title))

            return (mdir, title, path)

    qout = search_query(manga).getvalue().decode()
    qp   = _parsers.ParseQuery()
    qp.feed(qout)

    # FIXME:
    # this is a temporary workaround to
    # filter out non-manga results until
    # madokami allows for this granularity itself.
    qp.mresultnum = 0
    qp.mresults   = []
    for url, r in qp.results:
        if r.startswith('/Manga') and r.count('/') == 5:
            qp.mresults.append([url,r])
            qp.mresultnum += 1

    if qp.mresultnum == 0:
        _out.die('manga not found')

    if qp.mresultnum > 1:
        print('Multiple matches found. Please choose from the '
              'selection below:\n')
        i = 1
        for url, f in qp.mresults:
            print('{}: {}'.format(i, os.path.basename(f)))
            i += 1

        print()

        while 1:
            try:
                ch = int(input('choice > '))
                if ch in range(1, i):
                    if _g.conf._confirm_selection:
                        sel_no = False

                        while 1:
                            confirm = input('Download `{}`? [yn] > '
                                              .format(os.path.basename(
                                                qp.mresults[ch-1][1])))
                            if confirm.lower() in {'y', 'yes'}:
                                break
                            elif confirm.lower() in {'n', 'no'}:
                                sel_no = True
                                break
                        if sel_no:
                            continue

                    break
                print('Pick a number between 1 and {}'.format(i-1))
            except ValueError:
                print('Invalid input.')

        m     = qp.mresults[ch-1][0]
        title = os.path.basename(qp.mresults[ch-1][1])
    else:
        m     = qp.mresults[0][0]
        title = os.path.basename(qp.mresults[0][1])

        _out._('one match found: {}'.format(title))

    dirls = search_exact(m, True).getvalue().decode()

    _g.log.info('\n-----\n{}-----'.format(dirls))

    return (dirls, title, m)

def subdir_recurse(listing, path, depth=1):
    # XXX add a knob for this
    if depth > 256:
        _out.die('reached max recursion depth')

    for idx in range(len(listing)):
        d_or_f, fname = (listing[idx]['type'], listing[idx]['name'])
        this_path     = ''.join([path, '/', fname])

        if d_or_f == 'directory':
            listing[idx] = subdir_recurse(listing[idx]['contents'],
                                          this_path, depth+1)
        elif d_or_f == 'file':
            title          = Struct()
            title.basename = path
            title.name     = fname
            title.path     = this_path
            listing[idx]   = title
        else: # sanity check
            _out.die('BUG: unsupported file type `{}`'.format(d_or_f))

    if depth != 1:
        return listing

    return _util.flatten_sublists(listing)

def rem_subdir_recurse(listing, path, depth=1):
    # XXX add a knob for this
    if depth > 256:
        _out.die('reached max recursion depth')

    for idx in range(len(listing)):
        # madokami's FTP LIST format is long ls, [{}/, are meta tokens]:
        # {d,-}rwxrwxrwx 1 u g sz mon day y/time fname
        #  |                                     |
        #  |=> directory or regular file         |=> filename
        #
        # XXX: while highly unlikely that whitespace gives any significant
        # distinction beyond one space, the split() module splits by any amount         # of wspace; thus, when re-join()ed, any extra wspace is truncated to
        # one space.
        fields        = listing[idx].split()
        d_or_f, fname = (fields[0][:1], ' '.join(fields[8:]))
        this_path     = ''.join([path, '/', fname])

        if d_or_f == 'd':
            listing[idx] = rem_subdir_recurse(search_exact(this_path, True)
                                                .getvalue()
                                                .decode()
                                                .splitlines(),
                                              this_path, depth+1)
        elif d_or_f == '-': # is reg file
            title          = Struct()
            title.basename = path
            title.name     = fname
            title.path     = this_path
            listing[idx]   = title
        else: # sanity check
            _out.die('BUG: unsupported file type `{}`'.format(d_or_f))

    if depth != 1:
        return listing

    return _util.flatten_sublists(listing)

def main_loop(manga_list):
    global compc, compv

    for m in manga_list:
            req               = _parsers.ParseRequest(m)
            sout, title, path = get_listing(req._name)

            if _g.conf._usecache and _g.conf._found_in_cache:
                sout = subdir_recurse(sout, path)
            else:
                sout = sout.splitlines()
                sout = rem_subdir_recurse(sout, path)

            compv, compc, allf, compfile = walk_thru_listing(req, title, sout)

            if req._vols and req._vols[-1] == req.ALL:
                del req._vols[-1]

            if req._chps and req._chps[-1] == req.ALL:
                del req._chps[-1]

            missv = str([v for v in req._vols if v not in compv]).strip('[]')
            missc = str([c for c in req._chps if c not in compc]).strip('[]')

            if missv:
                _out._("couldn't find vol(s): " + missv)

            if missc:
                _out._("couldn't find chp(s): " + missc)

            if any((compfile, compc, compv)):
                # XXX sigh...
                # need to append MLOC when we get a cache hit.
                ppfx = ''.join(['https://', loc['DOMAIN']])

                if _g.conf._found_in_cache:
                    ppfx = ''.join([ppfx, loc['MLOC']])

                try:
                    stdscr          = unicurses.initscr()
                    _g.conf._stdscr = stdscr
                    unicurses.noecho()

                    if compfile:
                        _out._('downloading complete archive... ', end='')
                        _g.conf._stdscr.erase()
                        _g.conf._stdscr.addstr(0, 0, compfile.name)
                        _g.conf._stdscr.refresh()
                        _curl.curl_to_file('/'.join([ppfx,
                                                     _util.create_nwo_basename(
                                                        compfile.basename),
                                                     urllib
                                                       .parse
                                                       .quote(compfile.name)]),
                                           compfile.name, 'HTTP')
                    elif compv or compc:
                        _out._('downloading volume/chapters... ', end='')
                        for f,v,c in allf:
                            #_g.log.info('DL ' + f)
                            _g.conf._stdscr.erase()
                            _g.conf._stdscr.addstr(0, 0, 'title - {}'
                                                           .format(title))
                            _g.conf._stdscr.addstr(1, 0, 'current - {}'
                                                           .format(f.name))
                            _g.conf._stdscr.refresh()
                            _curl.curl_to_file('/'.join([ppfx,
                                                         _util
                                                           .create_nwo_basename(                                                             f.basename),
                                                         urllib
                                                           .parse
                                                           .quote(f.name)]),
                                               f.name, 'HTTP')
                except:
                    raise
                finally:
                    unicurses.nocbreak()
                    _g.conf._stdscr.keypad(False)
                    unicurses.echo()
                    unicurses.endwin()

                print('done', file=sys.stderr)
            else:
                _out._('could not find any requested volume/chapters.')
                return 1

    return 0

#
# TODO:
# - global extension filters
# - allow greedy v/c matching
# - add -p switch
# - allow non-manga DL's
# - msg output w/ unicurses
# - allow for pausing and skipping during DL
# - allow regex in config.yml
#
def main():
    try:
        _g.conf = Struct()
        args    = init_args()

        local_import()
        init_config()

        if args.outdir:
            _g.conf._outdir = args.outdir
        else:
            _g.conf._outdir = _g.conf._default_outdir

        if args.auth:
            up = args.auth.split(':', 1)

            if len(up) == 1 or '' in up:
                _out.die('argument -a: bad auth format')

            _g.conf._user, _g.conf._pass = up

        if args.silent or _g.conf._no_output:
            # go ahead and set this so it is globally known.
            # there is no need for distinction at this point.
            _g.conf._no_output = True
            _g.log.addFilter(nullfilter)

        ret = main_loop(args.manga)
    except (KeyboardInterrupt, EOFError) as e:
        print()
        _out._('caught {} signal, exiting...'.format(type(e).__name__))
        return 0

    return ret

if __name__ == '__main__':
    sys.exit(main())
