# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

"""!!!Note: context in this file only used for command line related logics,
please avoid using them in service code!!!"""
import contextlib
import os
import sys
import threading

# os.chdir is process-global; serialise concurrent uses so that threads in the
# line-execution process pool cannot observe each other's intermediate cwd state.
# See https://github.com/microsoft/promptflow/issues/3553
_working_dir_lock = threading.Lock()


@contextlib.contextmanager
def _change_working_dir(path, mkdir=True):
    """Context manager for changing the current working directory.

    Uses a module-level lock to prevent concurrent threads from observing
    each other's intermediate ``os.chdir`` state.
    """
    if mkdir:
        os.makedirs(path, exist_ok=True)
    with _working_dir_lock:
        saved_path = os.getcwd()
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
