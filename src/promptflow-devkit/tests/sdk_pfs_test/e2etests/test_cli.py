# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import subprocess
import sys
import timeit

import pytest

from promptflow._cli._pf.entry import main
from promptflow._sdk._service.utils.utils import (
    get_pfs_host,
    get_pfs_host_after_check_wildcard,
    get_port_from_config,
    is_pfs_service_healthy,
    kill_exist_service,
)


@pytest.mark.e2etest
class TestPromptflowServiceCLI:
    def _run_pfs_command(self, *args):
        """Run a pfs command with the given arguments."""
        origin_argv = sys.argv
        try:
            sys.argv = ["pf", "service"] + list(args)
            main()
        finally:
            sys.argv = origin_argv

    def _test_start_service(self, service_host, port=None, force=False):
        command = f"pf service start --port {port}" if port else "pf service start"
        if force:
            command = f"{command} --force"
        start_pfs = subprocess.Popen(command, shell=True)
        # Wait for service to be started
        start_pfs.wait()
        assert self._is_service_healthy(service_host)
        stop_command = "pf service stop"
        stop_pfs = subprocess.Popen(stop_command, shell=True)
        stop_pfs.wait()

    def _is_service_healthy(self, service_host, port=None, time_limit=0.1):
        service_host = get_pfs_host_after_check_wildcard(service_host)
        port = port or get_port_from_config(service_host)
        st = timeit.default_timer()
        is_healthy = is_pfs_service_healthy(port, service_host)
        ed = timeit.default_timer()
        assert ed - st < time_limit, f"The time limit is {time_limit}s, but it took {ed - st}s."
        return is_healthy

    def test_start_service(self, capsys):
        try:
            service_host = get_pfs_host()
            # force start pfs
            self._test_start_service(service_host, force=True)
            # start pfs
            start_pfs = subprocess.Popen("pf service start", shell=True)
            # Wait for service to be started
            start_pfs.wait()
            assert self._is_service_healthy(service_host)

            # show-status
            self._run_pfs_command("status")
            output, _ = capsys.readouterr()
            port = get_port_from_config(service_host)
            assert str(port) in output

            self._test_start_service(service_host, force=True)
            # previous pfs is killed
            assert start_pfs.poll() is not None
            python_dir = os.path.dirname(sys.executable)
            # python directory will be changed to Scripts directory after we switched to poetry in ci
            executable_dir = python_dir
            assert executable_dir in os.environ["PATH"].split(os.pathsep)
        finally:
            port = get_port_from_config(service_host)
            kill_exist_service(port=port)
            self._run_pfs_command("status")
