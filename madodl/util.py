#!/usr/bin/env python3

#
# utility functions
#

import re
from itertools import chain

import out as _out

def rm_req_elems(req, comp):
    for n in comp:
        if n in req:
            req.remove(n)

    return None

def common_elem(iter1, iter2):
    assert iter1 and iter2
    loc1 = iter1
    loc2 = chain.from_iterable(iter2)
    for elem in loc1:
        if elem in loc2:
            yield elem

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
