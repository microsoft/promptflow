# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import List

import requests


class LocalServiceOperations:
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
