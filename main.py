#!/usr/bin/python

# XXX temporary hack to pickle the status with "doaddoad" module not __main__
# the real solution would be to pack doaddoad into a package/module and write setup.py with setuptools

import sys

import doaddoad

if __name__ == '__main__':
    sys.exit(doaddoad.main())
