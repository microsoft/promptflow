# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import signal
import subprocess
from typing import List

import requests

PFS_PID_ENV_VAR = "PFS_PID"


class PFSOperations:
    def __init__(self):
        self._host = "http://localhost:5000"
        self._run_endpoint = f"{self._host}/run/v1.0"

    def heartbeat(self) -> requests.Response:
        return requests.get(f"{self._host}/heartbeat")

    def list(self) -> List[dict]:
        # TODO: add query parameters
        return requests.get(f"{self._run_endpoint}/list").json()

    def get(self, name: str) -> dict:
        return requests.get(f"{self._run_endpoint}/{name}").json()

    def get_metadata(self, name: str) -> dict:
        return requests.get(f"{self._run_endpoint}/{name}/metadata").json()

    def get_detail(self, name: str) -> dict:
        return requests.get(f"{self._run_endpoint}/{name}/detail").json()


def start_pfs() -> None:
    proc = subprocess.Popen(
        "python -m promptflow._sdk._service.entry",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    os.environ[PFS_PID_ENV_VAR] = str(proc.pid)


def stop_pfs() -> None:
    try:
        # windows does not support SIGTERM, so we need to check OS first
        if os.name == "nt":
            os.kill(int(os.getenv(PFS_PID_ENV_VAR)), signal.CTRL_C_EVENT)
        else:
            os.kill(int(os.getenv(PFS_PID_ENV_VAR)), signal.SIGTERM)
    except:  # noqa: E722
        pass
