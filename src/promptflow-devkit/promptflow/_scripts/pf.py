#!/usr/bin/env python

import sys
import os

def main():
    if os.environ.get('PF_INSTALLER') is None:
        os.environ['PF_INSTALLER'] = 'PIP'

    os.execl(sys.executable, sys.executable, '-m', 'promptflow._cli._pf.entry', *sys.argv[1:])

if __name__ == '__main__':
    main()