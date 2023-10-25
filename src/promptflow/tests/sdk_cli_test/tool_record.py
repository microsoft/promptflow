# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, OrderedDict

from promptflow._internal import ToolProvider, tool
from promptflow._utils.dataclass_serializer import serialize
from promptflow._utils.tool_utils import get_inputs_for_prompt_template
from promptflow.contracts.run_info import RunInfo as NodeRunInfo


class RecordStorage:
    """
    RecordStorage static class to manage recording file storage_record.json
    """

    runItems: Dict[str, Dict[str, str]] = {}

    @staticmethod
    def write_file(flow_directory: Path) -> None:

        path_hash = hashlib.sha1(str(flow_directory.parts[-4:-1]).encode("utf-8")).hexdigest()
        file_content = RecordStorage.runItems.get(path_hash, None)
        if file_content is not None:
            with open(flow_directory / "storage_record.json", "w+") as fp:
                json.dump(RecordStorage.runItems[path_hash], fp, indent=4)

    @staticmethod
    def load_file(flow_directory: Path) -> None:
        path_hash = hashlib.sha1(str(flow_directory.parts[-4:-1]).encode("utf-8")).hexdigest()
        local_content = RecordStorage.runItems.get(path_hash, None)
        if not local_content:
            if not os.path.exists(flow_directory / "storage_record.json"):
                return
            with open(flow_directory / "storage_record.json", "r", encoding="utf-8") as fp:
                RecordStorage.runItems[path_hash] = json.load(fp)

    @staticmethod
    def get_record(flow_directory: Path, hashDict: OrderedDict) -> str:
        # special deal remove text_content, because it is not stable.
        if "text_content" in hashDict:
            hashDict.pop("text_content")

        hash_value: str = hashlib.sha1(str(hashDict).encode("utf-8")).hexdigest()
        path_hash: str = hashlib.sha1(str(flow_directory.parts[-4:-1]).encode("utf-8")).hexdigest()
        file_item: Dict[str, str] = RecordStorage.runItems.get(path_hash, None)
        if file_item is None:
            RecordStorage.load_file(flow_directory)
            file_item = RecordStorage.runItems.get(path_hash, None)
        if file_item is not None:
            item = file_item.get(hash_value, None)
            if item is not None:
                real_item = base64.b64decode(bytes(item, "utf-8")).decode()
                return real_item
            else:
                raise BaseException(
                    f"Record item not found in folder {flow_directory}.\n"
                    f"Path hash {path_hash}\nHash value: {hash_value}\n"
                    f"Hash dict: {hashDict}\nHashed values: {json.dumps(hashDict)}\n"
                )
        else:
            raise BaseException(f"Record file not found in folder {flow_directory}.")

    @staticmethod
    def set_record(flow_directory: Path, hashDict: OrderedDict, output: object) -> None:
        # special deal remove text_content, because it is not stable.
        if "text_content" in hashDict:
            hashDict.pop("text_content")
        hash_value: str = hashlib.sha1(str(hashDict).encode("utf-8")).hexdigest()
        path_hash: str = hashlib.sha1(str(flow_directory.parts[-4:-1]).encode("utf-8")).hexdigest()
        output_base64: str = base64.b64encode(bytes(output, "utf-8")).decode(encoding="utf-8")
        current_saved_record: Dict[str, str] = RecordStorage.runItems.get(path_hash, None)
        if current_saved_record is None:
            RecordStorage.load_file(flow_directory)
            if RecordStorage.runItems is None:
                RecordStorage.runItems = {}
            if (RecordStorage.runItems.get(path_hash, None)) is None:
                RecordStorage.runItems[path_hash] = {}
            RecordStorage.runItems[path_hash][hash_value] = output_base64
            RecordStorage.write_file(flow_directory)
        else:
            saved_output = current_saved_record.get(hash_value, None)
            if saved_output is not None and saved_output == output_base64:
                return
            else:
                current_saved_record[hash_value] = output_base64
                RecordStorage.write_file(flow_directory)


class ToolRecord(ToolProvider):
    """
    ToolRecord Record inputs and outputs of llm tool, in replay mode,
    this tool will read the cached result from storage_record.json
    """

    @tool
    def completion(toolType: str, *args, **kwargs) -> str:
        # "AzureOpenAI" =  args[0], this is type indicator, there may be more than one indicators
        prompt_tmpl = args[1]
        prompt_tpl_inputs = args[2]
        working_folder = args[3]

        hashDict = {}
        for keyword in prompt_tpl_inputs:
            if keyword in kwargs:
                hashDict[keyword] = kwargs[keyword]
        hashDict["prompt"] = prompt_tmpl
        hashDict = collections.OrderedDict(sorted(hashDict.items()))

        real_item = RecordStorage.get_record(working_folder, hashDict)
        return real_item


@tool
def just_return(toolType: str, *args, **kwargs) -> str:
    return ToolRecord().completion(toolType, *args, **kwargs)


def record_node_run(run_info: NodeRunInfo, flow_folder: Path) -> None:
    """Persist node run record to local storage."""
    if os.environ.get("PF_RECORDING_MODE", None) == "record":
        for api_call in run_info.api_calls:
            hashDict = {}
            if "name" in api_call and api_call["name"].startswith("AzureOpenAI"):
                prompt_tpl = api_call["inputs"]["prompt"]
                prompt_tpl_inputs = get_inputs_for_prompt_template(prompt_tpl)

                for keyword in prompt_tpl_inputs:
                    if keyword in api_call["inputs"]:
                        hashDict[keyword] = api_call["inputs"][keyword]
                hashDict["prompt"] = prompt_tpl
                hashDict = collections.OrderedDict(sorted(hashDict.items()))
                item = serialize(run_info)
                RecordStorage.set_record(flow_folder, hashDict, str(item["output"]))
