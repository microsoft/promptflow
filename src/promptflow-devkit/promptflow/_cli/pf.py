#!/usr/bin/env python
# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
import sys


def main():
    if os.environ.get("PF_INSTALLER") is None:
        os.environ["PF_INSTALLER"] = "PIP"

    os.execl(sys.executable, sys.executable, "-m", "promptflow._cli._pf.entry", *sys.argv[1:])


# this is a compatibility layer for the old CLI which is used for vscode extension
if __name__ == "__main__":
    main()
