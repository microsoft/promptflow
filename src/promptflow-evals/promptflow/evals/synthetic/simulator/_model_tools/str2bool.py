# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse


def str2bool(val):
    """
    Resolving boolean arguments if they are not given in the standard format

    :param val: (bool or string) boolean argument type
    :type val: bool or str
    :return: (bool) the desired value {True, False}
    :rtype: bool
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        if val.lower() in ("yes", "true", "t", "y", "1"):
            return True
        if val.lower() in ("no", "false", "f", "n", "0"):
            return False
    raise argparse.ArgumentTypeError("Boolean value expected.")
