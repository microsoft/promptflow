# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, OrderedDict

from promptflow._sdk._configuration import Configuration
from promptflow._sdk._errors import RecordFileMissingException, RecordItemMissingException
from promptflow._utils.dataclass_serializer import serialize
from promptflow._utils.tool_utils import get_inputs_for_prompt_template


class RecordStorage(object):
    standard_record_name = ".cache/storage_record.json"
    _instance = None

    def __init__(self, input_path: str = None):
        """
        Status: binding with files inside .promptflow/
        """
        #
        self.input_path: Path = None
        self._input_path_str: str = None
        self.cached_items: Dict[str, Dict[str, Dict[str, object]]] = {}
        # cached items
        # {
        #    "/input/path/resolved": {
        #       "hash_value": { # hash_value is sha1 of dict
        #           "input": {
        #             "key1": "value1" Converted to string, type info dropped
        #           }
        #           "output": "output" Convert to string
        #           "output_type": "output_type" Currently support simple types.
        #       }
        #    }
        # }
        self.set_input_path(input_path)

    def _write_file(self) -> None:
        file_content = self.cached_items.get(self._input_path_str, None)

        if file_content is not None:
            with open(self.input_path, "w+") as fp:
                json.dump(self.cached_items[self._input_path_str], fp, indent=4)

    def _load_file(self) -> None:
        local_content = self.cached_items.get(self._input_path_str, None)
        if not local_content:
            if not self.input_path.exists():
                return
            with open(self.input_path, "r", encoding="utf-8") as fp:
                self.cached_items[self._input_path_str] = json.load(fp)

    def get_record(self, input_dict: OrderedDict) -> object:
        hash_value: str = hashlib.sha1(str(input_dict).encode("utf-8")).hexdigest()
        current_saved_records: Dict[str, str] = self.cached_items.get(self._input_path_str, None)
        if current_saved_records is None:
            raise RecordFileMissingException(
                f"This should except earlier, record file not found in folder {self.input_path}."
            )
        saved_output = current_saved_records.get(hash_value, None)
        if saved_output is None:
            raise RecordItemMissingException(
                f"Record item not found in folder {self.input_path}.\n" f"values: {json.dumps(input_dict)}\n"
            )

        output = saved_output["output"]
        output_type = saved_output["output_type"]
        if output_type == "str":
            return output
        elif output_type == "int":
            return int(output)
        elif output_type == "float":
            return float(output)
        elif output_type == "bool":
            return bool(output)
        else:
            raise Exception(f"Unsupported type {output_type}")

    def set_record(self, input_dict: OrderedDict, output: object) -> None:
        hash_value: str = hashlib.sha1(str(input_dict).encode("utf-8")).hexdigest()
        current_saved_records: Dict[str, str] = self.cached_items.get(self._input_path_str, None)

        if current_saved_records is None:
            current_saved_records = {}
            current_saved_records[hash_value] = {
                "input": input_dict,
                "output": output,
                "output_type": type(output).__name__,
            }
        else:
            saved_output = current_saved_records.get(hash_value, None)
            if saved_output is not None:
                if saved_output["output"] == str(output) and saved_output["output_type"] == type(output).__name__:
                    return
                else:
                    current_saved_records[hash_value] = {
                        "input": input_dict,
                        "output": output,
                        "output_type": type(output).__name__,
                    }
            else:
                current_saved_records[hash_value] = {
                    "input": input_dict,
                    "output": output,
                    "output_type": type(output).__name__,
                }
        self.cached_items[self._input_path_str] = current_saved_records
        self._write_file()

    def set_input_path(self, input_path):
        if input_path == self.input_path:
            return
        self.input_path = Path(input_path).resolve()
        self._input_path_str = str(self.input_path)
        if not os.path.exists(self.input_path.parent.parent):
            raise Exception(f"{self.input_path.parent.parent} does not exist")
        # cache folder we could create if not exist.
        if not self.input_path.parent.exists():
            os.makedirs(self.input_path.parent, exist_ok=True)
        # if file exist, load file
        if os.path.exists(self.input_path):
            self._load_file()

    @classmethod
    def get_instance(cls, input_path=None) -> "RecordStorage":
        """
        get_instance Use this to get instance to avoid multiple copies of same record storage.

        :param input_path: initiate at first entrance, defaults to None in the first call will raise exception.
        :type input_path: str or Path, optional
        :return: instance of RecordStorage
        :rtype: RecordStorage
        """
        # if not in recording mode, return None
        if not Configuration.get_instance().is_recording_mode():
            return None
        # Create instance if not exist
        if cls._instance is None:
            if input_path is None:
                raise Exception("input_path is None")
            cls._instance = RecordStorage(input_path=input_path)
        # Override configuration of recording file
        if Configuration.get_instance().get_recording_file_override() is not None:
            cls._instance.set_input_path(Configuration.get_instance().get_recording_file_override())
            return cls._instance
        if input_path is not None:
            cls._instance.set_input_path(input_path)
            return cls._instance
        return cls._instance

    def _record_node_run(self, run_info, api_call: Dict[str, Any]) -> None:
        hashDict = {}
        # current
        if "name" in api_call and api_call["name"].startswith("AzureOpenAI"):
            prompt_tpl = api_call["inputs"]["prompt"]
            prompt_tpl_inputs = get_inputs_for_prompt_template(prompt_tpl)

            for keyword in prompt_tpl_inputs:
                if keyword in api_call["inputs"]:
                    hashDict[keyword] = api_call["inputs"][keyword]
            hashDict["prompt"] = prompt_tpl
            hashDict = collections.OrderedDict(sorted(hashDict.items()))
            item = serialize(run_info)
            self.set_record(hashDict, str(item["output"]))

    def record_node_run(self, run_info: Any) -> None:
        """Recording: Persist llm node run record to local storage."""
        if isinstance(run_info, dict):
            for api_call in run_info["api_calls"]:
                self._record_node_run(run_info, api_call)
        else:
            for api_call in run_info.api_calls:
                self._record_node_run(run_info, api_call)
