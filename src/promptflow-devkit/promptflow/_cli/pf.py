# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow._cli._pf.entry import main

# this is a compatibility layer for the old CLI which is used for vscode extension
if __name__ == "__main__":
    main()
