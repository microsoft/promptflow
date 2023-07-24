# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import sys
import subprocess

from dataclasses import dataclass, field


@dataclass
class RTInstance:
    pid: str = field(default=-1)
    """the starting app."""
    command: str = field(default="")
    """the server type, available: dev, command"""


def stop_existing_rt_instances(dry_run=False):
    rt_instances = []
    if sys.platform.startswith("linux"):
        ps = "ps -eo pid,args | grep promptflow | grep python | grep create_app"
        for x in os.popen(ps):
            x = x.strip().rstrip("\n")
            pid, command = x.split(" ", 1)
            instance = RTInstance(pid, command)
            rt_instances.append(instance)

        print("Found %s rt instances" % len(rt_instances))
        for rt in rt_instances:
            print("Stop rt instance, pid: %s" % rt.pid)
            # TODO graceful shutdown by calling rt api
            if not dry_run:
                # kill by linux kill now
                args = ["kill", "-15", f"{rt.pid}"]
                subprocess.check_call(args)
    return rt_instances


def show_sdk_version():
    show_cmd = f"{sys.executable} -m pip list | grep prompt"
    v = os.popen(show_cmd).read()
    print("current version: %s" % v)


def upgrade(version, extra_index_url=None, dry_run=False):
    show_sdk_version()
    # install target version sdk
    package_name = f"promptflow-sdk[azure,builtins]=={version}"
    args = [
        sys.executable,
        "-m",
        "pip",
        "install",
        package_name,
    ]

    if extra_index_url is None and version.startswith("0.0"):
        extra_index_url = "https://azuremlsdktestpypi.azureedge.net/promptflow/"
    if extra_index_url:
        args += ["--extra-index-url", extra_index_url]
    print("Installing package: %s" % args)
    if not dry_run:
        subprocess.check_call(args)
        show_sdk_version()

    # stop existing rt instances, ingress will help to start new rt instances
    print("Restart existing rt instances:")
    stop_existing_rt_instances(dry_run=dry_run)


if __name__ == "__main__":
    upgrade(version="0.0.89855504", dry_run=False)
