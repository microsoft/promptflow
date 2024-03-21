# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import contextlib
import os
import platform
import subprocess
import sys
from pathlib import Path

REPO_ROOT_DIR = Path(__file__).parent.parent.parent


class Color:
    BLUE = "\033[94m"
    YELLOW = "\033[93m"
    END = "\033[0m"


def print_blue(msg: str) -> None:
    print(Color.BLUE + msg + Color.END)


def print_yellow(msg: str) -> None:
    print(Color.YELLOW + msg + Color.END)


@contextlib.contextmanager
def change_cwd(path):
    cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(cwd)


def run_cmd(cmd, verbose: bool = False) -> None:
    print_blue(f"Running {' '.join(cmd)}")
    shell = platform.system() == "Windows"
    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=shell,
    )
    for line in p.stdout:
        line = line.decode("utf-8").rstrip()
        if verbose:
            sys.stdout.write(f"{line}\n")
    p.communicate()
