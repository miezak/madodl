#!/usr/bin/env python3

#
# user output functions
#

import os, sys

import madodl.gvars as _g

def die(msg, lvl='error', **kwargs):
    if lvl:
      getattr(_g.log, lvl.lower())(msg, **kwargs)
    sys.exit(1)

def _(msg, file=sys.stderr, **kwargs):
    if not _g.conf._no_output:
        print('{}: {}'.format(os.path.basename(__file__), msg), file=file,
                              **kwargs)

    return None
