# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow._sdk._configuration import Configuration

# This logic is copied from: https://github.com/microsoft/knack/blob/dev/knack/help.py
# Will print privacy message and welcome when user run `pf` command.

PRIVACY_STATEMENT = """
Welcome to prompt flow!
---------------------
Use `pf -h` to see available commands or go to https://aka.ms/pf-cli.

Telemetry
---------
The prompt flow CLI collects usage data in order to improve your experience.
The data is anonymous and does not include commandline argument values.
The data is collected by Microsoft.

You can change your telemetry settings with `pf config`.
"""

WELCOME_MESSAGE = r"""
 ____                            _      __ _
|  _ \ _ __ ___  _ __ ___  _ __ | |_   / _| | _____      __
| |_) | '__/ _ \| '_ ` _ \| '_ \| __| | |_| |/ _ \ \ /\ / /
|  __/| | | (_) | | | | | | |_) | |_  |  _| | (_) \ V  V /
|_|   |_|  \___/|_| |_| |_| .__/ \__| |_| |_|\___/ \_/\_/
                          |_|

Welcome to the cool prompt flow CLI!

Use `pf --version` to display the current version.
Here are the base commands:
"""


def show_privacy_statement():
    config = Configuration.get_instance()
    ran_before = config.get_config("first_run")
    if not ran_before:
        print(PRIVACY_STATEMENT)
        config.set_config("first_run", True)


def show_welcome_message():
    print(WELCOME_MESSAGE)
