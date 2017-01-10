#!/usr/bin/env python3

#
# utility functions
#

import re
import urllib.parse
from   itertools import chain

import madodl.out as _out

def rm_req_elems(req, comp):
    for n in comp:
        if n in req:
            req.remove(n)

    return None

#
# XXX this looks to be O(n^2) to me. check if python
#     optimizes this or has a std util for it.
#
def common_elem(iter1, iter2, flat=True):
    if not any((iter1, iter2)):
        return None

    loc1 = iter1
    loc2 = iter2

    if not flat:
        loc2 = chain.from_iterable(iter2)

    for elem in loc1:
        if elem in loc2:
            return elem

    return None

def common_elem_gen(iter1, iter2, flat=True):
    if not any((iter1, iter2)):
        return None

    loc1 = iter1
    loc2 = iter2

    if not flat:
        loc2 = chain.from_iterable(iter2)

    for elem in loc1:
        if elem in loc2:
            yield elem

    return None

def create_nwo_path(name):
    '''Create the exact path that the manga `name` should be in.

       This path is constructed in the `New World Order` format
       described here: manga.madokami.com/Info/NewWorldOrder.txt

       Parameters:
       name - the name of the manga to convert to NWO format.
    '''
    if not name:
        _out.die('need a name with at least one character!')
        return None

    name = re.sub(r'^(the|an?) ', '', name, flags=re.I)
    name = name.upper()

    return re.sub(r'^(.)(.|)?(.|)?(.|)?.*', r'\1/\1\2/\1\2\3\4', name)

def create_nwo_basename(path):
    '''URL encode basename path when there are >= 4 dirs'''
    if path.count('/') == 3:
        return path

    path   = path.split('/')
    nwo_bn = path[:3]
    nwo_bn.extend([urllib.parse.quote(d) for d in path[3:]])

    return '/'.join(nwo_bn)

def conv_bytes(bvar):
    if bvar / 1024**3 >= 1:
        ret = ''.join([str(round((bvar / 1024**3), 2)), ' GB'])
    elif bvar / 1024**2 >= 1:
        ret = ''.join([str(round((bvar / 1024**2), 2)), ' MB'])
    elif bvar / 1024 >= 1:
        ret = ''.join([str(round((bvar / 1024), 2)), ' KB'])
    else:
        ret = ''.join([str(bvar), ' B'])

    return ret

def flatten_sublists(ls):
    retls = []

    for obj in ls:
        if not isinstance(obj, list):
            retls.append(obj)
        else:
            retls.extend(flatten_sublists(obj))

    return retls
