#!/usr/bin/env python
# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os


def main():
    if os.environ.get("PF_INSTALLER") is None:
        os.environ["PF_INSTALLER"] = "PIP"

    from promptflow._cli._pf.entry import main as _main

    _main()


# this is a compatibility layer for the old CLI which is used for vscode extension
if __name__ == "__main__":
    main()
