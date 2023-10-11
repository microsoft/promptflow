# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import base64
import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, NewType

from jinja2 import Environment, meta

from promptflow._sdk.entities import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo


class RecordingEnv:
    PF_RECORDING_MODE = os.environ.get("PF_RECORDING_MODE")
    PF_REPLAY_TIMEOUT_MODE = os.environ.get("PF_REPLAY_TIMEOUT_MODE")
    PF_RECORDING_REGEX = os.environ.get("PF_RECORDING_REGEX")


RunInputHash = NewType("RunInputHash", str)
RunOutputHash = NewType("RunOutputHash", str)
RunDict = NewType("RunDict", Dict[RunInputHash, RunOutputHash])


class MyStorageRecord:
    runItems: RunDict = {}

    @classmethod
    def dump(path: Path) -> None:
        with open(path, "w") as f:
            json.dump(MyStorageRecord.runItems, f)


def get_inputs_for_prompt_template(template_str):
    """Get all input variable names from a jinja2 template string."""
    env = Environment()
    template = env.parse(template_str)
    return sorted(meta.find_undeclared_variables(template), key=lambda x: template_str.find(x))


class MyStorageOperation(LocalStorageOperations):
    def __init__(self, run: Run, stream=False):
        super().__init__(run, stream)
        self._runInputHash: RunInputHash = None
        self._runOutputHash: RunOutputHash = None

    def persist_node_run(self, run_info: NodeRunInfo) -> None:
        """Persist node run record to local storage."""
        super().persist_node_run(run_info)
        hashDict = {}
        if "PF_RECORDING_MODE" in os.environ and os.environ["PF_RECORDING_MODE"] == "record":
            if "name" in run_info.api_calls[0] and run_info.api_calls[0]["name"].startswith("AzureOpenAI"):
                prompt_tpl = run_info.inputs["prompt"]
                prompt_tpl_inputs = get_inputs_for_prompt_template(prompt_tpl)

                for keyword in prompt_tpl_inputs:
                    if keyword in run_info.inputs:
                        hashDict[keyword] = run_info.inputs[keyword]
                hashDict["prompt"] = prompt_tpl
                hashDict = collections.OrderedDict(sorted(hashDict.items()))
                hashValue = hashlib.sha1(str(hashDict).encode("utf-8")).hexdigest()

                MyStorageRecord.runItems[hashValue] = base64.b64encode(
                    bytes(hashlib.run_info.inputs["output"], "utf-8")
                )
                MyStorageRecord.dump("MyStorageRecord.json")

    def persist_flow_run(self, run_info: FlowRunInfo):
        super().persist_flow_run(run_info)
