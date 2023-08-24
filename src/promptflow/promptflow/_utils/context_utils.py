# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

"""!!!Note: context in this file only used for command line related logics,
please avoid using them in service code!!!"""
import contextlib
import os
import sys


@contextlib.contextmanager
def _change_working_dir(path, mkdir=True):
    """Context manager for changing the current working directory"""
    saved_path = os.getcwd()
    if mkdir:
        os.makedirs(path, exist_ok=True)
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(saved_path)


@contextlib.contextmanager
def inject_sys_path(path):
    original_sys_path = sys.path.copy()
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path = original_sys_path
